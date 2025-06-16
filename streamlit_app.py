import streamlit as st
import datetime
import pandas as pd
import requests

# 시도 및 시군구 → 위도/경도 매핑
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

# 날짜 보정
def normalize_date(date_str):
    if isinstance(date_str, str):
        date_str = date_str.replace(".", "-").replace("/", "-")
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str

# ✅ 공휴일 API 호출 (Session + User-Agent 사용)
def get_korean_holidays(start, end):
    HOLIDAYS = set()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    for year in range(start.year, end.year + 1):
        url = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
        params = {
            "ServiceKey": "T0O8HHXPZI00FcX+4D2xmYnLG8yJ6nmOrWO/hdqXy//DLuaVgaKYz/RryLDE1ITn9F921p45ZqDf2dy3Gq7YSg==",
            "solYear": str(year),
            "numOfRows": 100,
            "_type": "json"
        }
        try:
            res = session.get(url, params=params, timeout=5)
            res.raise_for_status()
            json_data = res.json()
            items = json_data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            for item in items:
                date_str = str(item['locdate'])
                holiday = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                if start <= holiday <= end:
                    HOLIDAYS.add(holiday)
        except Exception as e:
            st.warning(f"❌ {year}년 공휴일 조회 실패: {e}")
            continue
    return HOLIDAYS

# 과거 강수일 분석
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
                    month_day = '-'.join(date.split('-')[1:])
                    rain_days.add(month_day)
        except:
            continue
    return rain_days

# 메인 예측
def predict_non_working_days(start, end, sido, sigungu, years, holiday_types):
    start = normalize_date(start)
    end = normalize_date(end)
    start = datetime.datetime.strptime(start, "%Y-%m-%d").date()
    end = datetime.datetime.strptime(end, "%Y-%m-%d").date()
    if start > end:
        st.error("⚠️ 시작일은 종료일보다 이전이어야 합니다.")
        return

    total_days = (end - start).days + 1
    all_days = [start + datetime.timedelta(days=i) for i in range(total_days)]
    md_list = [d.strftime("%m-%d") for d in all_days]

    lat, lon = district_coords[sido][sigungu]

    # 공휴일 계산
    holiday_set = set()
    if "법정공휴일" in holiday_types:
        holiday_set.update(get_korean_holidays(start, end))
    if "토요일" in holiday_types:
        holiday_set.update([d for d in all_days if d.weekday() == 5])
    if "일요일" in holiday_types:
        holiday_set.update([d for d in all_days if d.weekday() == 6])
    only_holiday = set([d for d in all_days if d in holiday_set])

    # 강수일 계산
    rain_md = get_past_rain_days(lat, lon, start, end, years)
    rain_days = set([d for i, d in enumerate(all_days) if md_list[i] in rain_md])

    # 출력
    df1 = pd.DataFrame({
        "구분": ["총 기간", "공휴일 비작업일수", "가동률"],
        "값": [f"{total_days}일", f"{len(only_holiday)}일", f"{round((total_days - len(only_holiday)) / total_days * 100, 1)}%"]
    })
    df2 = pd.DataFrame({
        "구분": ["총 기간", "강수 비작업일수", "가동률"],
        "값": [f"{total_days}일", f"{len(rain_days)}일", f"{round((total_days - len(rain_days)) / total_days * 100, 1)}%"]
    })
    total_non = only_holiday.union(rain_days)
    df3 = pd.DataFrame({
        "구분": ["총 기간", "최종 비작업일수", "최종 가동률"],
        "값": [f"{total_days}일", f"{len(total_non)}일", f"{round((total_days - len(total_non)) / total_days * 100, 1)}%"]
    })

    st.subheader("① 공휴일 기준 분석")
    st.dataframe(df1, use_container_width=True)
    st.subheader("② 날씨 기준 분석")
    st.dataframe(df2, use_container_width=True)
    st.subheader("③ 종합 비작업일 분석")
    st.dataframe(df3, use_container_width=True)

# 🌐 Streamlit UI 구성
st.title("🏗️ 비작업일수 예측기 (AI 기반)")
st.markdown("기간, 지역, 공휴일 기준을 입력하면 비작업일수를 예측합니다.")

col1, col2 = st.columns(2)
with col1:
    start_date = st.text_input("시작일 (YYYY-MM-DD)", "2025-01-01")
with col2:
    end_date = st.text_input("종료일 (YYYY-MM-DD)", "2025-12-31")

sido = st.selectbox("시도 선택", options=list(district_coords.keys()), index=0)
sigungu = st.selectbox("시군구 선택", options=list(district_coords[sido].keys()), index=0)
years = st.slider("과거 분석 연도 수", 1, 10, 5)
holiday_options = st.multiselect("공휴일 기준", ["법정공휴일", "토요일", "일요일"], default=["법정공휴일"])

if st.button("예측 시작"):
    predict_non_working_days(start_date, end_date, sido, sigungu, years, holiday_options)
