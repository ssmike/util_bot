import logging
import transmission_rpc as torrent
import json
import os
import base64

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from tgutil import command, callback, replyerrors, check_role, check_user_for_role


_log = logging.getLogger(__name__)

try:
    _client = torrent.Client(**json.loads(os.getenv('TRANSMISSION_CONF')))
    _timeout = int(os.getenv('TRANSMISSION_RPC_TIMEOUT', 10))
except Exception as e:
    _log.exception(e)


def _callback_data(loc):
    return 'torrent ' + loc


def _parse_callback_data(_str):
    return _str[len('torrent '):]


@callback('^torrent')
def torrent_callback(bot, update):
    assert check_user_for_role('user', update.callback_query.from_user.id)

    start_message = update.callback_query.message.reply_to_message
    target = _parse_callback_data(update.callback_query.data)
    url = start_message.text.split(' ', 1)[1]

    _client.add_torrent(torrent=url, timeout=_timeout, download_dir=target)
    start_message.reply_text('downloading to %s' % (target,), quote=True)


@command('torrent')
@check_role('user')
@replyerrors
def add_torrent(bot, update):
    assert update.message.text.startswith('/torrent')
    segments = update.message.text.split(' ')
    assert len(segments) in {2, 3}, 'usage: url [dir]'
    if len(segments) == 3:
        url, _dir = segments[1:]
        _client.add_torrent(torrent=url, timeout=_timeout, download_dir=_dir)

        update.message.reply_text('downloading to %s' % (_dir,), quote=True)
    else:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_dir, callback_data=_callback_data(_dir))]
                                        for _dir in {torrent.downloadDir for torrent in _client.get_torrents()}],
                                        one_time_keyboard=True)

        update.message.reply_text('pick location', reply_markup=keyboard, quote=True)
