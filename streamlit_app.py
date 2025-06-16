import streamlit as st
import datetime
import requests
import pandas as pd
import logging

# ✅ logging 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 시도/시군구 → 위도/경도
district_coords = {
    "서울특별시": {
        "강남구": (37.5172, 127.0473), "마포구": (37.5663, 126.9014)  # 예시 일부
    }
}

# 날짜 포맷 보정 함수
def normalize_date(date_str):
    if isinstance(date_str, str):
        date_str = date_str.replace(".", "-").replace("/", "-")
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str

# ✅ 공휴일 API 호출 함수 with logging
def get_korean_holidays(start, end):
    HOLIDAYS = set()
    for year in range(start.year, end.year + 1):
        url = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
        params = {
            "ServiceKey": "T0O8HHXPZI00FcX+4D2xmYnLG8yJ6nmOrWO/hdqXy//DLuaVgaKYz/RryLDE1ITn9F921p45ZqDf2dy3Gq7YSg==",  # 디코딩된 키
            "solYear": str(year),
            "numOfRows": 100,
            "_type": "json"
        }
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            logger.debug(f"🔍 요청 중: {year}")
            res = requests.get(url, params=params, headers=headers)
            logger.debug(f"📦 응답 상태코드: {res.status_code}")
            logger.debug(f"📄 응답 일부: {res.text[:300]}")  # 너무 길면 일부만 출력

            res.raise_for_status()
            json_data = res.json()
            items = json_data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict):
                items = [items]

            for item in items:
                date_str = str(item['locdate'])
                holiday = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                if start <= holiday <= end:
                    HOLIDAYS.add(holiday)
        except Exception as e:
            logger.error(f"❌ {year}년 공휴일 조회 실패: {e}")
            continue
    return HOLIDAYS

# 테스트용 Streamlit 인터페이스
st.title("공휴일 API 테스트")
start_input = st.text_input("시작일", value="20250101")
end_input = st.text_input("종료일", value="20251231")

if st.button("공휴일 조회"):
    try:
        start = datetime.datetime.strptime(normalize_date(start_input), "%Y-%m-%d").date()
        end = datetime.datetime.strptime(normalize_date(end_input), "%Y-%m-%d").date()
        holidays = get_korean_holidays(start, end)
        st.success(f"✅ 공휴일 {len(holidays)}일 조회됨")
        st.write(sorted(holidays))
    except Exception as e:
        st.error(f"오류: {e}")
