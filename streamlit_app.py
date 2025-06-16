import pandas as pd
import datetime
import requests
import streamlit as st
import matplotlib.pyplot as plt

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
    attempts = 0  # 몇 년치 과거까지 시도했는지 추적

    while len(valid_years) < years and attempts < 30:  # 안전장치: 최대 30년까지 시도
        attempts += 1
        past_start = start.replace(year=start.year - attempts)
        past_end = end.replace(year=end.year - attempts)

        if past_end >= today:
            continue  # 미래 구간은 건너뜀

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
def predict_non_working_days(start_date, end_date, sido, sigungu, lat, lon, years, selected_options, threshold):
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()

        total_days = (end - start).days + 1
        all_days = [start + datetime.timedelta(days=i) for i in range(total_days)]

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
        rain_table.insert(0, {"연도": "총 기간", "강수일수": total_days})  # 첫 행에 총 기간 추가
        rain_table.append({"연도": "평균", "강수일수": rain_avg})
        rain_table.append({
            "연도": "가동률",
            "강수일수": f"{round((1 - (rain_avg / total_days)) * 100, 1)}%" if total_days > 0 else "-"
        })
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
st.title("공사가동률 계산기")

@st.cache_data
def load_district_data():
    return pd.read_csv("district_coords.csv")

district_df = load_district_data()

sido_list = sorted(district_df["시도"].unique())
sido = st.selectbox("시도", sido_list)

sigungu_list = sorted(district_df[district_df["시도"] == sido]["시군구"].unique())
sigungu = st.selectbox("시군구", sigungu_list)

start_date = st.date_input("분석 시작일", value=datetime.date.today() + datetime.timedelta(days=1))
end_date = st.date_input("분석 종료일", value=datetime.date.today() + datetime.timedelta(days=60))
years = st.select_slider("과거 몇 년치 기상 데이터를 활용할까요?", options=list(range(1, 11)), value=3)
threshold = st.selectbox("강수량 기준 (비작업일로 간주할 강수량)", [1.0, 3.0, 5.0, 10.0], index=1)
selected_options = st.multiselect("비작업일 포함 기준", ["공휴일", "토요일", "일요일"], default=["공휴일", "토요일", "일요일"])

# 위도/경도 추출
row = district_df[(district_df["시도"] == sido) & (district_df["시군구"] == sigungu)]
lat = float(row["위도"].values[0])
lon = float(row["경도"].values[0])

if st.button("📊 예측 실행"):
    result = predict_non_working_days(str(start_date), str(end_date), sido, sigungu, lat, lon, years, selected_options, threshold)
    if result:
        df1, df2, df3 = result

        st.subheader("📌 공휴일/토/일 분석")
        st.dataframe(df1)

        st.subheader("📌 날씨 기반 분석 (과거 강수일 수)")
        st.dataframe(df2)

        st.subheader("📌 종합 예측 결과")
        st.dataframe(df3)

        # ------- 원형 그래프 3개 시각화 -------
        holidays_days = len(holidays) if "공휴일" in selected_options else 0
        sat_days = len(saturdays) if "토요일" in selected_options else 0
        sun_days = len(sundays) if "일요일" in selected_options else 0
        non_work1 = holidays_days + sat_days + sun_days
        work1 = total_days - non_work1

        non_work2 = round(rain_avg)
        work2 = total_days - non_work2

        total_non_work_days = non_work1 + non_work2
        work3 = total_days - total_non_work_days

        st.markdown("## 📊 가동률 시각화")
        col1, col2, col3 = st.columns(3)

        with col1:
            fig1, ax1 = plt.subplots()
            ax1.pie([work1, non_work1], labels=["가동", "비작업(공휴/주말)"], autopct='%1.1f%%', colors=["#4CAF50", "#FF9999"])
            ax1.set_title("공휴일/토/일 기반 가동률")
            st.pyplot(fig1)

        with col2:
            fig2, ax2 = plt.subplots()
            ax2.pie([work2, non_work2], labels=["가동", "비작업(강수)"], autopct='%1.1f%%', colors=["#4CAF50", "#2196F3"])
            ax2.set_title("날씨 기반 가동률")
            st.pyplot(fig2)

        with col3:
            fig3, ax3 = plt.subplots()
            ax3.pie([work3, total_non_work_days], labels=["가동", "비작업(최종)"], autopct='%1.1f%%', colors=["#4CAF50", "#FFCC80"])
            ax3.set_title("최종 종합 가동률")
            st.pyplot(fig3)
