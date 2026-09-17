# 루트 만들기 가이드 · 관리자 신고 관리 · 챗봇 출발지 코스

작성일: 2026-09-16 · 브랜치: `feat/route-guide-admin-moderation`

## 1. 루트 만들기 스포트라이트 가이드 (`/routes/new`)

- "가이드 시작" 버튼(제목 오른쪽)으로만 시작한다. [driver.js](https://driverjs.com/)(MIT) 사용.
- 실제 작성 화면을 건드리지 않도록 **같은 작성 화면을 샘플 모드로 전체 화면에 띄워** 그 위에서 진행한다.
  샘플 모드(`WriterForm sample`)는 임시저장·나가기 확인·챗봇 요청·코스 저장이 모두 꺼져 있고, 챗봇은 `ChatSampleProvider`(빈 대화)를 쓴다.
  가이드를 닫으면 샘플 화면만 사라지고 실제 화면은 그대로다.
- 진행 중에는 휠·터치·휠 클릭·방향키 스크롤을 막고, 단계에 맞춰 가이드가 직접 스크롤한다. 오른쪽 위 ×(또는 Esc)로 종료.
- 단계: 시작 → 구장 선택(광주-KIA 챔피언스 필드 고정) → 카테고리 → 출발점 선택(정해진 좌표) → 챗봇 입력(예시 문장 타이핑) →
  예시 코스 → 내 코스 → 코스 수정 → 코스 저장("마이 코스" 타이핑, 저장 버튼 활성) → 저장 팝업 → 마무리(캐릭터 + "가이드 종료").
- 사용자의 클릭은 실제 기능을 실행하지 않고 다음 단계로만 넘긴다(정해진 결과만 연출).
- 파일: `frontend/components/route-guide.tsx`, `frontend/lib/route-guide-events.ts`, `frontend/styles/writer.css`,
  `frontend/public/images/guide/guide-mascot.png`

## 2. 관리자 마이페이지 · 신고 관리

- 운영/마스터 관리자(`is_staff` 또는 `is_superuser`) 계정은 로그인하면 마이페이지로 이동한다(그 외 계정은 메인).
- 마이페이지 탭: 내 코스 · 찜한 코스 · 내가 쓴 글 · **회원 관리 · 게시글 관리 · 신고 관리** (회원 정보 탭 대신). 맨 아래 로그아웃.
- 헤더의 마이페이지 메뉴도 같은 관리 메뉴 3개로 연결한다.
- 신고 관리: 상태(처리 대기/보류/숨김) 표시, **보류(파랑) · 숨김(주황) · 삭제(빨강)**.
  - 보류: 신고 상태만 `held`. 글은 유지.
  - 숨김: 글 `is_hidden=true` → 공개 목록·상세(비관리자)에서 제외. 같은 글의 신고도 `hidden`.
  - 삭제: "해당 계정에 대한 처분을 결정하십시오" 팝업(닉네임·아이디, 보류/7일/30일/영구 정지 선택) 후 **글만 삭제**한다.
    선택한 처분은 현재 계정에 적용하지 않는다(요청에 따라 계정 정지는 제외).

### 관리자 API (운영 관리자 이상, JWT)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/community/admin/posts/?q=&page=` | 게시글 목록(제목·작성자·글 번호 검색, `report_count`, `is_hidden`) |
| DELETE | `/api/community/admin/posts/<source_id>/` | 게시글 삭제(댓글·추천·신고 포함) |
| GET | `/api/community/admin/reports/?page=` | 신고 목록(대기 먼저, 글·작성자 계정 정보 포함) |
| POST | `/api/community/admin/reports/<id>/action/` | `{"action": "hold"\|"hide"\|"delete", "sanction": "none"\|"7d"\|"30d"\|"permanent"}` |

- 마이그레이션: `community.0009_report_moderation`(글 `is_hidden`, 신고 `status`·`handled_at`·`handled_by`)
- `accounts.0006`(정지 칸 추가) → `accounts.0007`(정지 칸 제거): 계정 정지를 넣었다가 빼면서 생긴 쌍이다. 새 DB에서는 순서대로 적용되어 결과적으로 변화가 없다.
- 파일: `backend/community/admin_views.py`, `backend/community/test_admin.py`, `frontend/components/admin-panels.tsx`, `frontend/lib/api/admin-community.ts`
- `frontend/lib/api/schema.d.ts`·`contracts/openapi.yaml`은 아직 새 API로 다시 생성하지 않았다. 프론트는 `admin-community.ts`에 응답 타입을 직접 정의했다.

## 3. 챗봇 코스 · 코스 편집

- 코스 작성 화면에서 지도에 찍은 출발지를 `[출발지: lat,lng]` 접두어로 보낸다(`contextPrefix`).
  백엔드는 접두어를 떼어 `origin`으로 넘기고, **출발지가 있는 코스 질문은 에이전트 대신 course 도메인이 출발지부터 단계별로 장소를 찾는다**
  (출발지 근처 1번 → 1번 근처 2번 …, 구장에 가까워지는 방향 우선). 스트리밍 경로도 같다.
- 챗봇 코스를 다시 담아도 지도에 찍은 출발지는 유지한다(develop의 `courseTarget` 방식 위에 적용).
- 챗봇이 새 코스를 만드는 동안 완성된 코스 잠금을 푼다(`unlockRequest`).
- 비로그인 상태에서는 챗봇 질문을 막고 조회만 허용한다.
- 코스 편집: 방문 순서 되돌리기/다시하기, 페이지를 떠날 때 확인 후 초기화, 응원팀 구장(없으면 랜덤) 기본 선택.

## 4. 기타 화면

- 메인: 챗봇 입력창·야구모자 로봇(CapBot)·AI 버튼, 바로가기 이미지 아이콘. 헤더 메뉴의 챗봇 아이콘도 CapBot.
- 회원가입 성별 선택 박스, 닉네임 변경 확인창(별도 버튼), 경기 일정 "선발 → 투수" 표기.
- 구장 상세의 "수집된 구장 안내" 섹션 제거.

## 5. 샘플 데이터 (`community.0010_local_sample_data`)

로컬에서 만든 검토용 데이터를 다른 컴퓨터에서도 `migrate`만으로 볼 수 있게 한다. 이미 있는 데이터는 건드리지 않는다.

- 계정: test1~5, master1은 기존 `accounts.0005`가 만든다(공통 비밀번호는 팀 공유 값). 여기서는 비어 있는 test2 닉네임만 채운다.
- 게시글: 한화 팀 게시판 "역사상 가장 위대한 선수"(test2). 사진 파일은 옮길 수 없어 글자만 넣는다.
- 신고: test3이 신고한 2건(#020051·새 샘플 글) → master1로 로그인해 마이페이지 "신고 관리"에서 확인.
- 개인 계정(실제 이메일)은 넣지 않았다.
- 전체 게시글 수가 351 → 352개가 되어 관련 테스트 기대값을 함께 바꿨다.

## 6. 확인 방법

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py test community accounts.test.test_admin_permissions llm.test_course_chain
docker compose exec frontend npm test
```
