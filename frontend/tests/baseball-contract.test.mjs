import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const resources = readFileSync(new URL("../lib/baseball/admin-resources.ts", import.meta.url), "utf8");
const writer = readFileSync(new URL("../components/route-writer.tsx", import.meta.url), "utf8");
const stadiums = readFileSync(new URL("../app/stadiums/page.tsx", import.meta.url), "utf8");
const detail = readFileSync(new URL("../app/stadiums/[code]/page.tsx", import.meta.url), "utf8");
const admin = readFileSync(new URL("../app/admin/baseball/page.tsx", import.meta.url), "utf8");
const client = readFileSync(new URL("../lib/baseball/client.ts", import.meta.url), "utf8");
const adapters = readFileSync(new URL("../lib/baseball/adapters.ts", import.meta.url), "utf8");
const types = readFileSync(new URL("../lib/baseball/types.ts", import.meta.url), "utf8");
const schema = readFileSync(new URL("../lib/api/schema.d.ts", import.meta.url), "utf8");

test("baseball admin exposes exactly the approved 19 fixed resources", () => {
  const names = [...resources.matchAll(/^\s*\["([a-z-]+)",/gm)].map(match => match[1]);
  assert.equal(names.length, 19);
  assert.equal(new Set(names).size, 19);
});

test("detail and admin keep scoped data paging and searchable relation controls", () => {
  // 구장 상세의 "수집된 구장 안내"(시즌·홈팀별 수집 자료 목록)는 화면에서 제거했다
  assert.doesNotMatch(detail, /수집된 구장 안내/);
  assert.match(admin, /관계 검색/);
  assert.match(client, /page_size: String\(pageSize\)/);
  assert.match(admin, /fetchAdminDetail\(name, id\)/);
  assert.match(admin, /const missing = relationIds\(selectedIds\)/);
  assert.match(admin, /results: \[\.\.\.selected, \.\.\.rows\]/);
  assert.match(adapters, /visual\?\.region \?\? "미분류"/);
  assert.doesNotMatch(adapters, /regionFor/);
  assert.doesNotMatch(stadiums, /return "서울";/);
});

test("stadium consumers load DB data and do not silently import the static array", () => {
  assert.match(writer, /fetchBaseballStadiums/);
  assert.doesNotMatch(writer, /import \{ stadiums \}/);
  assert.match(stadiums, /fetchBaseballStadiums/);
  assert.match(stadiums, /야구 정보 서버에 연결하지 못했어요|구장 정보를 불러오지 못했어요/);
});

test("repeated admin searches refresh and nullable stadium flags stay three-state", () => {
  const selectResource = admin.match(/  function selectResource\(name: AdminResourceName\) \{[\s\S]*?\n  \}/)?.[0] ?? "";
  assert.match(admin, /onSubmit=.*setReload\(item => item \+ 1\)/);
  assert.match(selectResource, /setReload\(item => item \+ 1\)/);
  assert.match(schema, /accessible\?: boolean \| null/);
  assert.match(schema, /reservation_required\?: boolean \| null/);
  assert.match(types, /FacilityDto as Facility/);
});
