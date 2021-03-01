from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
import time

options = Options()
options.add_argument('--headless')
options.add_argument('--window-size=1920,3080')


def make_screenshot(url, fname, sleep=None):
    browser = Chrome(chrome_options=options)
    browser.get(url)
    if sleep:
        time.sleep(sleep)
    browser.save_screenshot(fname)
    browser.close()


if __name__ == '__main__':
    make_screenshot('http://github.com', 'screenshot.png')
