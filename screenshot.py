from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')
options.add_argument('--window-size=1920,1080')


def make_screenshot(url, fname):
    browser = Chrome(chrome_options=options)
    browser.get(url)
    browser.save_screenshot(fname)
    browser.close()


if __name__ == '__main__':
    make_screenshot('https://github.com', 'screenshot.png')
