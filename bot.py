from telegram.ext import Updater, CommandHandler
from os import environ
import requests
import subprocess

updater = Updater(environ['TELEGRAM_TOKEN'])


def command(command):
    def decorator(func):
        updater.dispatcher.add_handler(CommandHandler(command, func))
    return decorator


def replyerrors(func):
    def result(bot, update):
        try:
            func(bot, update)
        except Exception as e:
            update.message.reply_text('error: ' + str(e), quote=True)
    return result


def guard(predicate):
    def decorator(func):
        def handler(bot, update):
            chat = update.message.chat
            if predicate(chat):
                func(bot, update)
            else:
                print('denied access for', chat)
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
                    print('retrying {}'.format(e))
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
def dump(bot, message):
    print(bot)
    print(message)


@command('shell')
@owner('ssmike')
@replyerrors
def shell(bot, update):
    command = update.message.text.split(' ', 1)[1]
    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    out = p.stdout.read()
    update.message.reply_text(out.decode('utf-8'), quote=True)


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


updater.start_polling()
updater.idle()
