from threading import Thread
import time
import psutil
from getpass import getuser as currentuser
from bot import broadcast_chats, updater
from base import make_session


def check_memory():
    mem = psutil.virtual_memory()
    av = mem.available / 2 ** 30
    total = mem.total / 2 ** 30

    if total > av * 30:
        return 'alerts', 'critical memory usage {:.2f}/{:.2f}'.format(total - av, total)


def check_users():
    def get_list():
        return {user.name for user in psutil.users()}.union({currentuser()})

    last_users = get_list()
    while True:
        users = get_list()

        diff = users.difference(last_users)
        last_users = users

        if diff:
            yield 'logins', 'detected login for ' + ', '.join(diff)
        else:
            yield None


watchers = [check_memory, iter(check_users()).__next__]


def run(sleep=1):
    def target():
        while True:
            result = {}
            for w in watchers:
                res = w()
                if res:
                    result.__additem__(*w)

            with make_session() as s:
                for filter, message in result:
                    broadcast_chats(s, lambda _, id: updater.bot.send_message(id, message), filter)

            time.sleep(sleep)

    Thread(target=target()).start()
