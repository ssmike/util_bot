from telegram.ext import Updater, CommandHandler
import os
import requests
import subprocess
import logging

updater = Updater(os.environ['TELEGRAM_TOKEN'])
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)


class TgHandler(logging.Handler):
    def __init__(self, chat_id):
        logging.Handler.__init__(self, logging.INFO)
        self.chat_id = chat_id

    def emit(self, entry):
        try:
            "avoid hitting telegram limits"
            updater.bot.send_message(self.chat_id, self.format(entry)[-4096:])
        except Exception as e:
            "to awoid loops"
            print(str(e))


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


def guard(predicate):
    def decorator(func):
        def handler(bot, update):
            chat = update.message.chat
            if predicate(chat):
                func(bot, update)
            else:
                log.info('denied access for %s', chat)
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


def owner(user):
    def pred(chat):
        return chat.type == 'private' and chat.username == user
    return guard(pred)


def owners(users):
    def pred(chat):
        return chat.type == 'private' and chat.username in users
    return guard(pred)


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
@owner('ssmike')
@replyerrors
def shell(bot, update):
    command = update.message.text.split(' ', 1)[1]
    update.message.reply_text(get_call_result(command), quote=True)


@command('free')
@owner('ssmike')
def free(bot, update):
    update.message.reply_text(get_call_result('free -m'), quote=True)


@command('deploy')
@owner('ssmike')
def deploy(bot, update):
    for command in [['git', 'checkout', '-f'], ['git', 'pull']]:
        log.info("%s", command)
        subprocess.check_call(command)
    log.info("%s", ['python', 'bot.py'])
    os.execlp('python', 'python', 'bot.py')


@command('yasm')
@owner('ssmike')
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
        update.message.reply_text('available panels: ' + ' '.join(panels.keys()), quote=True)
        return
    panel = panel[1]

    if panel not in panels:
        update.message.reply_text('invalid panel')
    else:
        with requests.get(panels[panel], verify=False, stream=True) as resp:
            update.message.reply_photo(photo=resp.raw, quote=True)


handlers = {}


@command('log')
@owner('ssmike')
def switch_reply_logging(bot, update):
    "I know it is not thread safe"
    global handlers
    chat_id = update.message.chat.id
    if update.message.text.split(' ', 1)[1] == 'enable':
        if chat_id not in handlers:
            handler = TgHandler(chat_id)
            handlers[chat_id] = handler
            logging.getLogger().addHandler(handler)
    else:
        if chat_id in handlers:
            logging.getLogger().removeHandler(handlers[chat_id])
            del handlers[chat_id]


updater.start_polling()
updater.idle()
