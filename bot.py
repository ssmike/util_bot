from telegram.ext import Updater, CommandHandler, run_async
import os
import requests
import subprocess
import logging
import shutil
import uuid
from base import Bookmark, Watch, Role, User, Session, drop
from screenshot import make_screenshot

updater = Updater(os.environ['TELEGRAM_TOKEN'], workers=8)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


def broadcast_chats(func, *filters):
    session = Session()
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
        broadcast_chats(send, 'log')


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
    def check(update):
        user = Session().query(User).filter(User.id==update.message.from_user.id).one()
        for role in user.roles:
            if role.name == role_name:
                return True
        return False
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
    for command in [['git', 'checkout', '-f'],
                    ['git', 'pull'],
                    ['pip', 'install', '-r', 'requirements.txt']]:
        log.info("%s", command)
        subprocess.check_call(command)
    log.info("%s", ['python', 'bot.py'])
    os.execlp('python', 'python', 'bot.py')


@command('watch')
@check_role('watcher')
def toggle_logging(bot, update):
    session = Session()
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
    session.commit()


@command('new_role')
@check_role('admin')
def add_role(bot, update):
    role = update.message.text.split(' ', 1)[1]
    session = Session()
    session.add(Role(name=role))
    session.commit()


@command('acl_init')
@owner('ssmike')
@replyerrors
def clr_acl(bot, update):
    watch_role = Role(name='watcher')
    admin_role = Role(name='admin')
    user_role = Role(name='user')
    user = User(name='ssmike', id=update.message.from_user.id, roles=[admin_role, watch_role, user_role])

    session = Session()
    session.add_all([user_role, admin_role, watch_role, user])
    session.commit()


@command('drop')
@check_role('admin')
@replyerrors
def drop_tables(bot, update):
    drop(update.message.text.split(' ')[1:])


@command('start')
def add_user(bot, update):
    try:
        user = update.message.from_user
        session = Session()
        session.add(User(name=user.username, id=user.id))
        session.commit()
    except Exception:
        return


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
def add_roles(bot, update):
    session = Session()
    text = update.message.text
    names, role_names = parse_role_users(text)
    for user, role in session.query(User, Role) \
                             .filter(Role.name.in_(role_names)) \
                             .filter(User.name.in_(names)).all():
        user.roles.append(role)
    session.commit()


@command('acl_rm')
@check_role('admin')
@replyerrors
def del_roles(bot, update):
    session = Session()
    text = update.message.text
    names, role_names = parse_role_users(text)
    for user, role in session.query(User, Role) \
                             .filter(Role.name.in_(role_names)) \
                             .filter(User.name.in_(names)).all():
        user.roles.remove(role)
    session.commit()


@command('acl_list')
@check_role('admin')
def list_users(bot, update):
    name = update.message.text.split(' ')[1]
    session = Session()
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


@command('share')
@check_role('user')
@replyerrors
def share(bot, update):
    url = update.message.text.split(' ')[1]
    fname = download(url, dir)
    update.message.reply_text(get_call_result('sky share {}'.format(fname), quote=True))


@command('bookmark')
@check_role('user')
def add_url(bot, update):
    alias, url = update.message.text.split(' ', 2)[1:]
    session = Session()
    user = session.query(User).filter(User.id == update.message.from_user.id).one()
    session.add(Bookmark(shortname=alias, url=url, user=user))
    session.commit()


@command('bdelete')
@check_role('user')
def rm_url(bot, update):
    urls = update.message.text.split(' ')[1:]
    session = Session()
    session.query(Bookmark)\
           .filter(Bookmark.user_id == update.message.from_user.id)\
           .filter(Bookmark.shortname.in_(urls))\
           .delete(synchronize_session='fetch')
    session.commit()


@command('fetch')
@check_role('user')
@run_async
@replyerrors
def send_doc(bot, update):
    args = update.message.text.split(' ', 3)
    user_id = update.message.from_user.id
    session = Session()
    user = session.query(User).filter(User.id == update.message.from_user.id)
    if len(args) < 2:
        resp = "\n".join("%s: %s" % (b.shortname, b.url) for b in user.bookmarks)
        update.message.reply_text(resp, quote=True)
    else:
        explicit_sleep = None
        if len(args) >= 3:
            explicit_sleep = int(args[1])
        url = session.query(Bookmark)\
                .filter(Bookmark.user_id == user_id)\
                .filter(Bookmark.shortname == args[-1]).one().url
        fname = gen_fname()
        make_screenshot(url, fname, explicit_sleep)
        with open(fname, 'rb') as fin:
            update.message.reply_document(fin, quote=True)
        os.remove(fname)


updater.start_polling()
updater.idle()
