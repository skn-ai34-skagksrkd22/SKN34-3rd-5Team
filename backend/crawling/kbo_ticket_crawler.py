import requests
import json
import hashlib
import pandas as pd
import re
from datetime import datetime
from zoneinfo import ZoneInfo

# 0 8 * 3-10 * /usr/bin/python3 /path/to/your/script.py

# 1. 기본 설정
KST = ZoneInfo("Asia/Seoul")
now = datetime.now(KST)
crawled_at = now.strftime("%Y-%m-%d %H:%M:%S")
YEAR = now.year
MONTH = now.month
URL = f"https://yagu.today/calendar/{YEAR}/{MONTH}"
OUTPUT_FILE = "kbo_ticket_policy.csv"

KBO_TEAMS = {
    "LG",
    "한화",
    "SSG",
    "삼성",
    "NC",
    "KT",
    "롯데",
    "KIA",
    "두산",
    "키움",
}

# 2. 페이지 가져오기
response = requests.get(
    URL,
    headers={"User-Agent": "Mozilla/5.0"}
)
response.raise_for_status()
html = response.text

# 3. initialEvents 추출
start = html.find(r'initialEvents\":[{')

if start == -1:
    raise Exception("initialEvents를 찾지 못했습니다.")

array_start = start + len(r'initialEvents\":')
depth = 0
in_string = False
escape = False
end = None

for i in range(array_start, len(html)):
    char = html[i]

    if escape:
        escape = False
        continue

    if char == "\\":
        escape = True
        continue

    if char == '"':
        in_string = not in_string
        continue

    if not in_string:
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

if end is None:
    raise Exception("initialEvents 끝을 찾지 못했습니다.")

events_text = html[array_start:end]
events_text = events_text.replace(r'\"', '"')
events = json.loads(events_text)

print(f"전체 이벤트: {len(events)}")

# 4. 현재 시점 이후의 KBO 예매 이벤트만 추출
ticket_events = []

for event in events:
    if event.get("category") != "ticket":
        continue

    home_team = event.get("homeTeam")
    away_team = event.get("awayTeam")

    if home_team not in KBO_TEAMS and away_team not in KBO_TEAMS:
        continue

    date_str = event.get("date")

    if not date_str:
        continue

    try:
        # 사이트 날짜는 UTC
        event_date = datetime.fromisoformat(
            date_str.replace("Z", "+00:00")
        )
        event_date_kst = event_date.astimezone(KST)
    except ValueError:
        continue

    # 현재 시점보다 과거인 예매는 제외
    if event_date_kst < now:
        continue

    ticket_events.append({
        "event": event,
        "event_date": event_date_kst
    })

print(f"현재 이후 KBO 예매 이벤트: {len(ticket_events)}")

# 5. ID 생성 함수
def make_id(event):
    """이벤트의 고정 정보를 이용해 ID를 생성한다."""
    team = event.get("homeTeam") or ""
    away_team = event.get("awayTeam") or ""
    date = event.get("date") or ""

    identity = "|".join([
        team,
        away_team,
        date,
    ])

    hash_value = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()

    return f"ticket_policy_{hash_value[:16]}"

# 6. content 정리 함수
def make_content(event):
    """title과 description의 예매 시간 앞에 이벤트 날짜를 추가한다."""
    title = event.get("title", "")
    description = event.get("description", "")
    date_str = event.get("date", "")

    try:
        event_date = datetime.fromisoformat(
            date_str.replace("Z", "+00:00")
        ).astimezone(KST)

        weekdays = [
            "월요일",
            "화요일",
            "수요일",
            "목요일",
            "금요일",
            "토요일",
            "일요일"
        ]

        event_date_text = (
            f"{event_date.month}월 "
            f"{event_date.day}일 "
            f"{weekdays[event_date.weekday()]}"
        )

    except ValueError:
        event_date_text = ""

    # 제목의 예매 시간 앞에 날짜 추가
    if event_date_text:
        title = re.sub(
            r"(오전|오후)\s*\d+시",
            f"{event_date_text} \\g<0>",
            title,
            count=1
        )

        # description의 "오픈: 오전/오후 시간" 앞에 날짜 추가
        description = re.sub(
            r"(오픈:\s*)(오전|오후)\s*\d+시",
            f"\\g<1>{event_date_text} \\g<2>",
            description,
            count=1
        )

    content = f"{title} {description}"
    content = content.replace("\\\n", " ")
    content = content.replace("\n", " ")
    content = content.replace("\r", " ")
    content = re.sub(r"\s+", " ", content)

    return content.strip()

# 7. CSV 데이터 생성
rows = []

for item in ticket_events:
    event = item["event"]

    rows.append({
        "id": make_id(event),
        "source": URL,
        "team": event.get("homeTeam", ""),
        "category": "ticket_policy",
        "updated_at": crawled_at,
        "content": make_content(event),
    })

# 8. Pandas DataFrame으로 CSV 저장
df = pd.DataFrame(rows)

df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8"
)

print(f"CSV 저장 완료: {OUTPUT_FILE}")
print(f"저장된 데이터: {len(df)}개")

# 9. 일부 결과 확인
for _, row in df.head(5).iterrows():
    print("\n------------------------------")
    print("id:", row["id"])
    print("team:", row["team"])
    print("category:", row["category"])
    print("content:", row["content"])