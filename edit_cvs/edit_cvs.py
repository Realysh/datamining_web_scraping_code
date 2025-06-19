import os
import pickle
import pandas as pd
import re
import requests
import random
from bs4 import BeautifulSoup
from time import sleep
import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from time import sleep
file_path = "/Users/hb/Desktop/PROJECT/space_hangang_full.csv"  # 실제 경로로 바꿔서 사용

# 수정된 CSV가 있으면 해당 파일을 우선 로드
dir_name = os.path.dirname(file_path)
base_name = os.path.basename(file_path).rsplit('.', 1)[0]
output_name = f"{base_name}_edit.ver.csv"
output_path = os.path.join(dir_name, output_name)
if os.path.exists(output_path):
    load_path = output_path
    print(f"편집된 CSV 파일에서 데이터 로드 중: {load_path}")
else:
    load_path = file_path
    print(f"원본 CSV 파일에서 데이터 로드 중: {load_path}")

# CSV 모듈 필드 최대 크기 설정: 원본 파일 크기의 2배로 설정
import csv, sys
file_size = os.path.getsize(load_path)
try:
    csv.field_size_limit(file_size * 2)
except OverflowError:
    csv.field_size_limit(sys.maxsize)
print(f"CSV 모듈 최대 필드 크기를 {csv.field_size_limit()}로 설정 완료")



# 1. CSV 파일을 pandas DataFrame으로 읽기
print("1단계: CSV 파일 읽기 시작")
try:
    df = pd.read_csv(load_path)
except Exception as e:
    print(f"1단계 오류 (CSV 읽기): {e}")
    raise
else:
    print("1단계: CSV 파일 읽기 완료")
print("2단계: 필터링 및 결측값 처리 시작")

# 개별 컬럼 결측값을 NULL(pd.NA)로 설정
df['in advance'] = df['in advance'].fillna(pd.NA)
df['cover']      = df['cover'].fillna(pd.NA)
print("추가: in advance와 cover의 결측값을 NULL로 대체했습니다.")
print("2단계: 결측값 대체 완료")

# === content에서 in advance 및 cover 추출 (imsta.py와 유사한 로직) ===
print("2단계: content에서 in advance 및 cover 추출 시작")
def extract_price_values(content):
    in_adv, cover = None, None
    price_pattern = re.compile(
        r"(사전예매)\s*([\d\.]+)만원"
        r"|(?:현장예매|현매)\s*([\d\.]+)만원"
        r"|([\d\.]+)만원"
        r"|([\d,]+)(?=\s*(?:원|[Ww]|KRW))",
        flags=re.IGNORECASE
    )
    matches = price_pattern.findall(content)
    found_values = []
    for grp1, grp2, grp3, grp4, grp5 in matches:
        if grp1:  # 사전예매
            value = float(grp2)
            in_adv = str(int(value * 10000))
        elif grp3:  # 현장예매/현매
            value = float(grp3)
            cover = str(int(value * 10000))
        elif grp4:  # x만원
            value = float(grp4)
            found_values.append(str(int(value * 10000)))
        elif grp5:  # 원 단위
            raw = grp5.replace(",", "")
            found_values.append(raw)

    # ambiguous values 처리
    if not in_adv and not cover and found_values:
        cover = found_values[0]
    elif not cover and found_values:
        cover = found_values[0]
    elif not in_adv and len(found_values) > 1:
        in_adv = found_values[1]

    if "무료" in content:
        cover = "0"
    return pd.Series([in_adv, cover])

df[['in advance', 'cover']] = df.apply(
    lambda row: extract_price_values(str(row['content']))
    if (pd.isna(row['in advance']) and pd.isna(row['cover']))
    else pd.Series([row['in advance'], row['cover']]),
    axis=1
)
print("2단계: content에서 in advance 및 cover 추출 완료")

# 'content' 열에 "DJ" 포함된 행 삭제 (대소문자 무관)
print("2-1단계: 'DJ' 포함 레코드 제거 시작")
df = df[~df['content'].str.contains(r'DJ', case=False, na=False)]
print(f"2-1단계: 'DJ' 포함 레코드 제거 완료. 남은 행 수: {len(df)}")

# in advance와 cover 값이 모두 비어 있는 행 삭제
df.replace({'': pd.NA}, inplace=True)
df.dropna(subset=['in advance', 'cover'], how='all', inplace=True)
print(f"추가: in advance와 cover 모두 값이 없는 행을 제거했습니다. 남은 행 수: {len(df)}")
print("2단계: 결측값 제거 완료")
# time 열 문자형으로 변환 및 매크로 등 불필요 문자 제거

df['time'] = df['time'].astype(str)
df['time'] = df['time'].str.replace(r'[^\d:시분APMapm\. ]+', '', regex=True)
df['time'] = df['time'].str.strip()

# 3. time 열을 24시간 형식으로 변환
print("3단계: 시간 형식 변환 시작")
try:
    def convert_time(val):
        if pd.isna(val):
            return val
        s = str(val).strip()
        # 'YYYY.M.D HH:MM:SS AM/PM' 형식 처리
        m_ts = re.match(
            r'^\d{4}\.\d{1,2}\.\d{1,2}\s+(\d{1,2}):(\d{2}):(\d{2})\s*(AM|PM)$',
            s, flags=re.IGNORECASE
        )
        if m_ts:
            hour = int(m_ts.group(1))
            minute = int(m_ts.group(2))
            ampm = m_ts.group(4).upper()
            if ampm == 'PM' and hour != 12:
                hour += 12
            if ampm == 'AM' and hour == 12:
                hour = 0
            return f"{hour:02d}:{minute:02d}"
        # 'HH:MM' 형식 처리 (항상 오후로 변환)
        m = re.match(r'^(\d{1,2}):(\d{2})$', s)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2))
            h = (h % 12) + 12  # 항상 오후로 변환
            return f"{h:02d}:{mi:02d}"
        # 'HH:MMam/pm' 형식 처리 (대소문자 무관)
        m_am_pm = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM)$', s, flags=re.IGNORECASE)
        if m_am_pm:
            hour = int(m_am_pm.group(1))
            minute = int(m_am_pm.group(2))
            ampm = m_am_pm.group(3).upper()
            if ampm == 'PM' and hour != 12:
                hour += 12
            if ampm == 'AM' and hour == 12:
                hour = 0
            return f"{hour:02d}:{minute:02d}"
        # 'X시 Y분' 형식 처리 (오후 12시간 추가)
        m2 = re.match(r'^(\d{1,2})시\s*(\d{1,2})분$', s)
        if m2:
            h = int(m2.group(1))
            mi = int(m2.group(2))
            h = (h % 12) + 12
            return f"{h:02d}:{mi:02d}"
        # 'X시 MM' 형식 처리 (예: 7시 30 → 19:30)
        m4 = re.match(r'^(\d{1,2})시\s*(\d{1,2})$', s)
        if m4:
            h = int(m4.group(1))
            mi = int(m4.group(2))
            h += 12
            return f"{h:02d}:{mi:02d}"
        # 'X시' 형식 처리 (오후 12시간 추가)
        m3 = re.match(r'^(\d{1,2})시$', s)
        if m3:
            h = int(m3.group(1)) + 12
            return f"{h:02d}:00"
        # 'Xpm' 또는 'Xam' 형식 처리 (대소문자 무관)
        m5 = re.match(r'^(\d{1,2})\s*(AM|PM)$', s, flags=re.IGNORECASE)
        if m5:
            hour = int(m5.group(1))
            ampm = m5.group(2).upper()
            if ampm == 'PM' and hour != 12:
                hour += 12
            if ampm == 'AM' and hour == 12:
                hour = 0
            return f"{hour:02d}:00"
        # 나머지는 원본 반환
        return s

    df['time'] = df['time'].apply(convert_time)
    print(df['time'].head(30))
    print("3단계: 시간 형식 변환 완료")

    print("4단계: 날짜 형식 변환 시작")
    # date 열이 공백인 행에 대해 content에서 날짜 패턴을 추출하여 채우기
    print("4단계: content에서 날짜 추출 및 date 열 채우기 시작")
    import datetime
    def extract_date_from_content(text, default_year):
        # 전체 한국어 형식 "YYYY년 MM월 DD일"
        m_full = re.search(r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일', text)
        if m_full:
            y, mo, d = int(m_full.group(1)), int(m_full.group(2)), int(m_full.group(3))
            return f"{y}.{mo}.{d}"
        # ISO 형식 "YYYY.MM.DD"
        m_iso = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', text)
        if m_iso:
            y, mo, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
            return f"{y}.{mo}.{d}"
        # 한국어 월일 형식 "MM월 DD일"
        m_k = re.search(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', text)
        if m_k:
            mo, d = int(m_k.group(1)), int(m_k.group(2))
            y = default_year
            return f"{y}.{mo}.{d}"
        # 점(.) 구분형 "MM.DD" (단, 앞뒤가 숫자 아닌 경우)
        m_md = re.search(r'(?<!\d)(\d{1,2})\.(\d{1,2})(?!\.\d)', text)
        if m_md:
            mo, d = int(m_md.group(1)), int(m_md.group(2))
            y = default_year
            return f"{y}.{mo}.{d}"
        # 영어 월 이름 형식 처리 (예: "January 5, 2024", "Sep. 12", "Sept 8, 2023" 등)
        month_map = {
            'january':1, 'jan':1, 'jan.':1,
            'february':2, 'feb':2, 'feb.':2,
            'march':3, 'mar':3, 'mar.':3,
            'april':4, 'apr':4, 'apr.':4,
            'may':5,
            'june':6, 'jun':6, 'jun.':6,
            'july':7, 'jul':7, 'jul.':7,
            'august':8, 'aug':8, 'aug.':8,
            'september':9, 'sep':9, 'sep.':9, 'sept':9, 'sept.':9,
            'october':10, 'oct':10, 'oct.':10,
            'november':11, 'nov':11, 'nov.':11,
            'december':12, 'dec':12, 'dec.':12
        }
        m_eng = re.search(
            r'(?<!\w)(' + '|'.join(map(re.escape, month_map.keys())) + r')\s+(\d{1,2})(?:,\s*(\d{4}))?',
            text, flags=re.IGNORECASE
        )
        if m_eng:
            key = m_eng.group(1).lower().rstrip('.')
            if key not in month_map:
                return None
            mo = month_map[key]
            d = int(m_eng.group(2))
            y = int(m_eng.group(3)) if m_eng.group(3) else default_year
            return f"{y}.{mo}.{d}"
        return None

    current_year = datetime.datetime.now().year
    mask_blank = df['date'].isna() | (df['date'].astype(str).str.strip() == '')
    for idx in df[mask_blank].index:
        new_date = extract_date_from_content(str(df.at[idx, 'content']), current_year)
        if new_date:
            df.at[idx, 'date'] = new_date
    print("4단계: content에서 날짜 추출 및 date 열 채우기 완료")
    # 'date' 열을 "YYYY.MM.DD" 형식으로 통일
    def convert_date(val):
        if pd.isna(val):
            return val
        s = str(val).strip()
        # "YYYY년MM월DD일" 형식 처리 (공백 허용)
        m = re.match(r'^(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일$', s)
        if m:
            y = int(m.group(1))
            mo = int(m.group(2))
            d = int(m.group(3))
            return f"{y:04d}.{mo:02d}.{d:02d}"
        return s  # 규격에 맞지 않으면 원본 반환

    if 'date' in df.columns:
        df['date'] = df['date'].apply(convert_date)
        print("4단계: 날짜 형식 통합 완료")
        # 5단계: date, time, in advance, cover 중복 제거
        print("4단계: date, time, in advance, cover 중복 제거 시작")
        original_len = len(df)
        # 인덱스 오름차순으로 정렬하여 가장 작은 index가 먼저 오도록 함
        df = df.sort_index()
        df = df.drop_duplicates(subset=['date', 'time', 'in advance', 'cover'], keep='first')
        removed = original_len - len(df)
        print(f"4단계: date, time, in advance, cover 중복 제거 완료. 삭제된 행 수: {removed}, 남은 행 수: {len(df)}")
    else:
        print("4단계: date 열이 존재하지 않아 통합을 건너뜁니다")
except Exception as e:
    print("4단계 오류 (날짜 변환):", e)
    raise


# 5단계: in advance와 cover가 모두 NULL 또는 공백인 레코드 제거
df = df[~(
    (df['in advance'].isna() | (df['in advance'].astype(str).str.strip()=='')) &
    (df['cover'].isna()      | (df['cover'].astype(str).str.strip()=='')))]
print(f"5단계: in advance와 cover가 모두 NULL 또는 공백인 레코드 제거 완료. 남은 행 수: {len(df)}")

# 6. 수정된 DataFrame을 새 CSV로 저장
print("6단계: CSV 저장 시작")
try:
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path).rsplit('.', 1)[0]
    output_name = f"{base_name}_edit.ver.csv"
    output_path = os.path.join(dir_name, output_name)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"수정된 CSV를 저장했습니다: {output_path}")
    print("6단계: CSV 저장 완료")
except Exception as e:
    print(f"6단계 오류 (CSV 저장): {e}")
    raise