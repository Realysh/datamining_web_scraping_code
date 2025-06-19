from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import time
import os
import pickle

from dotenv import load_dotenv
from pathlib import Path

try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:
    BASE_DIR = Path().resolve()

ENV_PATH = BASE_DIR / ".env_main"
print("ENV_PATH:", ENV_PATH)

load_dotenv(dotenv_path=ENV_PATH, override=True)
INSTAGRAM_ID = os.getenv('INSTAGRAM_ID')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

if not INSTAGRAM_ID or not INSTAGRAM_PASSWORD:
    raise ValueError("❌ INSTAGRAM_ID or INSTAGRAM_PASSWORD not found. Check your .env_main and ENV_PATH.")

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

# Save cookies
with open("cookies_main.pkl", "wb") as f:
    pickle.dump(driver.get_cookies(), f)
print("✅ Cookie saving completed!")

# Load cookies
driver.get("https://www.instagram.com")
time.sleep(3)
with open("cookies_main.pkl", "rb") as f:
    cookies = pickle.load(f)
    for cookie in cookies:
        driver.add_cookie(cookie)
driver.refresh()
time.sleep(5)
print("✅ Cookie load and login test completed!")