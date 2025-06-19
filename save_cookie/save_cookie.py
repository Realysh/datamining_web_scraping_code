# 쿠키 저장 코드 (최초 1회만 실행)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import time
import os
import pickle

from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(dotenv_path=BASE_DIR / ".env_main", override=True)
INSTAGRAM_ID = os.getenv('INSTAGRAM_ID')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

options = webdriver.ChromeOptions()
options.add_argument("user-agent=Mozilla/5.0")
options.add_experimental_option("detach", True)
driver_path = "/opt/homebrew/bin/chromedriver"
service = Service(executable_path=driver_path)
driver = webdriver.Chrome(service=service, options=options)

driver.get('https://www.instagram.com/accounts/login/')
time.sleep(5)
driver.find_element(By.NAME, 'username').send_keys(INSTAGRAM_ID)
driver.find_element(By.NAME, 'password').send_keys(INSTAGRAM_PASSWORD)
driver.find_element(By.NAME, 'password').send_keys(Keys.ENTER)
time.sleep(15)

with open("cookies.pkl_main", "wb") as f:
    pickle.dump(driver.get_cookies(), f)


print("✅ 쿠키 저장 완료!")

# 쿠키 불러와서 로그인 테스트
driver.get("https://www.instagram.com")
time.sleep(3)

with open("cookies_main.pkl", "rb") as f:
    cookies = pickle.load(f)
    for cookie in cookies:
        driver.add_cookie(cookie)

driver.refresh()
time.sleep(5)

print("✅ 쿠키 로드 및 로그인 테스트 완료!")