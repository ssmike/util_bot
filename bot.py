from telegram.ext import run_async
import os
import subprocess
import logging
from base import Watch, User, drop, make_session, with_session
import watchers

from tgutil import broadcast_chats, command, replyerrors, check_role, owner, get_updater, configure_logging

import torrent  # noqa
import fetch  # noqa
import acl # noqa
import bc # noqa

log = logging.getLogger(__name__)
configure_logging()


@command('ping')
def ping(update, context):
    update.message.reply_text('pong')


@command('dump')
@owner('ssmike')
def dump(update, context):
    update.message.reply_text("{}\n{}".format(update, context))


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
def shell(update, context):
    command = update.message.text.split(' ', 1)[1]
    update.message.reply_text(get_call_result(command), quote=True)


@command('free')
@check_role('user')
def free(update, context):
    update.message.reply_text(get_call_result('free -m'), quote=True)


@command('deploy')
@owner('ssmike')
def deploy(update, context):
    for cmd in [['git', 'checkout', '-f'],
                ['git', 'pull'],
                ['pip', 'install', '-r', 'requirements.txt']]:
        log.info("%s", cmd)
        subprocess.check_call(cmd)
    log.info("%s", ['python', 'bot.py'])
    os.execlp('python', 'python', 'bot.py')


@command('watch')
@check_role('watcher')
@with_session
def toggle_logging(session, update, context):
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
def drop_tables(update, context):
    tables = update.message.text.split(' ')[1:]
    with_session(broadcast_chats)(lambda chat: context.bot.send_message(chat, 'dropping {}'.format(tables)), 'announces')
    drop(tables)


@command('start')
@with_session
def add_user(session, update, context):
    user = update.message.from_user
    session.add(User(name=user.username, id=user.id))
    session.add(Watch(filter='announces', chat_id=update.message.chat.id))


def notifier(kw):
    with make_session() as s:
        for filter, message in kw.items():
            broadcast_chats(s, lambda chat: get_updater().bot.send_message(chat, message), filter)


get_updater().start_polling()
watchers.run(notifier, int(os.getenv('PERIODIC_SLEEP', 60)))

log.info("started")
get_updater().idle()
