from threading import Thread
import time
import os
import psutil
from getpass import getuser as currentuser
import logging

watchers = []


def add_watcher(func):
    watchers.append(func)
    return func


def bind(*args, **kwargs):
    def decorator(func):
        def result():
            return func(*args, **kwargs)
        return result
    return decorator


def bind_generator(*args, **kwargs):
    def decorator(func):
        return iter(func(*args, **kwargs)).__next__
    return decorator


def check_temp(tag, crit):
    _base = '/sys/class/thermal/'
    found_temps = []
    for _file in os.listdir(_base):
        if _file.startswith('thermal_zone'):
            num = int(open('/sys/class/thermal/%s/temp' % (_file,)).read()) / 1000
            if num > crit:
                found_temps.append((num, (tag, "%s %.1f'C" % (_file, num,))))
    if found_temps:
        return max(found_temps)[1]


add_watcher(bind('alerts', 74)(check_temp))
add_watcher(bind('temp', 0)(check_temp))


@add_watcher
def check_memory():
    mem = psutil.virtual_memory()
    av = mem.available / 2 ** 30
    total = mem.total / 2 ** 30

    if total > av * 20:
        return 'alerts', 'critical memory usage {:.2f}/{:.2f}'.format(total - av, total)


@add_watcher
@bind_generator()
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


def run(broadcaster, sleep=1):
    def target():
        while True:
            result = {}
            for w in watchers:
                try:
                    res = w()
                    if res:
                        result.__setitem__(*res)
                except Exception as e:
                    logging.getLogger(__name__).exception(e)

            broadcaster(result)
            time.sleep(sleep)

    Thread(target=target()).start()
