from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ChromeOptions
from pyquery import PyQuery as pq
import requests
import asyncio
import aiohttp
import logging
import os, sys
from optparse import OptionParser

parser = OptionParser(usage='"usage:%prog [options] arg1,arg2"', version="%prog 0.1")
parser.add_option('-f', '--file', dest='FILE', help='absolute path of upload file, required')
parser.add_option('-o', '--outdir', dest='OUT_DIR', help='output dir, required')
parser.add_option('-a', '--abbreviate', dest='ORG', default='hsa', help='STR, Organism Abbreviate, default: %default')
parser.add_option('-d', '--default', dest='DEFAULT', default='pink', help='STR, default color, default: %default')
parser.add_option('-c', '--concurrency', dest='CONCURRENCY', default='6', help='INT, concurrency number, default: %default', type='int')
parser.add_option('-p', '--proxy', dest='PROXY', default=False, action='store_true', help='BOOL, Use Proxy Pool or not(caution: Proxy from Proxy Pool is NOT stable), default: %default')
opts, args = parser.parse_args()

if not opts.FILE or not opts.OUT_DIR:
    parser.print_help()
    sys.exit()

BASE_URL = 'https://www.kegg.jp'
START_URL = BASE_URL + '/kegg/tool/map_pathway2.html'

SET_ORG_JS = "document.getElementById('s_map').value='" + opts.ORG + "';"
SET_DEFAULT_COLOR = "document.getElementsByName('default')[0].value='" + opts.DEFAULT + "';"

PROXY_POOL_URL = 'http://localhost:5555/random'

semaphore = asyncio.Semaphore(opts.CONCURRENCY)

if not os.path.exists(opts.OUT_DIR):
    os.makedirs(opts.OUT_DIR)

async def get_content(link):
    async with aiohttp.ClientSession() as session:
        response = await session.get(link, timeout=None)
        content = await response.read()
        return content

async def download_image(imgFile, imgLink):
    async with semaphore:
        try:
            content = await get_content_proxy(imgLink)
            logging.info('scraping %s', imgLink)
            with open(imgFile, 'wb') as f:
                f.write(content)
        except aiohttp.ClientError:
            logging.error('error occurred while scraping %s', imgLink, exc_info=True)

async def get_content_proxy(link, proxy=None):
    async with aiohttp.ClientSession() as session:
        response = await session.get(link, timeout=None, proxy=proxy)
        content = await response.read()
        return content

async def download_image_proxy(imgFile, imgLink, proxy=None):
    async with semaphore:
        try:
            content = await get_content_proxy(imgLink, proxy)
            logging.info('scraping %s', imgLink)
            with open(imgFile, 'wb') as f:
                f.write(content)
        except aiohttp.ClientError:
            logging.error('error occurred while scraping %s', imgLink, exc_info=True)

def get_proxy():
    try:
        response = requests.get(PROXY_POOL_URL)
        if response.status_code == 200:
            return response.text
    except ConnectionError:
        return None

option = ChromeOptions()
option.add_argument('--headless')
option.add_argument('--ignore-certificate-errors')
option.add_argument('--ignore-ssl-errors')
browser = webdriver.Chrome(options=option)
browser.get(START_URL)
browser.execute_script(SET_ORG_JS)
browser.execute_script(SET_DEFAULT_COLOR)
browser.find_element(By.NAME, "color_list").send_keys(opts.FILE)
button = browser.find_element(By.XPATH, "//*[@id=\"main\"]/form/input[5]")
button.click()

if opts.PROXY:
    tasks = [asyncio.ensure_future(download_image_proxy(opts.OUT_DIR + '/' + str(pq(str(li.get_attribute('href')))('#pathwayimage').attr('src')).split('/')[-1], BASE_URL + str(pq(str(li.get_attribute('href')))('#pathwayimage').attr('src')), 'http://' + get_proxy())) for li in browser.find_elements(By.XPATH, "/html/body/div[2]/ul/pre/li/a[1]")]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
else:
    tasks = [asyncio.ensure_future(download_image(opts.OUT_DIR + '/' + str(pq(str(li.get_attribute('href')))('#pathwayimage').attr('src')).split('/')[-1], BASE_URL + str(pq(str(li.get_attribute('href')))('#pathwayimage').attr('src')))) for li in browser.find_elements(By.XPATH, "/html/body/div[2]/ul/pre/li/a[1]")]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))


