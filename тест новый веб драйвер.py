import asyncio
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions

async def main():
    options = ChromiumOptions()
    options.binary_location = '/usr/bin/google-chrome-stable'
    options.add_argument('--headless=new')
    options.add_argument('--start-maximized')
    options.add_argument('--disable-notifications')

    browser = Chrome(options=options)
    tab = await browser.start()
    await tab.go_to('https://github.com/autoscrape-labs/pydoll')
    await asyncio.sleep(5)
    input()
    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())

