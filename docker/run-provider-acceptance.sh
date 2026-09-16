#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose="$repo/docker/tving-backend-test.compose.yml"
work=$(mktemp -d "${TMPDIR:-/tmp}/provider-acceptance.XXXXXX")
trap 'rm -rf "$work"' EXIT

docker compose -p tving-backend-test -f "$compose" exec -T backend \
  python manage.py test tving.tests travel.tests travel.test_external travel.test_tourism travel.test_weather travel.test_places community.test_predictions --verbosity 1
docker compose -p tving-backend-test -f "$compose" exec -T -e DJANGO_SETTINGS_MODULE=baseball.tests.import_settings backend \
  python -m django test baseball.tests.test_import --verbosity 1
docker compose -p tving-backend-test -f "$compose" exec -T -e DJANGO_SETTINGS_MODULE=baseball.tests.api_settings backend \
  python -m django test baseball.tests.test_api --verbosity 1
docker compose -p tving-backend-test -f "$compose" exec -T backend \
  python manage.py makemigrations --check --dry-run
docker compose -p tving-backend-test -f "$compose" exec -T backend \
  python manage.py spectacular --file /tmp/provider-openapi.yaml --validate --fail-on-warn

backend_container=$(docker compose -p tving-backend-test -f "$compose" ps -q backend)
docker cp "$backend_container:/tmp/provider-openapi.yaml" "$work/openapi.yaml"
cmp "$repo/contracts/openapi.yaml" "$work/openapi.yaml"

"$repo/frontend/node_modules/.bin/openapi-typescript" "$work/openapi.yaml" --output "$work/schema.d.ts"
cmp "$repo/frontend/lib/api/schema.d.ts" "$work/schema.d.ts"

cd "$repo/frontend"
npm test
npm run lint
npm run build
