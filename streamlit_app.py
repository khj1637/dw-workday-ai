import pandas as pd
import datetime
import requests
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.transforms as mtransforms
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Wedge
import os

percent_font = FontProperties(fname="fonts/NanumBarunGothicBold.ttf")

# 폰트 경로
FONT_URL = "https://raw.githubusercontent.com/khj1637/dw-workday-ai/main/fonts/NanumGothic.ttf"
FONT_PATH = "NanumGothic.ttf"

# 폰트 다운로드 (처음 1회만)
if not os.path.exists(FONT_PATH):
    response = requests.get(FONT_URL)
    with open(FONT_PATH, "wb") as f:
        f.write(response.content)

# matplotlib에 폰트 등록
font_prop = fm.FontProperties(fname=FONT_PATH)
plt.rcParams['font.family'] = font_prop.get_name()

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

# ----------- 동일 원형 그래프 그리는 함수 -------------
def draw_fixed_pie(work, non_work, colors, caption, font_prop):
    fig, ax = plt.subplots(figsize=(3.5, 3.5))
    explode = [0.05, 0.05]
    values = [work, non_work]
    total = sum(values)

    # ✅ 메인 파이차트 먼저 그리기
    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct='%1.1f%%',
        startangle=90,
        colors=colors,
        explode=explode,
        textprops={'fontproperties': font_prop, 'fontsize': 14},
        wedgeprops=dict(edgecolor='#000000', linewidth=1.5),
        pctdistance=0.6
    )

    # ✅ 퍼센트 스타일
    for autotext in autotexts:
        autotext.set_fontproperties(percent_font)
        autotext.set_color('white')
        autotext.set_fontsize(24)

    # ✅ 각도 계산
    angles = [0]
    for v in values:
        angles.append(angles[-1] + v / total * 360)

    # 그림자 wedge 추가 (먼저 그림, zorder 낮게)
    for i in range(len(values)):
        theta1 = angles[i]
        theta2 = angles[i + 1]
        wedge = Wedge(
            center=(0.08, -0.08),  # ↘ 방향 그림자
            r=1,
            theta1=theta1,
            theta2=theta2,
            facecolor='#555555',
            alpha=0.5,
            linewidth=0,
            zorder=0  # ✅ 낮은 z순서로 뒤에 깔리게
        )
        ax.add_patch(wedge)

    ax.set_aspect('equal')
    ax.set_ylim(-1.7, 1.1)  # ✅ 그림자 보이게 충분히 여유 확보

    # ✅ 캡션
    ax.text(0, -1.6, caption, ha='center', va='top',
            fontproperties=font_prop, fontsize=18)

    # ✅ 범례
    ax.legend(
        wedges,
        ["가동률", "비작업일"],
        loc="upper right",
        bbox_to_anchor=(1.25, 1),
        prop=font_prop,
        fontsize=20,
        title_fontproperties=font_prop
    )

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return fig

# 3. 예측 실행 함수
def predict_non_working_days(start_date, end_date, sido, sigungu, lat, lon, years, selected_options, threshold):
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()

        # 날짜 목록 만들고
        total_days = (end - start).days + 1
        all_days = [start + datetime.timedelta(days=i) for i in range(total_days)]

        # 먼저 각 날짜 집합 정의
        holidays = get_holidays_from_csv(start, end) if "공휴일" in selected_options else set()
        saturdays = set(d for d in all_days if d.weekday() == 5) if "토요일" in selected_options else set()
        sundays = set(d for d in all_days if d.weekday() == 6) if "일요일" in selected_options else set()

        # 그 다음 개수 세기
        holidays_days = len(holidays)
        sat_days = len(saturdays)
        sun_days = len(sundays)

        rain_stats, rain_avg = get_statistical_rain_days(lat, lon, start, end, years, threshold)

                
        non_work1 = holidays_days + sat_days + sun_days
        
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
        "구분": [
            "총 기간",
            "휴일 분석 결과",
            "날씨 분석 결과",
            "최종 비작업일수",
            "최종 가동률"
        ],
        "값": [
            f"{total_days}일",
            f"{non_work1}일",  # 공휴일 + 토요일 + 일요일
            f"{round(rain_avg)}일",
            f"{round(total_non_work_days)}일",
            f"{round((total_days - total_non_work_days) / total_days * 100, 1)}%"
        ]
    })

        return df1, df2, df3, holidays_days, sat_days, sun_days, round(rain_avg), total_days, non_work1

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

start_date = st.date_input("공사 시작일", value=datetime.date.today() + datetime.timedelta(days=1))
end_date = st.date_input("공사 종료일", value=datetime.date.today() + datetime.timedelta(days=60))
years = st.select_slider("과거 몇 년치 기상 데이터를 활용할까요?", options=list(range(1, 11)), value=3)
threshold = st.selectbox("강수량 기준 (비작업일로 간주할 강수량)", [1.0, 3.0, 5.0, 10.0], index=1)

selected_options = st.multiselect("비작업일 포함 휴일 기준", ["공휴일", "토요일", "일요일"], default=["공휴일", "토요일", "일요일"])

# 위도/경도 추출
row = district_df[(district_df["시도"] == sido) & (district_df["시군구"] == sigungu)]
lat = float(row["위도"].values[0])
lon = float(row["경도"].values[0])

if st.button("📊 예측 실행"):
    result = predict_non_working_days(str(start_date), str(end_date), sido, sigungu, lat, lon, years, selected_options, threshold)
    if result:
        df1, df2, df3, holidays_days, sat_days, sun_days, rain_avg, total_days, non_work1 = result

        st.subheader("1️⃣ 휴일 분석")
        st.dataframe(df1)

        st.subheader("2️⃣ 날씨 기반 분석")
        st.dataframe(df2)

        st.subheader("3️⃣ 종합 결과")
        
        # --------- 원형 그래프 ---------
        non_work1 = holidays_days + sat_days + sun_days
        work1 = total_days - non_work1

        non_work2 = round(rain_avg)
        work2 = total_days - non_work2

        total_non_work_days = non_work1 + non_work2
        work3 = total_days - total_non_work_days

        col1, col2, col3 = st.columns(3)

        with col1:
            fig1 = draw_fixed_pie(
                work1, non_work1,
                ["#4B0082", "#696969"],
                "휴일 기반 가동률",
                font_prop
            )
            st.pyplot(fig1)

        with col2:
            fig2 = draw_fixed_pie(
                work2, non_work2,
                ["#4CAF50", "#696969"],
                "날씨 기반 가동률",
                font_prop
            )
            st.pyplot(fig2)

        with col3:
            fig3 = draw_fixed_pie(
                work3, total_non_work_days,
                ["#800000", "#696969"],
                "종합 가동률",
                font_prop
            )
            st.pyplot(fig3)
            
        st.dataframe(df3)

        st.subheader("4️⃣ 분석 해설 및 시스템 설명")

        st.markdown(f"""
        - 본 분석은 **{sido} {sigungu} 지역**을 대상으로, **{start_date.strftime('%Y년 %m월 %d일')}부터 {end_date.strftime('%Y년 %m월 %d일')}까지** 총 {total_days}일간의 공사 일정을 기준으로 수행되었습니다.

        - 날씨 기반 비작업일 예측은 **Open-Meteo의 과거 기상 API**를 활용하여, 최근 **{years}년간 동일 기간의 일별 강수 데이터를 분석**한 결과입니다. 하루 강수량이 **{threshold}mm 이상인 날을 비작업일로 간주**하고 연도별 통계를 기반으로 **신뢰도 높은 평균 비작업일수({round(rain_avg)}일)**를 산정하였습니다.

        - 공휴일은 GitHub에 등록된 **전국 공휴일 CSV 데이터**를 기준으로 자동 적용되며, 선택한 기간 내의 해당 날짜가 비작업일로 반영됩니다.
        """)

        # 공휴일 설명
        if "공휴일" in selected_options:
            df_holidays = pd.read_csv("korean_holidays.csv")
            df_holidays['date'] = pd.to_datetime(df_holidays['date']).dt.date
            filtered_holidays = df_holidays[(df_holidays['date'] >= start_date) & (df_holidays['date'] <= end_date)]
            holiday_list = [f"{d.strftime('%m/%d')} {n}" for d, n in zip(filtered_holidays['date'], filtered_holidays['holiday_name'])]
            if holiday_list:
                holiday_text = " / ".join(holiday_list)
                st.markdown(f"- 비작업일로 반영된 공휴일 목록: **{holiday_text}**")
            else:
                st.markdown("- 분석 기간 내 공휴일이 없어, 공휴일에 따른 비작업일은 적용되지 않았습니다.")
        else:
            st.markdown("- **공휴일 미포함** 옵션을 선택하였기에, 공휴일은 비작업일 계산에서 제외되었습니다.")

        # 주말 설명
        weekends = []
        if "토요일" in selected_options:
            weekends.append("토요일")
        if "일요일" in selected_options:
            weekends.append("일요일")

        if weekends:
            st.markdown(f"- 주말 중 **{', '.join(weekends)}** 또한 비작업일로 반영되었습니다.")
        else:
            st.markdown("- 주말은 비작업일에 포함되지 않았습니다.")



