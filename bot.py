from telegram.ext import Updater, CommandHandler, run_async
import os
import requests
import subprocess
import logging
import shutil
import uuid
from base import Bookmark, Watch, Role, User, drop, make_session, with_session
from screenshot import make_screenshot
import watchers

updater = Updater(os.environ['TELEGRAM_TOKEN'], workers=8)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


def broadcast_chats(session, func, *filters):
    ids = set()
    for watch in session.query(Watch).filter(Watch.filter.in_(filters)).all():
        if watch.chat_id not in ids:
            ids.add(watch.chat_id)
            try:
                func(session, watch.chat_id)
            except Exception as e:
                log.exception(e)


class TgHandler(logging.Handler):
    def __init__(self, level):
        logging.Handler.__init__(self, level)

    def emit(self, entry):
        message = self.format(entry)[-4096:]
        def send(_, chat):
            # avoid hitting telegram limits
            try:
                updater.bot.send_message(chat, message)
            except Exception as e:
                "to avoid loops"
                print(str(e))
        with_session(broadcast_chats)(send, 'log')


logging.getLogger().addHandler(TgHandler(logging.INFO))


def command(command):
    def decorator(func):
        updater.dispatcher.add_handler(CommandHandler(command, func))
        return func
    return decorator


def replyerrors(func):
    def result(bot, update):
        try:
            func(bot, update)
        except Exception as e:
            update.message.reply_text('error: ' + str(e), quote=True)
            raise e
    return result


def guard(predicate, message=None):
    def decorator(func):
        def handler(bot, update):
            if predicate(update):
                func(bot, update)
            else:
                if message is not None:
                    update.message.reply_text(message, quote=True)
                log.info('denied access for %s', update.message.chat)
        return handler
    return decorator


def retry(cnt):
    def decorator(func):
        def handler(bot, update):
            for i in range(cnt):
                try:
                    func(bot, update)
                    break
                except Exception as e:
                    log.exception(e)
                    if i == (cnt - 1):
                        raise e
        return handler
    return decorator


def check_role(role_name):
    @with_session
    def check(session, update):
        return session.query(User)\
                .filter(User.id == update.message.from_user.id)\
                .join(User.roles)\
                .filter(Role.name == role_name)\
                .first()
    return guard(check, "you are not {}".format(role_name))


def owner(*users):
    def pred(update):
        return update.message.chat.type == 'private' and \
               update.message.from_user.username in users
    return guard(pred, "only {} have access to this handler".format(", ".join(users)))


@command('ping')
def ping(bot, update):
    update.message.reply_text('pong')


@command('dump')
@owner('ssmike')
def dump(bot, update):
    update.message.reply_text("{}\n{}".format(bot, update))


def get_call_result(command):
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    out = p.stdout.read()
    if len(out) == 0:
        return 'empty output'
    else:
        return out.decode('utf-8')


@command('shell')
@check_role('admin')
@replyerrors
def shell(bot, update):
    command = update.message.text.split(' ', 1)[1]
    update.message.reply_text(get_call_result(command), quote=True)


@command('free')
@check_role('user')
def free(bot, update):
    update.message.reply_text(get_call_result('free -m'), quote=True)


@command('deploy')
@owner('ssmike')
def deploy(bot, update):
    with_session(broadcast_chats)(lambda _, chat: bot.send_message(chat, 'deploying new version'), 'announces')
    for command in [['git', 'checkout', '-f'],
                    ['git', 'pull'],
                    ['pip', 'install', '-r', 'requirements.txt']]:
        log.info("%s", command)
        subprocess.check_call(command)
    log.info("%s", ['python', 'bot.py'])
    os.execlp('python', 'python', 'bot.py')


@command('watch')
@check_role('watcher')
@with_session
def toggle_logging(session, bot, update):
    chat_id = update.message.chat.id
    tokens = update.message.text.split(' ', 2)
    action = tokens[1]
    filters_ = tokens[2:]
    if action == 'add':
        for filter_ in filters_:
            session.add(Watch(filter=filter_, chat_id=chat_id))
    elif action == 'rm':
        session.query(Watch)\
                .filter(Watch.chat_id == chat_id)\
                .filter(Watch.filter.in_(filters_))\
                .delete(synchronize_session='fetch')


@command('new_role')
@check_role('admin')
@with_session
def add_role(session, bot, update):
    role = update.message.text.split(' ', 1)[1]
    session.add(Role(name=role))


@command('acl_init')
@owner('ssmike')
@replyerrors
@with_session
def clr_acl(session, bot, update):
    watch_role = Role(name='watcher')
    admin_role = Role(name='admin')
    user_role = Role(name='user')
    user = User(name='ssmike', id=update.message.from_user.id, roles=[admin_role, watch_role, user_role])
    session.add_all([user_role, admin_role, watch_role, user])


@command('drop')
@check_role('admin')
@replyerrors
def drop_tables(bot, update):
    tables = update.message.text.split(' ')[1:]
    with_session(broadcast_chats)(lambda _, chat: bot.send_message(chat, 'dropping {}'.format(tables)), 'announces')
    drop(tables)


@command('start')
@with_session
def add_user(session, bot, update):
    user = update.message.from_user
    session.add(User(name=user.username, id=user.id))
    session.add(Watch(filter='announces', chat_id=update.message.chat))


def parse_role_users(text):
    names, role_names = [], []
    for token in text.split(' ')[1:]:
        if token.startswith('@'):
            names.append(token[1:])
        else:
            role_names.append(token)
    return names, role_names


@command('acl_add')
@check_role('admin')
@replyerrors
@with_session
def add_roles(session, bot, update):
    text = update.message.text
    names, role_names = parse_role_users(text)
    for user, role in session.query(User, Role) \
                             .filter(Role.name.in_(role_names)) \
                             .filter(User.name.in_(names)).all():
        user.roles.append(role)


@command('acl_rm')
@check_role('admin')
@replyerrors
@with_session
def del_roles(session, bot, update):
    text = update.message.text
    names, role_names = parse_role_users(text)
    for user, role in session.query(User, Role) \
                             .filter(Role.name.in_(role_names)) \
                             .filter(User.name.in_(names)).all():
        user.roles.remove(role)


@command('acl_list')
@check_role('admin')
@with_session
def list_users(session, bot, update):
    name = update.message.text.split(' ')[1]
    role = session.query(Role).filter(Role.name == name).one()
    result = []
    for user in role.users:
        result.append(user.name)
    if len(result) != 0:
        update.message.reply_text("\n".join(result), quote=True)


def gen_fname():
    os.makedirs('downloads', exist_ok=True)
    return os.path.join('downloads', uuid.uuid4().hex)


def download(url):
    with requests.get(url, verify=False, stream=True) as resp:
        fname = gen_fname()
        with open(fname, 'wb') as fout:
            shutil.copyfileobj(resp.raw, fout)
        return fname


@command('bookmark')
@check_role('user')
@with_session
def add_url(session, bot, update):
    alias, url = update.message.text.split(' ', 2)[1:]
    user = session.query(User).filter(User.id == update.message.from_user.id).one()
    session.add(Bookmark(shortname=alias, url=url, user=user))


@command('bdelete')
@check_role('user')
@with_session
def rm_url(session, bot, update):
    urls = update.message.text.split(' ')[1:]
    session.query(Bookmark)\
           .filter(Bookmark.user_id == update.message.from_user.id)\
           .filter(Bookmark.shortname.in_(urls))\
           .delete(synchronize_session='fetch')


@command('fetch')
@check_role('user')
@run_async
@replyerrors
def send_doc(bot, update):
    args = update.message.text.split(' ', 3)
    user_id = update.message.from_user.id
    fname = None
    with make_session() as session:
        user = session.query(User).filter(User.id == update.message.from_user.id).one()
        if len(args) < 2:
            resp = "\n".join("%s: %s" % (b.shortname, b.url) for b in user.bookmarks)
            update.message.reply_text(resp, quote=True)
        else:
            explicit_sleep = None
            if len(args) >= 3:
                explicit_sleep = int(args[1])
            url = session.query(Bookmark)\
                         .filter(Bookmark.user_id == user_id)\
                         .filter(Bookmark.shortname == args[-1])\
                         .one().url
            fname = gen_fname()

    if fname:
        make_screenshot(url, fname, explicit_sleep)
        with open(fname, 'rb') as fin:
            update.message.reply_document(fin, quote=True)
        os.remove(fname)


def notifier(kw):
    with make_session() as s:
        for filter, message in kw:
            broadcast_chats(s, lambda _, id: updater.bot.send_message(id, message), filter)


updater.start_polling()
watchers.run(notifier, os.getenv('PERIODIC_SLEEP', 60))
updater.idle()
