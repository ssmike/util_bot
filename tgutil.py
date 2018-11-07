from telegram.ext import Updater, CommandHandler
from base import Watch, Role, User, with_session
import logging
import os

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
