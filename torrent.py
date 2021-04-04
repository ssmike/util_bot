import logging
import transmission_rpc as torrent
import json
import os

from tgutil import command, replyerrors
from acl import check_role


_log = logging.getLogger(__name__)

try:
    print(os.getenv('TRANSMISSION_CONF'))

    _client = torrent.Client(**json.loads(os.getenv('TRANSMISSION_CONF')))
    _timeout = int(os.getenv('TRANSMISSION_RPC_TIMEOUT', 10))
    _dir = os.getenv('TRANSMISSION_DOWNLOAD_DIR')
except Exception as e:
    _log.exception(e)


@command('download_to')
@check_role('user')
def set_target(bot, update):
    global _dir
    _dir = update.message.text.split(' ', 1)[1]


@command('torrent')
@check_role('user')
@replyerrors
def add_torrent(bot, update):
    assert update.message.text.startswith('/torrent')
    url = update.message.text.split(' ', 1)[1]
    target = _dir
    _client.add_torrent(torrent=url, timeout=_timeout, download_dir=target)
    update.message.reply_text('downloading to %s' % (target,))
