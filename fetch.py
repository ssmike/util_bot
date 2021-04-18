import shutil
import uuid
import os
import requests

from telegram.ext import run_async

from tgutil import command, replyerrors, check_role
from base import Bookmark, User, with_session, make_session

from screenshot import make_screenshot


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
@check_role('fetcher')
@with_session
def add_url(session, update, context):
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
@check_role('fetcher')
@run_async
@replyerrors
def send_doc(update, context):
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
            fname = gen_fname() + ".png"

    if fname:
        make_screenshot(url, fname, explicit_sleep)
        with open(fname, 'rb') as fin:
            update.message.reply_document(fin, quote=True)
        os.remove(fname)


@command('render')
@check_role('fetcher')
@run_async
@replyerrors
def render_doc(update, context):
    args = update.message.text.split(' ')[1:]
    assert len(args) in {1, 2}
    url = args[-1]
    explicit_sleep = None
    if len(args) == 2:
        explicit_sleep = int(args[0])

    fname = gen_fname() + ".png"
    make_screenshot(url, fname, explicit_sleep)
    with open(fname, 'rb') as fin:
        update.message.reply_document(fin, quote=True)
    os.remove(fname)
