# streamlit_app.py
import streamlit as st
import datetime
import pandas as pd
import requests

# 시도 및 시군구 → 위도/경도 매핑 (서울특별시 예시)
district_coords = {
    "서울특별시": {
        "강남구": (37.5172, 127.0473), "강동구": (37.5301, 127.1238), "강북구": (37.6396, 127.0257),
        "강서구": (37.5509, 126.8495), "관악구": (37.4784, 126.9516), "광진구": (37.5385, 127.0823),
        "구로구": (37.4954, 126.8874), "금천구": (37.4568, 126.8950), "노원구": (37.6542, 127.0568),
        "도봉구": (37.6688, 127.0470), "동대문구": (37.5743, 127.0397), "동작구": (37.5124, 126.9392),
        "마포구": (37.5663, 126.9014), "서대문구": (37.5791, 126.9368), "서초구": (37.4836, 127.0327),
        "성동구": (37.5634, 127.0369), "성북구": (37.5894, 127.0167), "송파구": (37.5145, 127.1056),
        "양천구": (37.5169, 126.8664), "영등포구": (37.5263, 126.8963), "용산구": (37.5324, 126.9901),
        "은평구": (37.6027, 126.9291), "종로구": (37.5720, 126.9794), "중구": (37.5638, 126.9976),
        "중랑구": (37.6063, 127.0926)
    }
}

def normalize_date(date_str):
    if isinstance(date_str, str):
        date_str = date_str.replace(".", "-").replace("/", "-")
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str

def get_korean_holidays(start, end):
    HOLIDAYS = set()
    for year in range(start.year, end.year + 1):
        url = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
        params = {
            "ServiceKey": "T0O8HHXPZI00FcX%2B4D2xmYnLG8yJ6nmOrWO%2FhdqXy%2F%2FDLuaVgaKYz%2FRryLDE1ITn9F921p45ZqDf2dy3Gq7YSg%3D%3D",  # 여기! 본인의 공휴일 API KEY로 변경
            "solYear": str(year),
            "numOfRows": 100,
            "_type": "json"
        }
        try:
            headers = {
                "User-Agent": "Mozilla/5.0"
            }
            print(res.text)
            res = requests.get(url, params=params, headers=headers)
            json_data = res.json()
            items = json_data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict):
                items = [items]
            for item in items:
                date_str = str(item['locdate'])
                holiday = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                if start <= holiday <= end:
                    HOLIDAYS.add(holiday)
        except:
            continue
    return HOLIDAYS

def get_past_rain_days(lat, lon, start, end, years):
    base_year = start.year
    rain_days = set()
    for y in range(base_year - years, base_year):
        api_url = (
            f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
            f"&start_date={y}-{start.month:02d}-{start.day:02d}"
            f"&end_date={y}-{end.month:02d}-{end.day:02d}"
            f"&daily=precipitation_sum&timezone=Asia%2FSeoul"
        )
        try:
            res = requests.get(api_url)
            data = res.json()
            for date, rain in zip(data['daily']['time'], data['daily']['precipitation_sum']):
                if rain >= 1.0:
                    md = '-'.join(date.split('-')[1:])
                    rain_days.add(md)
        except:
            continue
    return rain_days

def predict_non_working_days(start_date, end_date, sido, sigungu, years, selected_holidays):
    try:
        start = datetime.datetime.strptime(normalize_date(start_date), "%Y-%m-%d").date()
        end = datetime.datetime.strptime(normalize_date(end_date), "%Y-%m-%d").date()

        total_days = (end - start).days + 1
        lat, lon = district_coords[sido][sigungu]
        all_days = [start + datetime.timedelta(days=i) for i in range(total_days)]
        md_list = [d.strftime("%m-%d") for d in all_days]

        # 공휴일 계산
        holiday_days = set()
        if "법정공휴일" in selected_holidays:
            holiday_days |= get_korean_holidays(start, end)
        if "토요일" in selected_holidays:
            holiday_days |= {d for d in all_days if d.weekday() == 5}
        if "일요일" in selected_holidays:
            holiday_days |= {d for d in all_days if d.weekday() == 6}

        # 날씨 계산
        rain_md = get_past_rain_days(lat, lon, start, end, years)
        rain_days = {d for i, d in enumerate(all_days) if md_list[i] in rain_md}

        # 결과 표
        holiday_only = {d for d in all_days if d in holiday_days}
        df1 = pd.DataFrame({"구분": ["총 기간", "공휴일 비작업일수", "가동률"],
                            "값": [f"{total_days}일", f"{len(holiday_only)}일", f"{round((total_days - len(holiday_only)) / total_days * 100, 1)}%"]})
        df2 = pd.DataFrame({"구분": ["총 기간", "강수 비작업일수", "가동률"],
                            "값": [f"{total_days}일", f"{len(rain_days)}일", f"{round((total_days - len(rain_days)) / total_days * 100, 1)}%"]})
        total_non = holiday_only | rain_days
        df3 = pd.DataFrame({"구분": ["총 기간", "최종 비작업일수", "최종 가동률"],
                            "값": [f"{total_days}일", f"{len(total_non)}일", f"{round((total_days - len(total_non)) / total_days * 100, 1)}%"]})
        return df1, df2, df3
    except Exception as e:
        return f"❌ 오류: {str(e)}", pd.DataFrame(), pd.DataFrame()

# Streamlit UI
st.title("🏗️ 비작업일수 예측기 (Streamlit 버전)")

col1, col2 = st.columns(2)
with col1:
    start = st.text_input("시작일 (YYYYMMDD 또는 YYYY-MM-DD)", "20250101")
with col2:
    end = st.text_input("종료일 (YYYYMMDD 또는 YYYY-MM-DD)", "20251231")

sido = st.selectbox("시도 선택", list(district_coords.keys()))
sigungu = st.selectbox("시군구 선택", list(district_coords[sido].keys()))
years = st.slider("분석에 사용할 과거 몇 년치 날씨?", 1, 10, 5)
holidays = st.multiselect("공휴일 기준 선택", ["법정공휴일", "토요일", "일요일"], default=["법정공휴일"])

if st.button("예측 실행"):
    result1, result2, result3 = predict_non_working_days(start, end, sido, sigungu, years, holidays)

    if isinstance(result1, str):
        st.error(result1)
    else:
        st.subheader("① 공휴일 기준 분석")
        st.dataframe(result1)

        st.subheader("② 날씨 기준 분석")
        st.dataframe(result2)

        st.subheader("③ 종합 비작업일 분석")
        st.dataframe(result3)
