from telegram.ext import Updater, CommandHandler
import os
import requests
import subprocess
import logging
from base import Session, Role, User, drop_all

updater = Updater(os.environ['TELEGRAM_TOKEN'])
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


class TgHandler(logging.Handler):
    def __init__(self, chats, level):
        self.chats = chats
        logging.Handler.__init__(self, level)

    def emit(self, entry):
        # avoid hitting telegram limits
        message = self.format(entry)[-4096:]
        for chat in enabled_logging:
            try:
                updater.bot.send_message(chat, message)
            except Exception as e:
                "to avoid loops"
                print(str(e))


enabled_logging = set()
logging.getLogger().addHandler(TgHandler(enabled_logging, logging.INFO))


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


def owner(user):
    def pred(update):
        return update.message.chat.type == 'private' and \
               update.message.from_user.username == user
    return guard(pred, "only {} has access to this handler".format(user))


def owners(users):
    def pred(update):
        return update.message.chat.type == 'private' and \
               update.message.from_user.username in users
    return guard(pred, "only {} have access to this handler".format(", ".join(users)))


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
    for command in [['pip', 'install', '-r', 'requirements.txt'],
                    ['git', 'checkout', '-f'],
                    ['git', 'pull']]:
        log.info("%s", command)
        subprocess.check_call(command)
    log.info("%s", ['python', 'bot.py'])
    os.execlp('python', 'python', 'bot.py')


@command('yasm')
@check_role('user')
@replyerrors
@retry(3)
def snapshot(bot, update):
    panels = {
        'indexer': 'https://s.yasm.yandex-team.ru/panel/ssmike._GpjE3A/?range=86400000',
        'cluster': 'https://s.yasm.yandex-team.ru/panel/ssmike._lKsvaf/',
        'replicator': 'https://s.yasm.yandex-team.ru/panel/ssmike._mSIC52',
        'knocker': 'https://s.yasm.yandex-team.ru/panel/ssmike._MDyCJy',
    }
    panel = update.message.text.split(' ', 1)
    if len(panel) == 1:
        update.message.reply_text('available panels: ' +
                                  ' '.join(panels.keys()), quote=True)
        return
    panel = panel[1]

    if panel not in panels:
        update.message.reply_text('invalid panel')
    else:
        with requests.get(panels[panel], verify=False, stream=True) as resp:
            update.message.reply_photo(photo=resp.raw, quote=True)


@command('log')
@check_role('admin')
def toggle_logging(bot, update):
    global enabled_logging
    chat_id = update.message.chat.id
    action = update.message.text.split(' ', 1)[1]
    if action == 'enable':
        enabled_logging.add(chat_id)
    elif action == 'disable':
        if chat_id in enabled_logging:
            enabled_logging.remove(chat_id)


@command('acl_init')
@owner('ssmike')
@replyerrors
def clr_acl(bot, update):
    admin_role = Role(name='admin')
    user_role = Role(name='user')
    user = User(name='ssmike', id=update.message.from_user.id, roles=[admin_role, user_role])

    session = Session()
    session.add_all([user_role, admin_role, user])
    session.commit()


@command('acl_clear')
@owner('ssmike')
@replyerrors
def ctl_clr(bot, update):
    drop_all()


@command('add_role')
@check_role('admin')
def add_role(bot, update):
    name = update.message.text.split(' ')[1]

    session = Session()
    session.add(Role(name=name))
    session.commit()


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
def list_users(bot, update):
    name = update.message.text.split(' ')[1]
    session = Session()
    role = session.query(Role).filter(Role.name == name).one()
    result = []
    for user in role.users:
        result.append(user.name)
    if len(result) != 0:
        update.message.reply_text("\n".join(result), quote=True)


updater.start_polling()
updater.idle()
