import requests
import json
import pandas as pd
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib


# 0 8 * 3-10 * /usr/bin/python3 /path/to/your/script.py


# ============================================================
# 1. 기본 설정
# ============================================================

KST = ZoneInfo("Asia/Seoul")

now = datetime.now(KST)
crawled_at = now.strftime("%Y-%m-%d %H:%M:%S")

YEAR = now.year
MONTH = now.month

URL = f"https://yagu.today/calendar/{YEAR}/{MONTH}"


# [수정] 파일 위치를 스크립트 기준으로 명확하게 지정
SCRIPT_DIR = Path(__file__).resolve().parent

OUTPUT_FILE = (
    SCRIPT_DIR
    / ".."
    / ".."
    / "data"
    / "preprocessed"
    / "kbo_ticket_policy_structured_test.csv"
).resolve()


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


# 팀 표기 → 표준 team_code
TEAM_NAME_TO_CODE = {
    "LG": "LG",
    "두산": "DOOSAN",
    "키움": "KIWOOM",
    "SSG": "SSG",
    "KT": "KT",
    "한화": "HANWHA",
    "삼성": "SAMSUNG",
    "KIA": "KIA",
    "롯데": "LOTTE",
    "NC": "NC",
}


# ============================================================
# 2. 페이지 가져오기
# ============================================================

response = requests.get(
    URL,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=20,
)

response.raise_for_status()

html = response.text


# ============================================================
# 3. initialEvents 추출
# ============================================================

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


# ============================================================
# 4. 현재 시점 이후의 KBO 예매 이벤트만 추출
# ============================================================

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
        "event_date": event_date_kst,
    })


print(f"현재 이후 KBO 예매 이벤트: {len(ticket_events)}")


# ============================================================
# 5. ID 생성
# ============================================================

def make_id(event):
    """
    [수정]
    사이트에서 제공하는 event.id를 그대로 사용한다.

    event.id는 같은 티켓 정책을 식별하는 원본 ID이므로
    title이나 description이 변경되어도 같은 ID를 유지할 수 있다.
    """

    event_id = event.get("id")

    if not event_id:
        raise ValueError("티켓 이벤트에 id가 없습니다.")

    return f"ticket_policy_{event_id}"


# ============================================================
# 6. content 정리
# ============================================================

def make_content(event):
    """
    title과 description을 하나의 검색용 content로 합친다.
    예매 시간 앞에 이벤트 날짜를 추가한다.
    """

    title = event.get("title", "")
    description = event.get("description") or ""
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
            "일요일",
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
            count=1,
        )


        # description의 "오픈: 오전/오후 시간" 앞에 날짜 추가
        description = re.sub(
            r"(오픈:\s*)(오전|오후)\s*\d+시",
            f"\\g<1>{event_date_text} \\g<2>",
            description,
            count=1,
        )


    content = f"{title} {description}"


    content = content.replace("\\\n", " ")
    content = content.replace("\n", " ")
    content = content.replace("\r", " ")

    content = re.sub(r"\s+", " ", content)


    return content.strip()


# ============================================================
# 7. 티켓 정책 파싱
# ============================================================

PATTERN = re.compile(
    r"^\[(?P<policy_type>선예매|일반|취소)\]\s*"
    r"(?P<name_part>.+?)\s+"
    r"(?P<open_date>\d{1,2}월\s*\d{1,2}일\s*[가-힣]요일)\s+"
    r"(?P<open_ampm1>오전|오후)\s*"
    r"(?P<open_time1>\d{1,2}시(?:\s*\d{1,2}분)?)\s*"
    r"\((?P<game_mmdd>\d{1,2}/\d{1,2}(?:~\d{1,2})?)\s*"
    r"(?:(?P<opponent>[^)]+?)전)?\)\s*"
    r"(?P<away>.+?)\s+vs\s+"
    r"(?P<home>.+?)\s*"
    r"\(\d{1,2}/\d{1,2}(?:~\d{1,2})?\)\s*"
    r"오픈:\s*"
    r"(?P<open_date2>\d{1,2}월\s*\d{1,2}일\s*[가-힣]요일)\s+"
    r"(?P<open_ampm2>오전|오후)\s*"
    r"(?P<open_time2>\d{1,2}시(?:\s*\d{1,2}분)?|\d{1,2}분)?\s*"
    r"(?:최대\s*(?P<max_tickets>\d+)매)?\s*"
    r"예매처:\s*(?P<booking>.+)$"
)


SUBTYPE_PATTERN = re.compile(
    r"\((?P<subtype>[^)]+)\)\s*$"
)


def parse_row(content):
    """
    content를 구조화된 티켓 정보로 변환한다.
    """

    content = content.strip()


    # [수정]
    # 제목이 [취소]로 바뀐 경우에도 기존 [선예매]/[일반] 형식으로
    # 파싱할 수 있도록 취소 상태를 따로 기억한다.
    is_cancelled = content.startswith("[취소]")


    match = PATTERN.match(content)

    if not match:
        return {
            "parse_status": "FAILED",
            "is_cancelled": is_cancelled,
        }


    data = match.groupdict()


    name_part = data["name_part"].strip()


    # 끝에 있는 괄호 내용을 policy_subtype으로 사용
    subtype_match = SUBTYPE_PATTERN.search(name_part)


    subtype = (
        subtype_match.group("subtype").strip()
        if subtype_match
        else ""
    )


    policy_name = SUBTYPE_PATTERN.sub(
        "",
        name_part
    ).strip()


    away_raw = data["away"].strip()
    home_raw = data["home"].strip()


    # [수정]
    # [취소]는 정책 유형이 아니라 상태이므로
    # 실제 policy_type은 일반/선예매로 유지한다.
    policy_type = data["policy_type"]

    if policy_type == "취소":
        policy_type = "일반"


    return {
        "parse_status": "OK",

        "policy_type": policy_type,

        "policy_name": policy_name,

        "policy_subtype": subtype,

        "open_date": data["open_date"],

        "open_ampm": data["open_ampm1"],

        "open_time": data["open_time1"],

        "game_date_mmdd": data["game_mmdd"],

        "opponent_name_raw": (
            data["opponent"] or ""
        ).strip(),

        "away_team_name_raw": away_raw,

        "home_team_name_raw": home_raw,

        "away_team_code": TEAM_NAME_TO_CODE.get(
            away_raw,
            ""
        ),

        "home_team_code": TEAM_NAME_TO_CODE.get(
            home_raw,
            ""
        ),

        "max_tickets": (
            data["max_tickets"]
            or ""
        ),

        "booking_channel_and_condition": (
            data["booking"].strip()
        ),

        "is_cancelled": is_cancelled,
    }


# ============================================================
# 8. 구조화 데이터 생성
# ============================================================

def make_structured_row(event):
    """
    하나의 ticket event를 최종 CSV 한 행으로 변환한다.
    """

    content = make_content(event)

    parsed = parse_row(content)


    team = event.get("homeTeam", "")

    team_code = TEAM_NAME_TO_CODE.get(
        team,
        team
    )


    # [수정]
    # 원본 event.id를 최종 ID로 사용한다.
    # title/content가 변경되어도 동일한 이벤트라면 같은 ID를 유지한다.
    row = {
        "id": make_id(event),

        # [수정]
        # 원본 사이트 event.id를 추적용으로 보존한다.
        "raw_id": event.get("id", ""),

        "source": URL,

        "team": team,

        "team_code": team_code,

        "category": "ticket_policy",

        "updated_at": crawled_at,

        "content": content,

        # [수정]
        # 취소된 이벤트는 CANCELLED로 표시
        "status": (
            "CANCELLED"
            if parsed.get("is_cancelled")
            else (
                "CONFIRMED"
                if parsed.get("parse_status") == "OK"
                else "RECHECK"
            )
        ),

        "evidence_type": "THIRD_PARTY_API",
    }


    # 구조화 컬럼 추가
    for key in [
        "parse_status",
        "policy_type",
        "policy_name",
        "policy_subtype",
        "open_date",
        "open_ampm",
        "open_time",
        "game_date_mmdd",
        "opponent_name_raw",
        "away_team_name_raw",
        "home_team_name_raw",
        "away_team_code",
        "home_team_code",
        "max_tickets",
        "booking_channel_and_condition",
    ]:

        row[key] = parsed.get(key, "")


    return row


# ============================================================
# 9. 기존 CSV와 비교해서 갱신
# ============================================================

def update_existing_csv(new_rows):
    """
    기존 structured CSV와 새로 수집한 데이터를 비교한다.

    같은 ID
        → 기존 데이터 업데이트

    새로운 ID
        → 신규 데이터 추가

    기존에는 있었지만 이번 크롤링에서 없는 ID
        → 삭제하지 않고 유지
    """

    # [수정]
    # 기존 CSV가 없으면 이번 데이터만 저장한다.
    if OUTPUT_FILE.exists():

        old_df = pd.read_csv(
            OUTPUT_FILE,
            encoding="utf-8-sig",
            dtype=str,
        )

        old_rows = old_df.fillna("").to_dict(
            orient="records"
        )

    else:

        old_rows = []


    # 기존 데이터를 ID 기준으로 dictionary화
    old_data = {
        row["id"]: row
        for row in old_rows
        if row.get("id")
    }


    new_count = 0
    updated_count = 0
    unchanged_count = 0


    for new_row in new_rows:

        row_id = new_row["id"]


        if row_id not in old_data:

            # 신규 데이터
            old_data[row_id] = new_row

            new_count += 1

        else:

            old_row = old_data[row_id]


            # 내용이 완전히 같으면 그대로 유지
            if old_row == new_row:

                unchanged_count += 1

            else:

                # 기존 ID의 데이터만 업데이트
                old_data[row_id] = new_row

                updated_count += 1


    # [수정]
    # 이번 크롤링에서 빠진 기존 데이터는 삭제하지 않는다.
    result_rows = list(old_data.values())


    # 컬럼 순서 고정
    fieldnames = [
        "id",
        "raw_id",
        "source",
        "team",
        "team_code",
        "category",
        "updated_at",
        "content",
        "status",
        "evidence_type",
        "parse_status",
        "policy_type",
        "policy_name",
        "policy_subtype",
        "open_date",
        "open_ampm",
        "open_time",
        "game_date_mmdd",
        "opponent_name_raw",
        "away_team_name_raw",
        "home_team_name_raw",
        "away_team_code",
        "home_team_code",
        "max_tickets",
        "booking_channel_and_condition",
    ]


    df = pd.DataFrame(
        result_rows,
        columns=fieldnames,
    )


    # 출력 폴더가 없으면 생성
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )


    print()
    print("------------------------------")
    print("CSV 갱신 결과")
    print("------------------------------")
    print(f"신규 데이터: {new_count}개")
    print(f"변경 데이터: {updated_count}개")
    print(f"변경 없음: {unchanged_count}개")
    print(f"최종 데이터: {len(df)}개")
    print(f"저장 위치: {OUTPUT_FILE}")


# ============================================================
# 10. 실행
# ============================================================

def main():

    new_rows = []


    for item in ticket_events:

        event = item["event"]

        try:

            row = make_structured_row(event)

            new_rows.append(row)

        except Exception as e:

            print(
                f"데이터 처리 실패: "
                f"{event.get('id', '')} / {e}"
            )


    print()
    print(f"구조화 데이터 생성: {len(new_rows)}개")


    update_existing_csv(new_rows)


    # 일부 결과 확인
    for row in new_rows[:5]:

        print()
        print("------------------------------")
        print("id:", row["id"])
        print("team:", row["team"])
        print("status:", row["status"])
        print("parse_status:", row["parse_status"])
        print("content:", row["content"])


if __name__ == "__main__":
    main()