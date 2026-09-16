# API 계약 관리

Django REST Framework serializer가 JSON 계약의 원본이다. `drf-spectacular`가 OpenAPI를 만들고 `openapi-typescript`가 프론트 타입을 생성한다.

## 파일과 명령

- `contracts/openapi.yaml`: 공개 경로 `/api/...`가 포함된 체크인 OpenAPI
- `frontend/lib/api/schema.d.ts`: OpenAPI에서 생성한 체크인 TypeScript 타입
- `frontend/lib/api/types.ts`: 스키마와 무관한 공통 `Page<T>` 및 오류 필드 타입
- `frontend/lib/api/client.ts`: JSON 응답/오류를 읽는 공통 transport

백엔드 의존성을 설치하고 프론트 의존성을 `npm ci`로 설치한 환경에서 실행한다. 활성 Python 환경 대신 특정 인터프리터를 쓰려면 `CONTRACT_PYTHON=/path/to/python`을 앞에 붙인다.

```bash
cd frontend
npm run contracts:generate
npm run contracts:check
CONTRACT_PYTHON=/path/to/python node --test tests/contracts-strict.test.mjs
```

두 명령은 `PYTHON_DOTENV_DISABLED=1`과 합성 DB/메일 설정으로 스키마를 생성하므로 실제 `.env`를 읽거나 DB/메일 네트워크를 사용하지 않는다. `contracts:generate`는 여러 domain이 annotation을 작성하는 중에도 부분 스키마를 갱신할 수 있지만 경고와 오류를 그대로 출력한다. `contracts:check`는 `--fail-on-warn`으로 schema 경고/오류가 하나라도 있으면 즉시 실패하며, 경고가 없을 때만 새 결과와 체크인 파일을 바이트 단위로 비교한다.

## 커뮤니티 임시저장·이미지 계약

- `GET|POST /api/community/drafts/`, `GET|PATCH|DELETE /api/community/drafts/{draft_id}/`는 JWT 소유자 범위다. 목록은 항상 `count`, `next`, `previous`, `results` 페이지 형태이며 링크는 공개 `/api` 경로를 사용한다.
- 초안은 제목·본문이 비어 있어도 저장할 수 있다. `PATCH`는 현재의 strict positive integer `revision`이 필수이고, 성공할 때 1 증가한다. `imageIds`는 중복 없는 본인 소유 미게시 이미지 UUID 최대 10개다.
- `POST /api/community/drafts/{draft_id}/publish/`는 현재 `revision` 본문과 `Idempotency-Key` 헤더가 필수다. 기존 게시글 serializer로 완전성을 검증하고, 행 잠금 아래 게시글·이미지·게시 이력을 원자적으로 저장한다. 같은 성공 요청은 `200`, 최초 성공은 `201`, 바뀐 키·revision·내용은 `409`다.
- 게시 실패는 초안과 첨부를 유지한다. 성공한 초안은 일반 CRUD에서 숨기되 `published_post`를 보존해 재시도를 복구한다.
- 게시글 삭제 시 소비된 초안도 함께 삭제해 삭제된 본문이 재게시되는 것을 막는다. 이미지 메타데이터는 남아 소유자가 정리할 수 있다.
- `POST /api/community/images/`는 `image` 하나만 받으며 임의 URL을 받지 않는다. 게시글 응답의 `images`는 서버가 보유한 `{id, contentType, size, width, height}` 읽기 전용 메타데이터다.
- 미연결·초안 이미지는 소유자만 읽고, 게시 이미지는 공개 읽기만 허용한다. 계정 삭제 후에도 이미지 메타데이터는 남지만 미연결 orphan의 자동 정리는 보존 정책이 정해질 때까지 의도적으로 제외한다.

## 서버 계약 작성 규칙

- serializer와 실제 view의 status/response를 먼저 맞춘 뒤 스키마 annotation을 추가한다. 포괄적인 공통 response envelope은 사용하지 않는다.
- Nginx가 `/api/`를 제거해 Django로 전달하므로 Django URL은 기존 경로를 유지하고 OpenAPI에만 `/api`를 삽입한다.
- 인증 endpoint는 기존 JWT `Authorization: Bearer <token>` 계약을 유지한다.
- 익명 코스 수정/삭제의 edit token은 요청 헤더와 검증 로직을 유지하며 생성 타입에 secret 값을 넣지 않는다.
- SSE endpoint는 `text/event-stream`과 스트림 body가 별도 계약이다. JSON transport로 읽거나 공통 JSON DTO로 감싸지 않는다.
- schema 생성의 `unable to guess serializer`와 method-field 경고는 해당 domain view/serializer가 annotation을 소유한다. 공통 생성기가 추측한 response로 경고를 숨기지 않는다.

## 프론트 공통 transport

`apiRequest<T>(path, init, fetcher)`와 `readApiResponse<T>(response)`는 `Promise<T | null>`을 반환한다. 인증 호출은 기존 `memberFetch`를 세 번째 인자로 주거나 그 결과를 `readApiResponse`에 전달해 JWT refresh/race 처리를 재사용한다.

`204`, `205`, `304`와 빈 성공 body는 `null`이다. 실패는 `ApiError`의 `status`, `fields`, `body`에 원래 HTTP 상태, DRF validation field, 파싱한 backend body를 보존한다. JSON이 아닌 성공 body는 안전한 `ApiError`가 되며 `AbortError`/`TimeoutError`는 transport가 감싸지 않는다.

DRF 기본 pagination만 `Page<T> = { count, next, previous, results }`를 사용한다. 배열을 직접 반환하거나 SSE처럼 특수한 endpoint에 pagination DTO를 강제로 적용하지 않는다.
