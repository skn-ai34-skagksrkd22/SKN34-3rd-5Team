# 프론트엔드 → 백엔드 연동 인계서

## 2026-09-15 장소 검색 백엔드 계약

- 외부 경로는 `POST /api/places/search/`, Nginx가 `/api/`를 제거한 Django 경로는 `/places/search/`다.
- 요청은 기존 장소 검색 필드 `method`, `keyword?`, `category?`, `lat`, `lng`, `radius?`, `page`, `size`, `sort`만 보내며 기존 Next `action: "places"`는 보내지 않는다.
- 응답은 기존 `{ places, hasNextPage }`와 카카오 장소 ID 및 문자열 `x/y`를 유지하고 `syncedAt`을 추가한다. `syncedAt`은 공급자 조회 성공 시각이며 모든 DB 행의 저장 시각을 뜻하지 않는다. 오류는 `{ "error": "안전한 사용자 메시지" }`다.
- 브라우저에서 카카오 REST 키를 보내거나 Next `/directions-api`를 장소 검색 릴레이로 사용하지 않는다. 지도 JavaScript SDK와 Django 길찾기·TourAPI 경로는 별도 계약으로 유지한다.
- 공개 API는 장소 검색·목록·상세이고, POST/PATCH/DELETE CRUD는 기존 JWT의 활성 staff 관리자만 허용한다. 자세한 내부 함수 계약은 `docs/PLACE_TOOLS_HANDOFF.md`를 따른다.

작성 기준: 2026-09-10, `feat/front` 브랜치

이 문서는 현재 프론트엔드 프로토타입을 Django·PostgreSQL 백엔드와 연결할 때 필요한 계약과 작업 순서를 정리한다. 화면 디자인과 사용자 흐름은 구현되어 있지만 회원, 게시글, 좋아요, 조회 수, 커뮤니티는 아직 실제 서버에 저장되지 않는다.

## 1. 먼저 알아야 할 현재 상태

| 기능 | 현재 프론트 동작 | 백엔드 작업 |
| --- | --- | --- |
| 로그인·회원가입 | 입력 검증과 화면만 구현, 전송하지 않음 | 회원·세션·카카오 로그인 API 필요 |
| 루트 작성·목록·상세 | 브라우저 `localStorage`에 저장 | 게시글 CRUD, 작성자 권한, 페이지네이션 필요 |
| 좋아요·조회 수 | 브라우저별 임시 집계 | 사용자 기준 좋아요와 서버 조회 수 필요 |
| 팀별 자유게시판 | 샘플 글만 표시 | 팀 게시판 글·댓글 API 필요 |
| 챗봇 | Next 서버에서 데모/OpenAI/팀 백엔드로 전환 가능 | `POST /api/chat/` 계약만 맞추면 즉시 연결 가능 |
| 경기·팀 순위·개인 순위 | 브라우저가 `/api/tving/` Django API 조회 | TVING 검증과 조건부 PostgreSQL 저장 구현됨 |
| 구단·선수 상세 | Django on-demand 조회와 관계형 PostgreSQL 엔티티 | 전체 선수 자동 backfill 없음 |
| KBO 하이라이트 | Next 서버가 YouTube Data API로 조회 | 현재 유지 가능, 필요하면 백엔드 캐시로 이전 |
| 카카오맵 | 브라우저 JavaScript SDK 사용 | 도메인 등록 필요, 백엔드 API는 필수 아님 |
| CKEditor | 연결 어댑터만 준비, 일반 글쓰기 사용 | 도입 시 이미지 업로드 API 필요 |

프론트의 임시 서버 API는 다음 경로다.

- `/chat-api`
- `/youtube-api`

남은 위 경로들은 Next.js가 처리합니다. KBO와 날씨는 Nginx `/api/`가 Django로 직접 전달합니다.

백엔드 연결과 관계가 큰 화면 주소는 다음과 같다.

| 화면 | 주소 | 필요한 서버 데이터 |
| --- | --- | --- |
| 메인 | `/` | 당일 경기, 순위, 하이라이트, 팀 게시판 미리보기, 추천 루트 |
| 전체 일정 | `/schedule` | 2026년 월별 경기 |
| 순위·기록 | `/standings` | 팀 순위, 투수·타자 개인 순위 |
| 구단 상세 | `/standings/teams/{code}` | 구단 기록, 일정, 상위 선수, 포지션별 선수단 |
| 선수 상세 | `/standings/players/{code}` | 프로필, 시즌 그래프, 통산 기록 |
| 커뮤니티·루트 목록 | `/routes` | 루트 목록과 팀 게시판 글 |
| 루트 작성·수정 | `/routes/new`, `/routes/new?edit={id}` | 게시글 저장과 작성자 권한 |
| 루트 상세 | `/routes/{id}` | 본문, 지도 좌표, 좋아요, 조회 수 |
| 챗봇 | `/chat` | 대화 응답, 추후 대화 기록 |
| 하이라이트 | `/highlights` | YouTube 영상 목록 |

## 2. Docker와 요청 경로

루트의 `docker-compose.yml` 기준 서비스는 다음과 같다.

- 프론트: `frontend:3000`, 호스트 `http://localhost:3000`
- 백엔드: `backend:8000`, 호스트 `http://localhost:8000`
- PostgreSQL: `db:5432`
- Nginx: 호스트 `http://localhost`

Nginx는 `/api/` 요청을 Django로, 그 외 요청을 Next.js로 전달한다. 프론트에서는 운영 주소를 직접 적지 말고 아래처럼 상대 경로를 사용한다.

```ts
fetch("/api/routes/")
```

Docker 컨테이너 안에서 Next 서버가 Django를 직접 호출할 때만 `http://backend:8000/...` 주소를 사용한다. 예를 들어 현재 챗봇 중계 설정은 다음과 같다.

```dotenv
CHAT_PROVIDER=backend
CHAT_BACKEND_URL=http://backend:8000/api/chat/
```

같은 Nginx 도메인에서 Django 세션 쿠키를 쓰면 별도 CORS 설정을 최소화할 수 있다. 운영에서는 프록시 헤더, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, HTTPS 쿠키 설정을 실제 도메인에 맞춰야 한다.

## 3. 공통 API 규칙 제안

- JSON 필드는 `snake_case`로 통일한다.
- 날짜·시각은 ISO 8601 문자열로 전달한다. 저장은 UTC, KBO 일정 판단과 화면 표시는 `Asia/Seoul` 기준으로 한다.
- 목록은 `page`, `page_size`, `ordering`, `search` 쿼리를 사용한다.
- 인증 실패는 `401`, 권한 부족은 `403`, 없는 리소스는 `404`, 입력 오류는 `400`을 사용한다.
- 입력 오류는 필드별 메시지를 내려 프론트가 각 입력칸 아래에 표시할 수 있게 한다.

권장 오류 응답:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "입력값을 확인해 주세요.",
    "fields": {
      "username": ["이미 사용 중인 아이디입니다."]
    }
  }
}
```

권장 페이지 응답:

```json
{
  "count": 42,
  "next": "/api/routes/?page=2",
  "previous": null,
  "results": []
}
```

현재 KBO와 YouTube용 Next API는 `{ "data": ..., "error": null }` 형식을 사용한다. 이를 Django로 옮길 때 같은 형식을 유지하거나 프론트 어댑터를 함께 수정해야 한다.

## 4. 회원과 인증

### 필요한 API

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| `GET` | `/api/auth/csrf/` | 세션 로그인용 CSRF 쿠키 발급 |
| `POST` | `/api/auth/signup/` | 일반 회원가입 |
| `POST` | `/api/auth/login/` | 아이디·비밀번호 로그인 |
| `POST` | `/api/auth/logout/` | 로그아웃 |
| `GET` | `/api/auth/me/` | 현재 로그인 사용자 확인 |
| `POST` | `/api/auth/password/reset-request/` | 비밀번호 찾기 메일 요청 |
| `GET` | `/api/auth/kakao/start/` | 카카오 로그인 시작 |
| `GET` | `/api/auth/kakao/callback/` | 카카오 콜백 |

현재 화면의 회원가입 필드와 검증 조건은 다음과 같다.

| 필드 | 조건 |
| --- | --- |
| `username` | 영문·숫자 4~20자 |
| `password` | 8~128자, 숫자와 특수문자 각각 1개 이상 |
| `password_confirm` | 비밀번호와 일치 |
| `name` | 필수, 프론트 최대 40자 |
| `resident_front` | 숫자 6자리 |
| `resident_back` | 숫자 7자리. 화면에는 첫 숫자만 보이고 나머지는 가림 |
| `email` | 이메일 형식, 프론트 최대 254자 |
| `agreements.service` | 필수 |
| `agreements.privacy` | 필수 |
| `agreements.marketing` | 선택 |

회원가입 요청 예시:

```json
{
  "username": "baseball01",
  "password": "example!1",
  "password_confirm": "example!1",
  "name": "홍길동",
  "resident_front": "000000",
  "resident_back": "0000000",
  "email": "user@example.com",
  "agreements": {
    "service": true,
    "privacy": true,
    "marketing": false
  }
}
```

위 값은 형식 예시이며 실제 개인정보가 아니다.

주민등록번호는 현재 프론트에서 서버로 보내거나 저장하지 않는다. 전체 번호가 정말 필요한지 먼저 확정해야 한다. 가능하면 본인인증 사업자가 반환한 인증 결과와 최소 정보만 저장하고 전체 주민번호 저장은 피한다. 저장이 결정되면 암호화, 접근 권한, 로그 마스킹, 보유 기간과 삭제 정책을 백엔드에서 함께 설계해야 한다.

약관 동의는 단순 Boolean만 남기지 말고 약관 종류, 버전, 동의 시각을 기록한다. 마케팅 동의는 필수 약관과 분리해 철회할 수 있어야 한다.

세션 방식 권장 설정:

- Django 세션 쿠키는 `HttpOnly`
- 운영 HTTPS에서 `Secure`
- 동일 사이트 구성에서 `SameSite=Lax`
- 상태를 바꾸는 요청은 CSRF 토큰 검사

## 5. 직관 루트 게시글

현재 프론트 타입은 다음 구조다.

```ts
type RouteStop = {
  name: string;
  lat: number;
  lng: number;
  category: string;
};

type TripRoute = {
  id: string;
  title: string;
  stadium: string;
  description: string;
  content: string;
  contentFormat?: "html";
  tags: string[];
  duration: string;
  cover: string;
  stops: RouteStop[];
  author: string;
  likes: number;
  views?: number;
  isSample: boolean;
  createdAt: string;
};
```

입력 제한은 제목 80자, 본문 평문 기준 12,000자, 방문 장소 12개, 장소 이름 70자다. 위도는 -90~90, 경도는 -180~180 범위를 검사한다. `stops` 배열 순서가 지도 마커와 Polyline의 방문 순서다.

### 필요한 API

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| `GET` | `/api/routes/` | 목록, 검색, 구장 필터, 정렬, 페이지네이션 |
| `POST` | `/api/routes/` | 로그인 사용자의 루트 작성 |
| `GET` | `/api/routes/{id}/` | 상세 조회 |
| `PATCH` | `/api/routes/{id}/` | 작성자 본인 수정 |
| `DELETE` | `/api/routes/{id}/` | 작성자 본인 삭제 |
| `POST` | `/api/routes/{id}/like/` | 좋아요 추가 |
| `DELETE` | `/api/routes/{id}/like/` | 좋아요 취소 |
| `POST` | `/api/routes/{id}/view/` | 조회 수 기록 |

목록 쿼리 예시:

```text
GET /api/routes/?page=1&page_size=10&search=잠실&stadium=JAMSIL&ordering=-created_at
```

작성 요청 예시:

```json
{
  "title": "잠실 직관 하루",
  "stadium_code": "JAMSIL",
  "description": "경기 전 산책부터 직관까지",
  "content": "<p>석촌호수를 걷고 야구장으로 이동합니다.</p>",
  "content_format": "html",
  "tags": ["첫 직관", "산책"],
  "duration": "경기 전후 반나절",
  "stops": [
    {
      "order": 1,
      "name": "석촌호수",
      "lat": 37.507,
      "lng": 127.102,
      "category": "산책"
    }
  ]
}
```

백엔드는 `author`, `likes`, `views`, `created_at`, 소유 여부를 요청값으로 믿지 말고 서버에서 결정한다. 상세 응답에는 프론트가 수정·삭제 버튼을 판단할 수 있도록 `is_owner`, `is_liked`를 포함하는 편이 좋다.

현재 임시 저장 키는 다음과 같다.

- `kbo-trip-routes-v1`
- `kbo-trip-likes-v1`
- `kbo-trip-views-v1`

API 연결 시 기존 로컬 글을 폐기할지, 로그인 후 한 번 가져올지 팀에서 결정해야 한다. 자동 업로드한다면 중복 방지를 위한 클라이언트 ID를 함께 보낸다.

본문은 일반 텍스트와 CKEditor HTML을 모두 읽을 수 있다. HTML을 저장할 때 서버에서 허용 태그·속성을 기준으로 정화하여 XSS를 차단해야 한다.

## 6. 팀별 자유게시판

현재 팀 코드는 다음 값으로 고정되어 있다.

```text
LG, HH, SK, SS, NC, KT, LT, HT, OB, WO
```

화면의 글 분류는 `응원`, `직관`, `질문`, `잡담`이다. 홈은 실시간 순위 상위 6개 팀을 먼저 보여주고 `MORE`를 누르면 나머지 팀을 보여준다. 각 팀 영역에는 글 5개가 필요하다.

### 필요한 API

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| `GET` | `/api/community/posts/` | 팀·분류별 글 목록 |
| `POST` | `/api/community/posts/` | 글 작성 |
| `GET` | `/api/community/posts/{id}/` | 글 상세 |
| `PATCH` | `/api/community/posts/{id}/` | 작성자 본인 수정 |
| `DELETE` | `/api/community/posts/{id}/` | 작성자 본인 삭제 |
| `GET` | `/api/community/posts/{id}/comments/` | 댓글 목록 |
| `POST` | `/api/community/posts/{id}/comments/` | 댓글 작성 |
| `GET` | `/api/community/preview/` | 홈의 여러 팀 글을 한 번에 조회 |

홈에서 팀마다 API를 따로 호출하지 않도록 미리보기 일괄 조회를 권장한다.

```text
GET /api/community/preview/?team_codes=SS,KT,LG,HT,OB,NC&limit=5
```

응답은 팀 코드별 글 배열이면 된다.

```json
{
  "data": {
    "SS": [{ "id": 1, "category": "응원", "title": "오늘도 파이팅!" }],
    "KT": []
  }
}
```

## 7. 챗봇 연동 계약

프론트 브라우저는 `/chat-api`만 호출한다. Next 서버가 `CHAT_PROVIDER` 값에 따라 데모, OpenAI, 팀 백엔드 중 하나로 전달한다. 팀 백엔드가 아래 계약을 구현하면 프론트 UI를 바꾸지 않고 연결할 수 있다.

```text
POST /api/chat/
Content-Type: application/json
```

요청:

```json
{
  "messages": [
    { "role": "user", "content": "잠실 첫 직관 코스를 추천해 줘" }
  ],
  "context": {
    "stadium": "잠실야구장",
    "intent": "route"
  }
}
```

응답:

```json
{
  "reply": "잠실야구장에 가기 전 석촌호수를 산책해 보세요."
}
```

검증 제한:

- 최근 메시지 최대 12개
- 사용자 메시지 최대 2,000자
- 응답 최대 8,000자
- 요청 본문 최대 64KB
- 마지막 메시지는 반드시 `user`
- `intent`: `route`, `baseball`, `stadium` 중 하나
- 공급자 호출 제한 25초, 브라우저 전체 제한 30초

현재는 SSE 스트리밍을 사용하지 않는 단일 JSON 응답 방식이다. 첫 연동은 이 계약으로 완료하고, SSE를 추가할 때 프론트 전송·중단 처리와 백엔드 스트림 형식을 함께 변경한다.

현재 Next의 제한은 프로세스당 분당 20건, 동시 3건인 로컬 보호 장치다. 운영 백엔드는 로그인 사용자와 IP 기준 제한을 공용 저장소에서 적용해야 한다. 대화 기록도 현재 React 상태에만 있으므로 계정별 기록이 필요하면 `conversation`과 `message` 모델을 추가한다.

RAG 답변에 출처를 표시하려면 추후 응답을 아래처럼 확장하고 프론트 `ChatReply` 타입도 함께 수정한다.

```json
{
  "reply": "...",
  "sources": [
    { "title": "구장 반입 규정", "url": "..." }
  ]
}
```

## 8. KBO 일정·순위·구단·선수 데이터

TVING 네트워크·검증·저장은 Django `tving` 앱이 소유합니다. 브라우저는 `/api/tving/daily/`, `/api/tving/schedule/`, `/api/tving/details/teams/{code}/`, `/api/tving/details/athletes/{code}/`를 호출합니다. Next의 `/kbo-api` route, 프로세스 timer와 `.cache/kbo` 파일 저장은 제거됐습니다.

각 명시적 조회는 공급자를 새로 호출하며 `EXTERNAL_DATA_SYNC_INTERVAL_SECONDS`(기본 600초)는 entity별 DB 쓰기만 억제합니다. 기존 `Team`·`Game`·`StandingHistory`를 재사용하고 TVING과 CSV가 겹치면 TVING provenance 한 행만 유지합니다. 전체 계약과 callable CRUD/search 도구는 `frontend/docs/KBO_DATA.md`와 `docs/TVING_TOOLS_HANDOFF.md`를 기준으로 합니다.

정확한 필드 타입은 다음 프론트 파일을 계약 기준으로 본다.

- `frontend/lib/kbo/types.ts`
- `frontend/lib/kbo/details-types.ts`

외부 TVING 주소는 공개 개발자용 API가 아니라 웹사이트 내부 응답이므로 주소나 형식이 바뀔 수 있다. 원본 수집 코드와 예외 조건은 `frontend/docs/KBO_DATA.md`에 정리되어 있다.

브라우저는 현재 KBO 프리뷰를 약 60초마다 다시 요청한다. 백엔드로 옮긴 직후에도 이 방식을 유지할 수 있으며 SSE는 필수 조건이 아니다.

## 9. YouTube, 카카오맵, CKEditor

### YouTube 하이라이트

`YOUTUBE_API_KEY`는 현재 Next 서버 전용 값이다. 브라우저에 노출되는 `NEXT_PUBLIC_` 접두사를 붙이지 않는다. `/youtube-api?limit=3`은 메인, `limit=12`는 하이라이트 게시판에서 사용한다. 응답 타입은 `frontend/lib/youtube/types.ts`에 있다.

백엔드로 옮긴다면 `GET /api/highlights/?limit=12`를 만들고 최소 10분 캐시를 둔다. `videoId`, 제목, 게시 시각, 채널명, URL, 썸네일, 재생 시간, 조회 수를 현재 형식으로 반환하면 된다.

### 카카오맵

- `NEXT_PUBLIC_KAKAO_MAP_KEY`: 프론트 브라우저 JavaScript 키
- `KAKAO_REST_API_KEY`: 백엔드 수집·장소 검색용 서버 키

두 키는 용도가 다르다. 카카오 개발자 콘솔의 웹 도메인에 로컬 `http://localhost:3000`, Nginx `http://localhost`, 실제 배포 origin을 각각 등록한다.

### CKEditor

현재는 `NEXT_PUBLIC_CKEDITOR_LICENSE_KEY`가 없어 일반 textarea를 사용한다. CKEditor를 활성화해 이미지 업로드까지 지원하려면 인증된 `POST /api/uploads/images/`를 구현하고 파일 크기, MIME, 저장 경로를 검사한다. 업로드 응답 형식은 최종 CKEditor upload adapter와 함께 확정한다.

## 10. 환경변수 소유권

실제 값은 Git에 올리지 않는다. `frontend/.env.local`, 루트 `.env`, `.cache`, `node_modules`, `.next`는 커밋 대상이 아니다.

| 변수 | 사용 위치 | 공개 여부 |
| --- | --- | --- |
| `CHAT_PROVIDER` | Next 서버 | 비공개 설정 |
| `CHAT_BACKEND_URL` | Next 서버 | 비공개 설정 |
| `OPENAI_MODEL` | Next 또는 챗봇 백엔드 | 비공개 설정 |
| `OPENAI_API_KEY` | Next 또는 챗봇 백엔드 | 비밀 |
| `YOUTUBE_API_KEY` | Next 또는 백엔드 | 비밀 |
| `EXTERNAL_DATA_SYNC_INTERVAL_SECONDS` | Django TVING·길찾기·장소·관광 entity | 비공개 설정, 기본 600초 |
| `KMA_SERVICE_KEY` / `KMA_API_KEY` | Django 날씨 live 조회 | 비밀, 프론트 전달 금지 |
| `NEXT_PUBLIC_KAKAO_MAP_KEY` | 브라우저 | 공개되는 키, 도메인 제한 필요 |
| `NEXT_PUBLIC_CKEDITOR_LICENSE_KEY` | 브라우저 | 번들에 포함됨, 라이선스 정책 확인 |
| `KAKAO_REST_API_KEY` | Django 장소 검색·길찾기 | 비밀 |
| `EXTERNAL_DATA_SYNC_INTERVAL_SECONDS` | Django 외부 데이터 DB 재기록 간격(기본 600초) | 비공개 설정 |
| `DJANGO_SECRET_KEY` | Django | 비밀 |
| `DATABASE_URL` 또는 `DB_*` | Django | 비밀 |
| `ALLOWED_HOSTS` | Django | 환경별 설정 |
| `CSRF_TRUSTED_ORIGINS` | Django | 환경별 설정 |

현재 `frontend/.env.example`은 작업 트리에서 삭제된 상태이므로 커밋 전에 팀이 공유할 예시 파일을 다시 정리할지 결정해야 한다. 실제 키가 들어간 `.env.local`은 계속 Git 제외 상태로 둔다.

## 11. Django 쪽 현재 선행 문제

현재 `backend/config/urls.py`는 다음 import를 사용한다.

```py
from api.views import test_api
```

하지만 저장소에 `backend/api/` 패키지가 없어 현재 상태로는 Django가 시작될 때 import 오류가 발생할 수 있다. 먼저 실제 API 앱을 만들거나 URL import를 수정해야 한다.

추가로 확인된 항목:

- `djangorestframework`는 설치되어 있지만 `INSTALLED_APPS`에 `rest_framework`가 없다.
- `SECRET_KEY`, `DEBUG`, DB 접속 정보가 `settings.py`에 직접 들어 있다.
- `ALLOWED_HOSTS`가 비어 있다.
- `TIME_ZONE`이 `UTC`다. 저장은 UTC로 유지할 수 있지만 KBO 스케줄러의 판단 기준은 `Asia/Seoul`로 명시해야 한다.
- 헬스 체크 API와 실제 앱 모델·migration이 아직 없다.

우선 `GET /api/health/`가 Docker와 Nginx 양쪽에서 200을 반환하도록 만든 다음 기능 API를 연결하는 편이 안전하다.

## 12. 추천 DB 모델

최소 모델 구성:

- `User` 또는 프로젝트용 custom user
- `PolicyAgreement`
- `RoutePost`
- `RouteStop`
- `RouteLike`
- `RouteViewEvent` 또는 집계 필드
- `CommunityPost`
- `CommunityComment`
- `ChatConversation`, `ChatMessage` (대화 저장이 필요할 때)
- `KboTeam`, `KboGame`, `KboStandingSnapshot`
- `KboAthlete`, `KboAthleteSeasonRecord`, `KboAthleteCareerRow`
- `CollectionRun`

`RouteLike`에는 `(user_id, route_id)` unique 제약을 둔다. 경기·구단·선수는 외부 source code를 unique key로 사용한다. 삭제 정책과 작성자 표시 정책은 회원 탈퇴 처리와 함께 정한다.

## 13. 연결 순서

1. Django 앱 생성, 설정 환경변수화, `/api/health/` 확인
2. 회원가입·로그인·로그아웃·`me`와 CSRF 연결
3. 루트 CRUD와 장소 순서, 작성자 권한 연결
4. 좋아요·조회 수와 목록 검색·정렬·페이지네이션 연결
5. 팀별 게시판·댓글·홈 미리보기 연결
6. `/api/chat/` 계약 구현 후 `CHAT_PROVIDER=backend`로 전환
7. KBO 수집기를 단일 워커와 PostgreSQL로 이전하고 기존 응답 형식 유지
8. 필요하면 YouTube 캐시와 CKEditor 이미지 업로드를 백엔드로 이전

## 14. 인수 확인 체크리스트

- [ ] `docker compose up -d --build` 후 `http://localhost`, `:3000`, `:8000` 확인
- [ ] Nginx를 거친 `GET /api/health/`가 200 반환
- [ ] 로그인 후 새로고침해도 세션 유지
- [ ] 다른 사용자의 루트 수정·삭제는 403
- [ ] 좋아요 중복 생성 방지
- [ ] 루트 장소 순서와 좌표가 상세 지도에 동일하게 복원
- [ ] 팀별 게시판 홈 미리보기가 한 번의 API 요청으로 조회
- [ ] 챗봇 백엔드가 `{ "reply": "..." }` 반환
- [ ] 수집 워커가 여러 웹 인스턴스에서 중복 실행되지 않음
- [ ] 경기 결과 저장 후 최종 순위 재확인 로직 유지
- [ ] `.env.local`, API 키, KBO `.cache`, 개인정보가 Git에 포함되지 않음

## 15. 관련 파일

- 프론트 전체 현황: [`frontend/docs/UIUX_PROGRESS.md`](../frontend/docs/UIUX_PROGRESS.md)
- 챗봇 연결: [`frontend/docs/CHAT_SETUP.md`](../frontend/docs/CHAT_SETUP.md)
- KBO 수집 정책: [`frontend/docs/KBO_DATA.md`](../frontend/docs/KBO_DATA.md)
- 루트 임시 저장·타입: [`frontend/lib/routes.ts`](../frontend/lib/routes.ts)
- 챗봇 요청 타입: [`frontend/lib/chat/types.ts`](../frontend/lib/chat/types.ts)
- KBO 일정·순위 타입: [`frontend/lib/kbo/types.ts`](../frontend/lib/kbo/types.ts)
- KBO 구단·선수 타입: [`frontend/lib/kbo/details-types.ts`](../frontend/lib/kbo/details-types.ts)
- YouTube 타입: [`frontend/lib/youtube/types.ts`](../frontend/lib/youtube/types.ts)
- Nginx 분기: [`nginx/nginx.conf`](../nginx/nginx.conf)
- Docker 구성: [`docker-compose.yml`](../docker-compose.yml)
