# 📆 instagram_crawler.py - 1000개 게시물만, 본문·이미지·추가 정보 추출
# (넉넉한 랜덤 sleep + 자동화 탐지 우회 강화)

import os
import time
import re
import pickle
import csv
import random
import traceback
import sys

from pathlib import Path

# Use explicit project directory for cookie storage
PROJECT_DIR = Path("/Users/hb/Desktop/PROJECT")
COOKIE_PATH = os.getenv("COOKIE_PATH", PROJECT_DIR / "cookies.pkl")

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchWindowException, NoSuchElementException
import requests

def load_instagram_cookies(driver, path=COOKIE_PATH):
    if os.path.exists(path):
        # Ensure on base domain before adding cookies
        driver.get("https://www.instagram.com")
        rand_sleep(2, 4)
        try:
            with open(path, "rb") as f:
                cookies = pickle.load(f)
        except Exception as e:
            print(f"⚠️ 쿠키 로드 실패: {e}")
            return False
        for ck in cookies:
            safe = {
                "name": ck.get("name"), "value": ck.get("value"),
                "domain":   ck["domain"],
                "path": ck.get("path", "/"), "expiry": ck.get("expiry"),
                "secure": ck.get("secure", False),
                "httpOnly": ck.get("httpOnly", False),
                "sameSite": ck.get("sameSite")
            }
            try:
                driver.add_cookie(safe)
            except:
                pass
        print("✅ 쿠키 로드 완료")
        driver.refresh()
        rand_sleep(5, 8)
        return True
    return False

# ✅ 환경 변수 로드
load_dotenv()
INSTAGRAM_ID       = os.getenv("INSTAGRAM_ID")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
USER_AGENT         = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
)
# 여러 계정 지정 시 .env: INSTAGRAM_ACCOUNTS=hongdaeff,another_user
ACCOUNTS = [acct.strip() for acct in os.getenv("INSTAGRAM_ACCOUNTS", "ccyc.live").split(",")]

CHROMEDRIVER_PATH = "/opt/homebrew/bin/chromedriver"
BASE_IMG_DIR      = "images"
MAX_POSTS         = 500
SCROLL_PAUSE_MIN  = 6.0
SCROLL_PAUSE_MAX  = 9.0

# 🔍 정규표현식 패턴
default_patterns = {
    "date":  [r"(\d{4}[./-]\d{2}[./-]\d{2})", r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일"],
    "time":  [r"\d{1,2}[:시]\d{2}", r"\d{1,2}시"],
    "price": [r"([\d,]+)(?=\s*(?:원|[Ww]|KRW))"],
    "place": [r"📍\s*(.+)", r"(서울.*구.*)"]
}
account_patterns = {
    "hongdaeff": {
        "date":  [r"(\d{4}/\d{2}/\d{2})", r"(\d{1,2}/\d{1,2})"],
        "time":  [r"(\d{1,2}[:.]\d{2})", r"(\d{1,2}PM|\d{1,2}AM)"],
        "price": [
            r"([\d,]+)(?=\s*(?:원|[Ww]|KRW))",
            r"(Cover\s*[:\-]?\s*\d{1,3},?\d{3})",
            r"(₩\d{1,3},?\d{3})"
        ],
        "place": [r"(서울시\s?[^\n\r]+)", r"@hongdaeff"]
    }
}

def convert_time(s):
    if not s:
        return ""
    s = s.strip()
    # 'YYYY.M.D HH:MM:SS AM/PM'
    m_ts = re.match(r'^\d{4}\.\d{1,2}\.\d{1,2}\s+(\d{1,2}):(\d{2}):\d{2}\s*(AM|PM)$', s, re.IGNORECASE)
    if m_ts:
        h, mi, ampm = int(m_ts.group(1)), int(m_ts.group(2)), m_ts.group(3).upper()
        if ampm == 'PM' and h != 12: h += 12
        if ampm == 'AM' and h == 12: h = 0
        return f"{h:02d}:{mi:02d}"
    # 'HH:MM'
    m = re.match(r'^(\d{1,2}):(\d{2})$', s)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    # 'X시 Y분' or 'X시Y분'
    m_kr = re.match(r'^(\d{1,2})시\s*(\d{1,2})분$', s)
    if m_kr:
        return f"{int(m_kr.group(1)):02d}:{int(m_kr.group(2)):02d}"
    # 'X시MM'
    m4 = re.match(r'^(\d{1,2})시\s*(\d{1,2})$', s)
    if m4:
        return f"{int(m4.group(1)):02d}:{int(m4.group(2)):02d}"
    # 'X시'
    m3 = re.match(r'^(\d{1,2})시$', s)
    if m3:
        return f"{int(m3.group(1)):02d}:00"
    return ""

def multi_search(patterns, text):
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return (m.group(1) if m.lastindex else m.group(0)).strip()
    return ""

def rand_sleep(a, b):
    time.sleep(random.uniform(a, b))

def smooth_scroll(driver):
    driver.execute_script("window.scrollBy(0, 400);")
    rand_sleep(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX)

# 🚀 WebDriver 시작 및 자동화 탐지 우회 설정
options = webdriver.ChromeOptions()
options.add_argument(f"--user-agent={USER_AGENT}")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

service = Service(CHROMEDRIVER_PATH)
driver  = webdriver.Chrome(service=service, options=options)
wait    = WebDriverWait(driver, 25)

# navigator.webdriver 속성 감추기
driver.execute_cdp_cmd(
    "Page.addScriptToEvaluateOnNewDocument",
    {"source": """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """}
)


# 🔐 쿠키 로그인 우선
driver.get("https://www.instagram.com")
rand_sleep(8, 12)
if not load_instagram_cookies(driver):
    print("🔐 쿠키 없음 또는 유효하지 않음. 수동 로그인 후 Enter:")
    input()
    with open(COOKIE_PATH, "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    print("✅ 쿠키 저장 완료")
rand_sleep(8, 12)

try:
    # 🔄 계정별 크롤링
    for account in ACCOUNTS:
        csv_file = f"{account}_full.csv"
        existing_links = []
        existing_results = []
        if os.path.exists(csv_file):
            with open(csv_file, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_links.append(row["link"])
                    existing_results.append(row)
            print(f"🔄 기존에 저장된 게시물 {len(existing_links)}개 로드")
        else:
            existing_links = []
            existing_results = []

        print(f"\n=== Crawling @{account} ===")
        img_dir = os.path.join(BASE_IMG_DIR, account)
        os.makedirs(img_dir, exist_ok=True)

        # ▶ 프로필 페이지 로드 & 대기
        driver.get(f"https://www.instagram.com/{account}/")
        rand_sleep(7, 10)

        # ▶ 게시물 링크 수집 (최대 1000개)
        all_links = []
        prev_count = 0
        attempts = 0
        while len(all_links) < MAX_POSTS:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            rand_sleep(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX)

            anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/p/']")
            for a in anchors:
                href = a.get_attribute("href")
                if href and href not in all_links:
                    all_links.append(href)
                    if len(all_links) >= MAX_POSTS:
                        break

            new_count = len(all_links)
            if new_count == prev_count:
                attempts += 1
                if attempts >= 3:
                    break
            else:
                attempts = 0
                prev_count = new_count
            print(f"🔄 스크롤 진행 중: {len(all_links)}/{MAX_POSTS} 링크 수집")

        print(f"🔍 총 {len(all_links)}개 게시물 링크 수집")

        if existing_links:
            if existing_links[-1] in all_links:
                last_index = all_links.index(existing_links[-1])
                new_links = all_links[last_index + 1:]
            else:
                new_links = all_links
        else:
            new_links = all_links
        print(f"🔍 새로 크롤링할 링크 {len(new_links)}개")

        # ▶ 게시물 열어서 정보 추출
        results = existing_results.copy()
        start_idx = len(existing_results) + 1
        for offset, link in enumerate(new_links):
            idx = start_idx + offset
            print(f"  {idx}. Opening: {link}")
            try:
                driver.get(link)
                rand_sleep(7, 10)

                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article header")))
                rand_sleep(7, 10)

                try:
                    content = driver.find_element(By.CSS_SELECTOR, "article header h1").text
                except NoSuchElementException:
                    try:
                        content = driver.find_element(By.TAG_NAME, "h1").text
                    except NoSuchElementException:
                        content = driver.find_element(By.TAG_NAME, "span").text

                # 3) 정규표현식 정보 추출
                patterns   = account_patterns.get(account, default_patterns)
                place      = multi_search(patterns["place"],  content)
                date       = multi_search(patterns["date"],   content)
                raw_time  = multi_search(patterns["time"],   content)
                time_info = convert_time(raw_time)
                # 가격 정보 추출 초기화
                in_adv = ""
                cover = ""
                # 통합 정규표현식: 사전예매/현장예매 구분 및 단위(만원/원) 처리
                price_pattern = re.compile(
                    r"(사전예매)\s*([\d\.]+)만원"
                    r"|(?:현장예매|현매)\s*([\d\.]+)만원"
                    r"|([\d\.]+)만원"
                    r"|([\d,]+)(?=\s*(?:원|[Ww]|KRW))",
                    flags=re.IGNORECASE
                )
                matches = price_pattern.findall(content)
                for grp1, grp2, grp3, grp4, grp5, grp6 in matches:
                    if grp1:  # 사전예매 x만원
                        value = float(grp2)
                        in_adv = str(int(value * 10000))
                    elif grp3:  # 현장예매/현매 x만원
                        value = float(grp4)
                        cover = str(int(value * 10000))
                    elif grp3 == "" and grp1 == "" and grp5:  # 접두어 없는 x만원
                        value = float(grp5)
                        if not cover:
                            cover = str(int(value * 10000))
                    elif grp6:  # 원 단위 (comma 포함)
                        raw = grp6.replace(",", "")
                        if not in_adv:
                            in_adv = raw
                        elif not cover:
                            cover = raw
                # '무료'가 포함된 경우 cover를 0으로 설정
                if "무료" in content:
                    cover = "0"

                # 4) 결과 저장
                results.append({
                    "link":    link,
                    "content": content,
                    "place":   place,
                    "date":    date,
                    "time":    time_info,
                    "in advance": in_adv,
                    "cover":      cover
                })

            except TimeoutException:
                print("    ⚠️ 요소 로딩 타임아웃")
            except NoSuchWindowException:
                print("⚠️ 브라우저가 닫혔습니다. 종료합니다.")
                break
            except Exception as e:
                print(f"    ❗ 처리 중 오류: {e}\n{traceback.format_exc()}")
            finally:
                rand_sleep(7, 10)

        # 💾 CSV 저장
        with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["link","content","place","date","time","in advance","cover"]
            )
            writer.writeheader()
            writer.writerows(results)
        print(f"✅ 결과 저장: {csv_file}")

except KeyboardInterrupt:
    print("\n🔔 크롤링 중단 신호 감지: 현재까지 수집된 데이터를 저장합니다.")
    # 파이썬 스크립트가 멈춘 계정의 CSV 파일에 부분 저장
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["link","content","place","date","time","in advance","cover"]
        )
        writer.writeheader()
        writer.writerows(results)
    print(f"✅ 중간 결과 저장: {csv_file}")
    driver.quit()
    sys.exit(0)

except Exception as e:
    print("\n❗ 예기치 않은 오류 발생! 현재까지 수집된 데이터를 저장합니다.")
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["link","content","place","date","time","in advance","cover"]
        )
        writer.writeheader()
        writer.writerows(results)
    print(f"✅ 중간 결과 저장: {csv_file}")
    driver.quit()
    sys.exit(1)

# 🛑 종료
driver.quit()