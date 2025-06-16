import streamlit as st
import datetime
import pandas as pd
import requests
import xml.etree.ElementTree as ET

# ---------------------------- 기본 설정 ----------------------------
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

# ------------------------- 날짜 포맷 보정 -------------------------
def normalize_date(date_str):
    if isinstance(date_str, str):
        date_str = date_str.replace(".", "-").replace("/", "-")
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str

# ---------------------- 공휴일 조회 함수 (Proxy) ----------------------
def get_korean_holidays(start, end):
    HOLIDAYS = set()
    for year in range(start.year, end.year + 1):
        try:
            url = f"https://holiday-proxy.hyukjin1637.workers.dev/?year={year}"
            res = requests.get(url, timeout=10)
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
            print(f"❌ {year}년 공휴일 조회 실패: {e}")
            continue
    return HOLIDAYS

# ---------------------- 과거 강수일 예측 ----------------------
def get_past_rain_days(lat, lon, start, end, years):
    base_year = start.year
    rain_days = set()
    for y in range(base_year - years, base_year):
        url = (
            f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
            f"&start_date={y}-{start.month:02d}-{start.day:02d}"
            f"&end_date={y}-{end.month:02d}-{end.day:02d}"
            f"&daily=precipitation_sum&timezone=Asia%2FSeoul"
        )
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
            for date, rain in zip(data['daily']['time'], data['daily']['precipitation_sum']):
                if rain >= 1.0:
                    month_day = '-'.join(date.split('-')[1:])
                    rain_days.add(month_day)
        except:
            continue
    return rain_days

# ---------------------- 비작업일수 예측 ----------------------
def predict_non_working_days(start_date, end_date, sido, sigungu, analysis_years, selected_holidays):
    try:
        start_date = normalize_date(start_date)
        end_date = normalize_date(end_date)

        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        if start > end:
            return "⚠️ 시작일은 종료일보다 이전이어야 합니다."

        total_days = (end - start).days + 1
        lat, lon = district_coords[sido][sigungu]
        all_days = [start + datetime.timedelta(days=i) for i in range(total_days)]
        md_list = [d.strftime("%m-%d") for d in all_days]

        # 공휴일 계산
        holiday_days = set()
        if "법정공휴일" in selected_holidays:
            holiday_days.update(get_korean_holidays(start, end))
        if "토요일" in selected_holidays:
            holiday_days.update([d for d in all_days if d.weekday() == 5])
        if "일요일" in selected_holidays:
            holiday_days.update([d for d in all_days if d.weekday() == 6])

        # 날씨 계산
        rain_md = get_past_rain_days(lat, lon, start, end, int(analysis_years))
        rain_days = set([d for i, d in enumerate(all_days) if md_list[i] in rain_md])

        # 결과표 구성
        holiday_only = set([d for d in all_days if d in holiday_days])
        df1 = pd.DataFrame({
            "구분": ["총 기간", "공휴일 비작업일수", "가동률"],
            "값": [f"{total_days}일", f"{len(holiday_only)}일", f"{round((total_days - len(holiday_only)) / total_days * 100, 1)}%"]
        })

        df2 = pd.DataFrame({
            "구분": ["총 기간", "강수 비작업일수", "가동률"],
            "값": [f"{total_days}일", f"{len(rain_days)}일", f"{round((total_days - len(rain_days)) / total_days * 100, 1)}%"]
        })

        total_non_work = holiday_only.union(rain_days)
        df3 = pd.DataFrame({
            "구분": ["총 기간", "최종 비작업일수", "최종 가동률"],
            "값": [f"{total_days}일", f"{len(total_non_work)}일", f"{round((total_days - len(total_non_work)) / total_days * 100, 1)}%"]
        })

        return df1, df2, df3

    except Exception as e:
        return f"❌ 오류 발생: {str(e)}"

# ---------------------- Streamlit UI ----------------------
st.set_page_config(page_title="비작업일수 예측기", layout="centered")

st.title("🏗️ 비작업일수 예측기 (AI 기반)")
st.markdown("📆 기간과 지역을 선택하면, 날씨 및 공휴일을 반영한 비작업일수를 예측합니다.")

col1, col2 = st.columns(2)
with col1:
    start_date = st.text_input("시작일 (예: 2024-01-01 또는 20240101)", value="20240101")
with col2:
    end_date = st.text_input("종료일 (예: 2024-12-31 또는 20241231)", value="20241231")

sido = st.selectbox("시도 선택", list(district_coords.keys()))
sigungu = st.selectbox("시군구 선택", list(district_coords[sido].keys()))

analysis_years = st.slider("과거 강수 분석 기간 (년)", min_value=1, max_value=10, value=5)
selected_holidays = st.multiselect("비작업일로 포함할 공휴일 항목", ["법정공휴일", "토요일", "일요일"], default=["법정공휴일"])

if st.button("📊 예측 시작"):
    df1, df2, df3 = predict_non_working_days(start_date, end_date, sido, sigungu, analysis_years, selected_holidays)
    st.subheader("① 공휴일 기준 분석")
    st.dataframe(df1, use_container_width=True)
    st.subheader("② 날씨 기준 분석")
    st.dataframe(df2, use_container_width=True)
    st.subheader("③ 종합 비작업일 분석")
    st.dataframe(df3, use_container_width=True)

def check_api_key_validity(api_key):
    url = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
    params = {
        "ServiceKey": api_key,
        "solYear": "2025",
        "numOfRows": "5",
        "_type": "xml"
    }

    try:
        res = requests.get(url, params=params)
        res.raise_for_status()

        root = ET.fromstring(res.text)
        header = root.find("cmmMsgHeader")

        if header is not None:
            err_msg = header.findtext("errMsg")
            auth_msg = header.findtext("returnAuthMsg")
            return f"❌ 인증 실패: {auth_msg} / {err_msg}"
        else:
            return "✅ 인증 성공: 유효한 API Key입니다."

    except Exception as e:
        return f"❌ 요청 실패: {str(e)}"


with st.expander("🔑 공휴일 API 인증키 확인"):
    input_key = st.text_input("API Key 입력", value="T0O8HHXPZI00FcX+4D2xmYnLG8yJ6nmOrWO/hdqXy//DLuaVgaKYz/RryLDE1ITn9F921p45ZqDf2dy3Gq7YSg==")
    if st.button("API Key 유효성 확인"):
        result = check_api_key_validity(input_key)
        st.write(result)
