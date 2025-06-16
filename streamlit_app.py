import datetime
import requests

def get_korean_holidays(start, end):
    HOLIDAYS = set()
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    for year in range(start.year, end.year + 1):
        url = "https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
        params = {
            "ServiceKey": "T0O8HHXPZI00FcX+4D2xmYnLG8yJ6nmOrWO/hdqXy//DLuaVgaKYz/RryLDE1ITn9F921p45ZqDf2dy3Gq7YSg==",  # 디코딩된 키
            "solYear": str(year),
            "numOfRows": 100,
            "_type": "json"
        }
        try:
            print(f"🔍 요청 중: {year}")
            res = session.get(url, params=params, timeout=5)
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
