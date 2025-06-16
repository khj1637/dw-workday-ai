import pandas as pd
import datetime
import requests
import streamlit as st

# 1. CSV 기반 공휴일 로딩
def get_holidays_from_csv(start: datetime.date, end: datetime.date) -> set:
    try:
        df = pd.read_csv("korean_holidays.csv")
        df['date'] = pd.to_datetime(df['date']).dt.date
        return set(df[(df['date'] >= start) & (df['date'] <= end)]['date'])
    except Exception as e:
        st.error(f"공휴일 CSV 로드 오류: {e}")
        return set()

# 2. 날씨 기반 비작업일 계산 (강수 기준/기간에 따른 통계 기반 분석)
def get_statistical_rain_days(lat, lon, start, end, years=3, threshold=1.0):
    today = datetime.date.today()
    results = {}
    valid_years = []

    for y in range(1, years + 1):
        past_start = start.replace(year=start.year - y)
        past_end = end.replace(year=end.year - y)

        if past_end >= today:
            continue  # 미래 데이터는 스킵

        try:
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": past_start.strftime("%Y-%m-%d"),
                "end_date": past_end.strftime("%Y-%m-%d"),
                "daily": "precipitation_sum",
                "timezone": "Asia/Seoul"
            }
            res = requests.get(url, params=params)
            res.raise_for_status()
            data = res.json()

            rain_days = sum(1 for rain in data['daily']['precipitation_sum'] if rain >= threshold)
            results[f"{past_start.year}-{past_end.year}"] = rain_days
            valid_years.append(rain_days)
        except Exception as e:
            st.warning(f"{past_start.year}~{past_end.year} 강수 분석 실패: {e}")
            continue

    avg = round(sum(valid_years) / len(valid_years), 1) if valid_years else 0
    return results, avg

# 3. 예측 실행 함수
def predict_non_working_days(start_date, end_date, sido, sigungu, years, selected_options, threshold, district_coords):
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()

        total_days = (end - start).days + 1
        all_days = [start + datetime.timedelta(days=i) for i in range(total_days)]

        lat, lon = district_coords[sido][sigungu]

        holidays = get_holidays_from_csv(start, end) if "공휴일" in selected_options else set()
        saturdays = set(d for d in all_days if d.weekday() == 5) if "토요일" in selected_options else set()
        sundays = set(d for d in all_days if d.weekday() == 6) if "일요일" in selected_options else set()

        rain_stats, rain_avg = get_statistical_rain_days(lat, lon, start, end, years, threshold)

        # 각각 분석
        df1 = pd.DataFrame({
            "구분": ["총 기간", "공휴일", "토요일", "일요일", "가동률"],
            "값": [
                f"{total_days}일",
                f"{len(holidays)}일" if "공휴일" in selected_options else "-",
                f"{len(saturdays)}일" if "토요일" in selected_options else "-",
                f"{len(sundays)}일" if "일요일" in selected_options else "-",
                f"{round((total_days - len(holidays.union(saturdays, sundays))) / total_days * 100, 1)}%" if selected_options else "-"
            ]
        })

        rain_table = [{"연도": k, "강수일수": v} for k, v in rain_stats.items()]
        rain_table.append({"연도": "평균", "강수일수": rain_avg})
        df2 = pd.DataFrame(rain_table)

        total_non_work = holidays.union(saturdays, sundays)
        total_non_work_days = len(total_non_work) + rain_avg

        df3 = pd.DataFrame({
            "구분": ["총 기간", "최종 비작업일수", "최종 가동률"],
            "값": [f"{total_days}일", f"{round(total_non_work_days)}일", f"{round((total_days - total_non_work_days) / total_days * 100, 1)}%"]
        })

        return df1, df2, df3

    except Exception as e:
        st.error(f"예측 오류: {e}")
        return None

# 4. UI
st.title("📅 비작업일수 예측기")

district_coords = {
    "서울특별시": {
        "강남구": (37.5172, 127.0473),
        "마포구": (37.5665, 126.9016),
    },
    "경기도": {
        "성남시": (37.4202, 127.1266),
        "수원시": (37.2636, 127.0286),
    }
}

sido = st.selectbox("시도", list(district_coords.keys()))
sigungu = st.selectbox("시군구", list(district_coords[sido].keys()))
start_date = st.date_input("분석 시작일", value=datetime.date.today() + datetime.timedelta(days=1))
end_date = st.date_input("분석 종료일", value=datetime.date.today() + datetime.timedelta(days=60))
years = st.select_slider("과거 몇 년치 기상 데이터를 활용할까요?", options=list(range(1, 11)), value=3)
threshold = st.selectbox("강수량 기준 (비작업일로 간주할 강수량)", [1.0, 3.0, 5.0, 10.0], index=1)
selected_options = st.multiselect("비작업일 포함 기준", ["공휴일", "토요일", "일요일"], default=["공휴일", "토요일", "일요일"])

if st.button("📊 예측 실행"):
    result = predict_non_working_days(str(start_date), str(end_date), sido, sigungu, years, selected_options, threshold, district_coords)
    if result:
        df1, df2, df3 = result
        st.subheader("📌 공휴일/토/일 분석")
        st.dataframe(df1)
        st.subheader("📌 날씨 기반 분석 (과거 강수일 수)")
        st.dataframe(df2)
        st.subheader("📌 종합 예측 결과")
        st.dataframe(df3)