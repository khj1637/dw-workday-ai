import streamlit as st
import datetime
import requests
import pandas as pd

# ⏱️ 공휴일 조회 함수 (Cloudflare Worker 프록시 사용)
def get_korean_holidays(start, end):
    holidays = set()
    for year in range(start.year, end.year + 1):
        try:
            url = f"https://holiday-proxy.hyukjin1637.workers.dev/?year={year}"
            res = requests.get(url, timeout=5)
            res.raise_for_status()
            data = res.json()
            for date_str in data.get("holidays", []):
                holiday_date = datetime.datetime.strptime(date_str, "%Y%m%d").date()
                if start <= holiday_date <= end:
                    holidays.add(holiday_date)
        except Exception as e:
            st.error(f"❌ {year}년 공휴일 조회 실패: {e}")
    return holidays

# 📅 날짜 자동 포맷 (예: 20251125 → 2025-11-25)
def parse_date(date_str):
    try:
        if len(date_str) == 8:
            return datetime.datetime.strptime(date_str, "%Y%m%d").date()
        else:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        return None

# 🧠 비작업일수 계산
def calculate_non_working_days(start_date, end_date, include_saturday, include_sunday, include_holidays):
    all_days = [start_date + datetime.timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    holidays = get_korean_holidays(start_date, end_date) if include_holidays else set()

    non_working = set()
    for day in all_days:
        if (include_saturday and day.weekday() == 5) or \
           (include_sunday and day.weekday() == 6) or \
           (include_holidays and day in holidays):
            non_working.add(day)

    total_days = len(all_days)
    non_working_days = len(non_working)
    utilization = round((total_days - non_working_days) / total_days * 100, 1)

    return pd.DataFrame({
        "구분": ["총 기간", "비작업일수", "가동률"],
        "값": [f"{total_days}일", f"{non_working_days}일", f"{utilization}%"]
    })

# 🖥️ Streamlit UI
st.title("📅 비작업일수 계산기")

col1, col2 = st.columns(2)
with col1:
    start_input = st.text_input("시작일 (YYYYMMDD 또는 YYYY-MM-DD)", value="20250101")
with col2:
    end_input = st.text_input("종료일 (YYYYMMDD 또는 YYYY-MM-DD)", value="20251231")

start_date = parse_date(start_input)
end_date = parse_date(end_input)

include_holidays = st.checkbox("법정공휴일 포함", value=True)
include_saturday = st.checkbox("토요일 포함", value=False)
include_sunday = st.checkbox("일요일 포함", value=True)

if st.button("비작업일수 계산하기"):
    if not start_date or not end_date:
        st.warning("📌 날짜 형식이 올바르지 않습니다.")
    elif start_date > end_date:
        st.warning("📌 시작일은 종료일보다 이전이어야 합니다.")
    else:
        df_result = calculate_non_working_days(start_date, end_date, include_saturday, include_sunday, include_holidays)
        st.success("✅ 계산 완료!")
        st.dataframe(df_result, use_container_width=True)
