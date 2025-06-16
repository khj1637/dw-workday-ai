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

# 2. 날씨 기반 분석
def get_past_rain_days(lat, lon, start, end, years=3):
    md_rain_count = {}

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

            for date_str, rain in zip(data['daily']['time'], data['daily']['precipitation_sum']):
                if rain >= 1.0:
                    md = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%m-%d")
                    md_rain_count[md] = md_rain_count.get(md, 0) + 1

        except Exception as e:
            st.warning(f"날씨 API 오류 ({prev_year}): {e}")
            continue

    threshold = years // 2 + 1
    return {md for md, count in md_rain_count.items() if count >= threshold}

# 3. 통합 예측 함수
def predict_non_working_days(start_date, end_date, sido, sigungu, years, selected_options, district_coords):
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()

        total_days = (end - start).days + 1
        all_days = [start + datetime.timedelta(days=i) for i in range(total_days)]
        md_list = [d.strftime("%m-%d") for d in all_days]

        lat, lon = district_coords[sido][sigungu]

        holidays = get_holidays_from_csv(start, end) if "공휴일" in selected_options else set()
        saturdays = set(d for d in all_days if d.weekday() == 5) if "토요일" in selected_options else set()
        sundays = set(d for d in all_days if d.weekday() == 6) if "일요일" in selected_options else set()

        rain_md = get_past_rain_days(lat, lon, start, end, int(years))
        rain_days = set(d for i, d in enumerate(all_days) if md_list[i] in rain_md)

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

        # 강수일 분석
        df2 = pd.DataFrame({
            "구분": ["총 기간", "강수 비작업일수", "가동률"],
            "값": [f"{total_days}일", f"{len(rain_days)}일", f"{round((total_days - len(rain_days)) / total_days * 100, 1)}%"]
        })

        # 종합
        total_non_work = holidays.union(saturdays, sundays, rain_days)
        df3 = pd.DataFrame({
            "구분": ["총 기간", "최종 비작업일수", "최종 가동률"],
            "값": [f"{total_days}일", f"{len(total_non_work)}일", f"{round((total_days - len(total_non_work)) / total_days * 100, 1)}%"]
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
years = st.selectbox("과거 날씨 분석 연도 수", [1, 2, 3, 4, 5], index=2)

selected_options = st.multiselect("비작업일 포함 기준", ["공휴일", "토요일", "일요일"], default=["공휴일", "토요일", "일요일"])

if st.button("분석 시작"):
    result = predict_non_working_days(str(start_date), str(end_date), sido, sigungu, years, selected_options, district_coords)
    if result:
        df1, df2, df3 = result
        st.subheader("📌 공휴일/토/일 분석")
        st.dataframe(df1)
        st.subheader("📌 날씨 기반 비작업일")
        st.dataframe(df2)
        st.subheader("📌 종합 예측 결과")
        st.dataframe(df3)
