# accounts — 회원·인증·관리자 API

회원가입, JWT 로그인·갱신·로그아웃, 본인 프로필, 계정 복구, 이메일 변경 및 회원 권한 관리를 담당한다. 아래는 OpenAPI 설명만이 아니라 현재 view·serializer·service와 회귀 테스트를 기준으로 정리한 계약이다.

- [백엔드 안내](../../backend/README.md) · [프로젝트 안내](../../README.md)
- 등록 경로: [프로젝트 URLconf](../../backend/config/urls.py), [accounts URLconf](../../backend/accounts/urls.py)
- 구현: [인증 view](../../backend/accounts/views.py), [serializer](../../backend/accounts/serializers.py), [인증 service](../../backend/accounts/auth_service.py), [관리 API](../../backend/accounts/admin_views.py), [모델](../../backend/accounts/models.py), [인증 설정](../../backend/config/settings.py)

## 경로·인증·응답 공통 규칙

표의 URL은 **Django 직접 호출 기준**이다. Nginx 경유 시 앞에 `/api`를 붙인다. 예를 들어 `/auth/user`는 `/api/auth/user`가 된다. 끝 슬래시 유무도 표 그대로 사용한다. `/auth/logout/`, `/auth/user/`는 등록되어 있지 않다.

- JWT가 필요한 API: `Authorization: Bearer <access>`를 보낸다. 누락·만료·위조·비활성/삭제 사용자 토큰은 `401`; 인증된 사용자의 권한 부족은 `403`이다.
- 공개 함수형 API도 전역 JWT 인증을 수행하므로 불필요하게 잘못된 Authorization 헤더를 보내면 `401`이 될 수 있다. Simple JWT 기반 로그인·갱신·로그아웃 view는 헤더 인증을 수행하지 않는다.
- JSON 응답에 공통 `data` wrapper는 없다. 본문 없는 성공 응답과 `{}` 응답은 서로 다르다.
- 입력 오류는 보통 `400`의 필드별 오류 또는 `detail`/`non_field_errors`다. JWT 오류는 `detail`, `code` 등이 포함된다. 미지원 메서드는 `405`, 없는 경로/리소스는 `404`다.
- 메일 전송 실패를 정형화된 API 오류로 변환하는 별도 처리는 없다. 메일러 장애를 성공으로 가정하지 않는다.

## 모델과 데이터 경계

| 모델 | 역할·주요 필드 | 제약/노출 범위 |
|---|---|---|
| `CustomUser` | Django `AbstractUser` + `birth_date`, `gender`, `nickname`, `team_code`, `avatar`, `nickname_changed_at`, `notifications`, `visibility` | `username` unique. 이메일은 DB unique가 아니며 가입 단계에도 이메일 중복 차단이 없다. 비밀번호는 해시 저장, API 응답에 포함하지 않는다. |
| `EmailChangeChallenge` | UUID, 사용자 FK, 새 이메일, 코드 해시, 생성/만료/사용 시각, 실패 횟수 | 사용자 삭제 시 함께 삭제. 평문 인증 코드가 아닌 해시 저장. 사용자 소유·10분 만료·최대 5회 실패·1회 사용을 view에서 검증한다. |
| Simple JWT 토큰 모델 | outstanding/blacklist 기록 | 앱 자체 모델이 아니라 Simple JWT blacklist 앱 사용. 로그아웃과 만료 레코드 정리에 필요하다. |
| Django `LogEntry` | 관리자 `is_staff` 변경 기록 | 실제 값이 바뀐 경우에만 실행자, 대상, 변경 전후 값을 기록한다. |

## 인증·계정 API 전체

`회원` 응답은 아래 프로필 계약, `관리회원`은 관리자 계약에서 정의한다. 입력은 별도 명시가 없으면 JSON body다.

| 메서드·Django URL | 권한 | 입력 | 성공 | 주요 오류 |
|---|---|---|---|---|
| `POST /auth/signup/` | 공개 | `username`, `email`, `first_name`, `birth_date`, `gender`, `password`, `re_password` | `201`, 본문 없음 | `400` 필수값·형식·중복 아이디·비밀번호 정책/확인 불일치 |
| `POST /auth/signin` | 공개, 헤더 인증 없음 | `username`, `password` | `200 {access, refresh}` | `400` 입력 누락, `401` 로그인 실패/비활성 계정 |
| `POST /auth/token/refresh/` | refresh 소지, 헤더 인증 없음 | `refresh` | `200 {access}` | `400` 입력 오류, `401` 만료·폐기·잘못된 타입/서명·변경된 비밀번호·비활성/삭제 사용자 |
| `POST /auth/logout` | refresh 소지, 헤더 인증 없음 | `refresh` | `200 {}` | `400` 누락·빈 값·본문 형식, `401` 위조·만료·폐기·access 제출 |
| `GET /auth/user` | JWT 본인 | 없음 | `200 회원` | `401`; 토큰 누락 시 `{"detail":"인증이 필요합니다."}` |
| `PATCH /auth/user` | JWT 본인 | 허용된 프로필 필드 일부 | `200 회원` | `400` 변경 불가 필드·프로필 검증, `401` |
| `POST /auth/password/request` | 공개 | `email` | `200`, 본문 없음 | `400` 이메일 형식, `429` 동일 이메일 60초 제한 |
| `POST /auth/password` | JWT 본인 또는 유효한 재설정 링크 | 새 비밀번호와 확인; 로그인 방식은 현재 비밀번호, 재설정 방식은 body의 `uid`, `token` | `200`, 본문 없음 | `400` 잘못된 링크·비밀번호/확인·현재 비밀번호, `401` 인증수단 없음 |
| `POST /auth/username/request` | 공개 | `email` | `200 {"ok":true}` | `400` 이메일 형식, `429` 동일 이메일 60초 제한 |
| `POST /auth/email/request` | JWT 본인 | 새 `email` | `200 {request_id}` — UUID 문자열 | `400` 형식·다른 계정 이메일, `401`, `429` 사용자별 60초 재요청 제한 |
| `POST /auth/email/verify` | JWT 본인 | 문자열 `request_id`, 6자리 숫자 문자열 `code` | `200 {"verified":true,"email":…}` | `400` 형식·타인/없는 요청·만료·재사용·5회 실패·코드 불일치·이메일 중복, `401` |
| `GET /auth/admin/members/` | 활성 staff | query `q`, `page` | `200 {count,next,previous,results:[관리회원]}` | `401` 익명/JWT 실패, `403` 비관리자, `404` 페이지 범위 초과 |
| `PATCH /auth/admin/members/<int:pk>/role/` | 활성 staff이면서 superuser | 정확히 `{"is_staff":true}` 또는 `false` | `200 관리회원` | `400` 입력·비활성 대상, `401`, `403` 권한/대상 제한, `404` 없는 회원 |

### 회원가입과 비밀번호 정책

[SignupSerializer / PasswordValidationMixin](../../backend/accounts/serializers.py), [회원가입 테스트](../../backend/accounts/test/tests.py), [회원 통합 테스트](../../backend/accounts/test/test_member_integration.py)를 기준으로 한다.

- 아이디는 영문 대·소문자/숫자만 4~20자. 중복 검사와 저장 경쟁 중 `IntegrityError` 모두 `username` 오류로 응답한다.
- 이메일은 필수, 최대 254자. 이름 `first_name`은 빈 문자열 불가, 최대 150자. 생년월일은 날짜 형식이며 미래 날짜 불가. 성별은 `M` 또는 `F`.
- 비밀번호는 8~128자, 문자(`isalpha`)와 숫자(`isdigit`)를 각각 포함하고 공백 문자를 포함하지 않아야 한다. 오류 문구는 “영문자”라고 표현하지만 실제 검사는 ASCII 영문에 한정되지 않는다.
- 비밀번호와 확인값의 앞뒤 공백을 제거하지 않는다. Django의 유사도·최소 길이·흔한 비밀번호·숫자 전용 비밀번호 검사도 적용한다.
- 서버가 지정한 생성 필드만 저장하며 staff/superuser 권한을 가입 요청으로 부여하지 않는다. 가입 즉시 JWT를 반환하지 않으므로 별도 로그인해야 한다.

### 프로필 입력과 응답

`회원` 응답 필드:

`id`, `username`, `email`, `first_name`, `birth_date`, `gender`, `is_staff`, `is_superuser`, `is_active`, `nickname`, `team_code`, `avatar`, `nickname_changed_at`, `notifications`, `visibility`.

PATCH는 객체이며 다음 필드만 허용한다. 그 외 필드가 하나라도 있으면 `400`이며 아이디·이메일·권한·변경 시각을 직접 수정할 수 없다. 이메일은 별도 인증 절차를 사용한다.

| 입력 필드 | 실제 검증/동작 |
|---|---|
| `first_name`, `birth_date`, `gender` | 모델 기반 serializer 검증. 이름 최대 150자, 날짜 형식, 성별 `M/F`(모델의 blank/null 허용 범위 포함). **가입의 미래 생년월일 검증은 PATCH에 별도로 구현되어 있지 않다.** |
| `nickname` | trim 후 한글 완성형/영문만 1~12자, 숫자·공백 불가. 기존 값과 다른 값은 마지막 변경 후 KST 달력 기준 6개월이 지나야 변경 가능. 월말은 도착 월 마지막 날짜로 보정. 같은 값 제출은 변경 시각을 갱신하지 않는다. |
| `team_code` | 빈 문자열 또는 `LG, HH, SK, SS, NC, KT, LT, HT, OB, WO`. 대문자로 자동 변환하지 않는다. |
| `avatar` | 빈 문자열로 제거. 그 외 `data:image/jpeg;base64,` 접두어, 전체 문자열 600,000자 미만. 실제 JPEG 디코딩 성공, 가로·세로 각각 64~10,000, 총 4천만 픽셀 이하. 커뮤니티 이미지 API와 별개이며 재인코딩/EXIF 제거 처리는 없다. |
| `notifications` | 정확히 `comments`, `courses`, `announcements` 3개 키와 실제 JSON boolean 값 필요. 부분 객체 불가. 응답의 누락 키 기본값은 모두 `true`. |
| `visibility` | 정확히 `courses`, `posts`, `likes` 3개 키와 실제 JSON boolean 값 필요. 부분 객체 불가. 응답의 누락 키 기본값은 모두 `false`. |

빈 PATCH 객체는 허용된다. 설정 저장 자체가 다른 앱의 공개 접근 권한을 자동 집행한다는 뜻은 아니다.

### 비밀번호 변경·아이디 찾기·메일 변경

구현: [AuthService](../../backend/accounts/auth_service.py), [view](../../backend/accounts/views.py). 회귀 근거: [토큰 무효화 테스트](../../backend/accounts/test/test_tokens.py), [회원 통합 테스트](../../backend/accounts/test/test_member_integration.py).

- 로그인 변경: `current_password`, `new_password`, `new_password_confirm`을 보낸다. 기존 별칭 `old_password`, `password`, `re_password`도 지원하며 둘 다 있으면 새 이름의 값이 우선한다.
- 이메일 재설정: **JSON body**에 `uid`, `token`, `new_password`, `new_password_confirm`을 보낸다. view의 과거 주석과 달리 URL query의 `uid/token`만으로는 처리되지 않는다.
- `uid` 또는 `token` 중 하나라도 body에 있으면 재설정 방식으로 판단한다. 두 값 모두 필요하고, 로그인 상태여도 현재 비밀번호는 요구하지 않는다. 활성 사용자·사용 가능한 비밀번호·Django 재설정 토큰을 검사한다.
- 재설정 메일 링크는 `AUTH_FRONTEND_ORIGIN/login#uid=…&token=…`. 같은 이메일을 가진 활성 계정의 사용 가능한 비밀번호 계정마다 링크를 담는다. 아이디 찾기도 같은 이메일의 활성 계정 아이디를 메일로 안내한다.
- 없는 이메일도 정상 요청과 같은 성공 응답으로 계정 존재 여부를 노출하지 않는다. 아이디 찾기/재설정 메일 요청은 종류별·대소문자 무시 이메일별 캐시 60초 제한이며 분산 배포에서는 공유 캐시 구성이 중요하다.
- 비밀번호 변경은 사용자 행을 잠근 트랜잭션 안에서 검증·저장한다. 성공 후 재설정 링크와 해당 사용자의 기존 access/refresh가 무효화된다. 다른 사용자 토큰은 유지된다.
- 이메일 변경 요청은 다른 사용자와 대소문자 무시 중복을 검사한다. 새 요청 시 이전 미사용 요청은 소비 처리한다. 6자리 코드를 메일로 보내고 API에는 요청 UUID만 반환한다.
- 검증은 본인 요청만 가능하며 실패 횟수는 불일치마다 누적된다. 5회 실패 후 올바른 코드도 거부한다. 검증 직전에도 이메일 중복을 다시 검사한다. 다만 이메일 DB unique 제약은 없으므로 이를 전역 DB 유일성 보장으로 해석하면 안 된다.

## JWT 로그아웃 및 운영 계약

[JWT 설정](../../backend/config/settings.py), [logout 회귀 테스트](../../backend/accounts/test/test_logout.py), [password-aware refresh serializer](../../backend/accounts/serializers.py) 기준이다.

1. access 수명은 **5분**, refresh 수명은 **1일**. refresh rotation을 사용하지 않으며 갱신 응답에는 access만 온다.
2. 로그아웃은 body의 refresh를 blacklist에 등록한다. 본문 없는 로그아웃은 지원하지 않는다. 성공은 `200 {}`이며 같은 refresh 재전송은 `401`이다.
3. Authorization 헤더는 필요하지 않다. 잘못되거나 만료된 access 헤더가 있어도 body의 refresh를 검증한다.
4. **제출한 refresh만 폐기**한다. 같은 사용자의 다른 로그인 refresh는 유지되고, 이미 발급한 access도 남은 5분 이내 수명 동안 유효하다. 전 세션 로그아웃 API는 없다.
5. 클라이언트는 로그아웃 처리 후 저장한 access·refresh와 로그인 상태를 삭제해야 한다. 요청 실패를 서버 폐기 성공으로 간주하지 않는다.
6. 비밀번호 변경/재설정은 로그아웃과 다르게 비밀번호 해시 검증(`CHECK_REVOKE_TOKEN`)으로 기존 access와 refresh 모두 거부한다. 갱신에서도 커스텀 `PasswordAwareTokenRefreshSerializer`가 사용자 상태와 해시를 확인한다.
7. blacklist 앱 마이그레이션을 먼저 적용해야 한다. 토큰 원문은 로그/문서에 남기지 않는다. 운영 스케줄러에서 하루 한 번 만료 outstanding/blacklist 레코드를 정리한다. 저장소가 스케줄러를 자동 설치하지는 않는다.

프로젝트 루트 기준 운영 명령:

```bash
python backend/manage.py migrate
docker compose exec -T backend python manage.py flushexpiredtokens
```

## 관리자 API와 Django admin 구분

[관리 API](../../backend/accounts/admin_views.py)는 JWT JSON API이고 `/admin/`은 Django의 세션 기반 관리 웹사이트다.

- `관리회원` 응답: `id`, `username`, `is_active`, `is_staff`, `is_superuser`, `date_joined`. 비밀번호/해시·이메일·프로필은 관리 API 목록에 없다.
- 목록은 ID 오름차순, 페이지당 20명. `q`는 trim 후 150자로 자르고 아이디 부분 검색한다. ASCII 숫자 19자리 미만이면 회원 PK 일치 검색도 OR로 적용한다. 비활성 계정도 조회 대상이다. `page_size` 변경 옵션은 없다.
- 역할 PATCH는 `is_staff` 하나의 키와 실제 JSON boolean만 허용한다. 문자열 `"false"`, 추가 `is_superuser`, 배열 등은 `400`이다.
- 활성 staff+superuser만 변경 가능. 본인 또는 superuser 대상 변경은 `403`, 비활성 대상은 `400`. 값이 같으면 그대로 `200`이며 중복 감사 로그를 남기지 않는다.
- 일반 staff에게 권한 부여 권한이 없고, JSON API에 회원 삭제·활성화 변경·superuser 승격 경로는 등록되어 있지 않다.
- [CustomUserAdmin](../../backend/accounts/admin.py)은 Django `UserAdmin`을 상속한다. `/admin/accounts/customuser/`에서 회원을 조회·검색하며 실제 웹 접근/변경 권한은 Django admin 권한 체계를 따른다. JSON 역할 API의 master-only 제한을 admin 웹 전체의 추가 제한으로 오해하면 안 된다.
- 개발용 demo 기능이 켜진 경우 관리 화면에 fixture 확인용 비밀번호 열을 노출하는 코드가 있다. [관리 화면 테스트](../../backend/accounts/test/test_admin_site.py)는 DEBUG와 명시적 opt-in이 모두 필요함을 확인한다. 운영에서는 해당 기능을 활성화하지 않으며 이 문서에는 자격증명 값을 수록하지 않는다.

## 확인 근거와 테스트 실행

| 테스트 | 확인하는 계약 |
|---|---|
| [회원가입](../../backend/accounts/test/tests.py) | 필수 필드, 해시 저장, 비밀번호 정책/공백/확인값 |
| [JWT 로그아웃](../../backend/accounts/test/test_logout.py) | blacklist, 헤더 무시, 반복 폐기 거부, 다른 세션 유지, 슬래시·메서드 |
| [JWT 비밀번호 회귀](../../backend/accounts/test/test_tokens.py) | 재설정 링크, 두 방식의 비밀번호 변경, 기존 토큰 거부, inactive/deleted 사용자 |
| [프로필·복구·이메일](../../backend/accounts/test/test_member_integration.py) | allowlist, 닉네임 달력 6개월, 요청 소유/만료/실패 횟수/1회 사용, 계정 열거 방지 |
| [관리자 권한](../../backend/accounts/test/test_admin_permissions.py), [관리 화면](../../backend/accounts/test/test_admin_site.py) | staff/master 경계, 감사 로그, 웹 검색/접근 |
| [스키마](../../backend/accounts/test/test_schema.py), [설정](../../backend/accounts/test/test_settings.py) | wire 필드·본문 없음·메일러/JWT 설정 회귀 |

별도 PostgreSQL/pgvector 테스트 DB를 생성·삭제할 수 있는 **테스트 전용** 설정에서 실행한다. 운영 DB 계정으로 실행하지 않는다.

```bash
python backend/manage.py test accounts.test.test_logout accounts.test.test_tokens accounts.test.tests accounts.test.test_member_integration accounts.test.test_admin_permissions accounts.test.test_admin_site accounts.test.test_schema --noinput
```

`manage.py check`는 API 테스트를 대체하지 않는다. [Postman 컬렉션](../postman/auth.postman_collection.json)의 `01 자동 회귀`를 사용할 때 `base_url`은 직접 호출 `http://127.0.0.1:8000`, Nginx `http://localhost/api`이며 끝 `/`는 제외한다. 테스트 계정이 DB에 남으므로 테스트 환경에서만 실행하고 저장된 토큰은 삭제한 뒤 공유한다.

이 문서 작업에서는 소스와 테스트 정의를 확인했으며 DB/API 테스트를 새로 실행하지 않았다. 기존 상위 README의 “프론트 인증 화면 미구현” 문구는 백엔드 계약이 아니므로 현재 구현 상태로 단정하여 옮기지 않았다.
