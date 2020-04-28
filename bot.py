from telegram.ext import run_async
import os
import requests
import subprocess
import logging
import shutil
import uuid
from base import Bookmark, Watch, Role, User, drop, make_session, with_session
from screenshot import make_screenshot
import watchers
from tgutil import updater, broadcast_chats, TgHandler, command, guard, retry, replyerrors, check_role, owner
import acl

log = logging.getLogger(__name__)
logging.getLogger().addHandler(TgHandler(logging.INFO))


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
@run_async
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
    if len(tokens) < 2:
        return
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
    elif action == 'list':
        update.message.reply_text('\n'.join(watch.filter for watch in session.query(Watch).filter(Watch.chat_id == chat_id)))


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
    cmd, data = update.message.text.split(' ', 2)[1:]
    if cmd == 'add':
        alias, url = data.split(' ', 1)
        user = session.query(User).filter(User.id == update.message.from_user.id).one()
        session.add(Bookmark(shortname=alias, url=url, user=user))
    elif cmd == 'rm':
        urls = data.split(' ')
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
        for filter, message in kw.items():
            broadcast_chats(s, lambda _, id: updater.bot.send_message(id, message), filter)


updater.start_polling()
watchers.run(notifier, int(os.getenv('PERIODIC_SLEEP', 60)))

log.info("started")
updater.idle()
