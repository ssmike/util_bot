from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')
options.add_argument('--window-size=1366,768')


def make_screenshot(url, fname):
    browser = Chrome(chrome_options=options)
    browser.get(url)
    browser.save_screenshot(fname)


if __name__ == '__main__':
    make_screenshot('https://github.com', 'screenshot.png')
