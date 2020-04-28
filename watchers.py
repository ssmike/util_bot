from threading import Thread
import time
import psutil
from getpass import getuser as currentuser
import logging
import subprocess


def check_temp(tag, crit):
    def func():
        num = int(open('/sys/class/thermal/thermal_zone0/temp').read()) / 1000
        if num > crit:
            return tag, "acpi temperature %.1f'C" % (num,)


def check_memory():
    mem = psutil.virtual_memory()
    av = mem.available / 2 ** 30
    total = mem.total / 2 ** 30

    if total > av * 20:
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


watchers = [check_memory, iter(check_users()).__next__, check_temp('alerts', 72), check_temp('temp', 0)]


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
