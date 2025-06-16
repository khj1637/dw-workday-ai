import datetime
import pandas as pd
import requests

# 공휴일 CSV 기반 불러오기 함수
def get_holidays_from_csv(start: datetime.date, end: datetime.date) -> set:
    try:
        df = pd.read_csv("korean_holidays.csv")
        df['date'] = pd.to_datetime(df['date']).dt.date
        return set(df[(df['date'] >= start) & (df['date'] <= end)]['date'])
    except Exception as e:
        print(f"❌ 공휴일 CSV 파일 로드 실패: {e}")
        return set()

# 날씨 기반 과거 강수일 분석 함수
def get_past_rain_days(lat, lon, start, end, years=3):
    md_rain_count = {}

    for y in range(1, years + 1):
        prev_year = start.year - y
        s = start.replace(year=prev_year)
        e = end.replace(year=prev_year)

        try:
            # 예시 API (대체 필요): API 형식에 맞게 수정
            url = f"https://archive-api.open-meteo.com/v1/archive"
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
            print(f"❌ 날씨 데이터 호출 실패 ({prev_year}): {e}")
            continue

    # 확률적으로 절반 이상 비가 온 날 추출
    threshold = years // 2 + 1
    return {md for md, count in md_rain_count.items() if count >= threshold}


# 통합 비작업일수 예측 함수
def predict_non_working_days(start_date, end_date, sido, sigungu, analysis_years, selected_holidays, district_coords):
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()

        if start > end:
            return "⚠️ 시작일은 종료일보다 이전이어야 합니다."

        total_days = (end - start).days + 1
        lat, lon = district_coords[sido][sigungu]
        all_days = [start + datetime.timedelta(days=i) for i in range(total_days)]
        md_list = [d.strftime("%m-%d") for d in all_days]

        # ✅ 공휴일 계산
        holiday_days = set()
        if selected_holidays:
            holiday_days = get_holidays_from_csv(start, end)

        holiday_only = set(d for d in all_days if d in holiday_days)

        # ✅ 날씨 기반 비작업일 계산
        rain_md = get_past_rain_days(lat, lon, start, end, int(analysis_years))
        rain_days = set(d for i, d in enumerate(all_days) if md_list[i] in rain_md)

        # ✅ 결과 표 생성
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
