# KMA live weather handoff

This replaces the cached Next.js design in `WEATHER_HANDOFF.md`. Weather is never persisted or cached: every callable or HTTP invocation makes one fresh KMA `getVilageFcst` request and returns the latest eligible published short-term forecast, not an instant sensor observation.

## Callable and HTTP contract

```python
from travel.weather_service import get_stadium_weather

weather = get_stadium_weather("JAMSIL", "2026-09-15", "18:30")
```

- Inputs are strict strings: canonical stadium code, real `YYYY-MM-DD`, real `HH:MM` in KST. The target is limited to the rolling interval from 24 hours ago through 120 hours ahead.
- The target forecast uses JavaScript `Math.round` half-hour behavior. A `18:30` game selects `19:00`.
- The issue is the newest cycle at least one hour before `min(now, target)`: `02/05/08/11/14/17/20/23`, including the previous-day `23:00` rollover.
- Return value is the weather object below or `None` when KMA has no matching target hour. Validation, configuration, provider transport, malformed response, and local concurrency errors are typed exceptions; no provider message, URL, or key is exposed.
- The nine static coordinates exactly match `data/preprocessed/stadium_coordinates.csv`; this deliberately avoids a DB dependency. A `SimpleTestCase` proves two identical calls make two provider calls and zero DB queries/writes.

Browser route after Nginx prefix stripping:

```http
GET /api/weather/?stadium=JAMSIL&date=2026-09-15&time=18%3A30
```

```json
{
  "weather": {
    "label": "구름많음",
    "temperature": 24.0,
    "forecastAt": "2026-09-15T19:00+09:00",
    "issuedAt": "2026-09-15T11:00+09:00",
    "fetchedAt": "2026-09-15T12:00:00+09:00",
    "source": "기상청 단기예보"
  }
}
```

No forecast is `{"weather": null}` with HTTP 200. Invalid input is 400, local concurrency exhaustion is 429, malformed/rejected provider data is 502, and missing configuration or unavailable provider transport is 503. Responses always send `Cache-Control: no-store`.

## Required shared-file integration

Apply this exact weather-only delta to `backend/travel/urls.py`:

```python
from .weather_views import StadiumWeatherView

urlpatterns = [
    path("weather/", StadiumWeatherView.as_view(), name="stadium-weather"),
    # existing course paths...
]
```

Apply these settings to `backend/config/settings.py`:

```python
KMA_SERVICE_KEY = os.getenv("KMA_SERVICE_KEY", "")
KMA_API_KEY = os.getenv("KMA_API_KEY", "")
```

Pass the server-only values to the backend service in `docker-compose.yml`; remove the frontend KMA value because the browser/Next process must never receive the key:

```yaml
backend:
  environment:
    KMA_SERVICE_KEY: ${KMA_SERVICE_KEY:-}
    KMA_API_KEY: ${KMA_API_KEY:-}
frontend:
  environment:
    # no KMA key
```

The existing generic Nginx `location /api/ { proxy_pass http://backend:8000/; }` already maps `/api/weather/` to Django `/weather/`; do not add a Next route or rewrite. No `EXTERNAL_DATA_SYNC_INTERVAL_SECONDS`, model, migration, scheduled sync, request cache, or stale DB fallback belongs in this integration.

Suggested generated DTO shape for `frontend/contracts/schema.d.ts` after regenerating the shared schema:

```ts
Weather: {
  label: string;
  temperature: number;
  forecastAt: string;
  issuedAt: string;
  fetchedAt: string;
  source: string;
};
WeatherResponse: { weather: components["schemas"]["Weather"] | null };
```

## Verification

```bash
docker exec -e DJANGO_SETTINGS_MODULE=travel.weather_test_settings kma-live-test \
  python -m django test travel.test_weather -v 2

docker run --rm -v "$PWD/frontend:/app" -v /app/node_modules -w /app \
  skn34-3rd-5team-frontend:latest node --test tests/weather-api.test.mjs
```

The disposable `kma-live-test` container is intentionally left running for coordinator checks. A real KMA smoke is valid only when an authorized key is supplied in memory; provider denial is not a successful live forecast.

Verified on 2026-09-15 with `skn34-3rd-5team-backend:latest` (Python 3.12.14, Django 6.1.1, DRF 3.18.0): 15/15 isolated Django tests passed with no database setup. The focused frontend test passed 4/4, the full frontend suite passed 340 with one skip, and the Next.js 16.3.4 production build completed. Loopback HTTP on `127.0.0.1:18077` returned sanitized JSON plus `Cache-Control: no-store` for invalid input (400) and an intentionally absent key (503). A separate authorized key supplied only through process memory reached KMA successfully and returned a non-null forecast with exactly `fetchedAt`, `forecastAt`, `issuedAt`, `label`, `source`, and `temperature`; no key, URL, or provider body was printed or written.
