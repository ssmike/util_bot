from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')


def make_screenshot(url, fname):
    browser = Chrome(chrome_options=options)
    browser.get(url)
    browser.save_screenshot(fname)
