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

# 2. 강수 기준별 과거 비작업일 계산 함수
def get_yearly_rain_days(lat, lon, start, end, rain_threshold, years):
    year_results = {}
    for y in range(1, years + 1):
        prev_year = start.year - y
        s = start.replace(year=prev_year)
        e = end.replace(year=prev_year)

        try:
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": s.strftime("%Y-%m-%d"),
                "end_date": e.strftime("%Y-%m-%d"),
                "daily": "precipitation_sum",
                "timezone": "Asia/Seoul"
            }
            res = requests.get(url, params=params)
            res.raise_for_status()
            data = res.json()
            rain_days = [
                datetime.datetime.strptime(d, "%Y-%m-%d").date()
                for d, r in zip(data['daily']['time'], data['daily']['precipitation_sum'])
                if r >= rain_threshold
            ]
            year_results[prev_year] = len(rain_days)
        except Exception as e:
            st.warning(f"{prev_year}년 날씨 데이터 오류: {e}")
            year_results[prev_year] = None
    return year_results

# 3. 통합 예측 함수
def predict_non_working_days(start_date, end_date, sido, sigungu, years, selected_options, rain_threshold, district_coords):
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        total_days = (end - start).days + 1
        all_days = [start + datetime.timedelta(days=i) for i in range(total_days)]

        lat, lon = district_coords[sido][sigungu]

        holidays = get_holidays_from_csv(start, end) if "공휴일" in selected_options else set()
        saturdays = set(d for d in all_days if d.weekday() == 5) if "토요일" in selected_options else set()
        sundays = set(d for d in all_days if d.weekday() == 6) if "일요일" in selected_options else set()

        # 공휴일 분석
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

        # 강수 분석
        rain_results = get_yearly_rain_days(lat, lon, start, end, rain_threshold, int(years))
        valid_rain_counts = [v for v in rain_results.values() if v is not None]
        avg_rain = round(sum(valid_rain_counts) / len(valid_rain_counts), 1) if valid_rain_counts else 0

        df2 = pd.DataFrame(
            [["총 기간", f"{total_days}일"]] +
            [[f"{year}년 강수일수", f"{cnt}일" if cnt is not None else "오류"] for year, cnt in rain_results.items()] +
            [["평균 강수일수", f"{avg_rain}일"]],
            columns=["구분", "값"]
        )

        # 종합 결과
        total_non_work = holidays.union(saturdays, sundays)
        total_non_work_count = len(total_non_work) + avg_rain
        final_operate_rate = round((total_days - total_non_work_count) / total_days * 100, 1)

        df3 = pd.DataFrame({
            "구분": ["총 기간", "최종 비작업일수", "최종 가동률"],
            "값": [f"{total_days}일", f"{int(total_non_work_count)}일", f"{final_operate_rate}%"]
        })

        return df1, df2, df3
    except Exception as e:
        st.error(f"예측 오류: {e}")
        return None

# 4. UI
st.title("📅 비작업일수 분석기")

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
start_date = st.date_input("분석 시작일", value=datetime.date.today() - datetime.timedelta(days=30))
end_date = st.date_input("분석 종료일", value=datetime.date.today())

selected_options = st.multiselect("비작업일 포함 기준", ["공휴일", "토요일", "일요일"], default=["공휴일", "토요일", "일요일"])

rain_threshold = st.selectbox("강수량 기준(mm 이상)", [1, 3, 5, 10], index=0)
years = st.selectbox("과거 날씨 분석 연도 수", list(range(1, 11)), index=2)

if st.button("분석 시작"):
    result = predict_non_working_days(str(start_date), str(end_date), sido, sigungu, years, selected_options, rain_threshold, district_coords)
    if result:
        df1, df2, df3 = result
        st.subheader("📌 공휴일/토/일 분석")
        st.dataframe(df1)
        st.subheader("📌 과거 강수 기반 비작업일 분석")
        st.dataframe(df2)
        st.subheader("📌 종합 예측 결과")
        st.dataframe(df3)
