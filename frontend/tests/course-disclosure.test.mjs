import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";

test("course save disclosures say courses are public and only edit access is browser-local", () => {
  const writer = readFileSync(new URL("../components/route-writer.tsx", import.meta.url), "utf8");
  const planner = readFileSync(new URL("../components/nearby-route-planner.tsx", import.meta.url), "utf8");
  const list = readFileSync(new URL("../app/routes/page.tsx", import.meta.url), "utf8");
  const detail = readFileSync(new URL("../app/routes/[id]/page.tsx", import.meta.url), "utf8");
  const mypage = readFileSync(new URL("../app/mypage/page.tsx", import.meta.url), "utf8");
  assert.match(writer, /코스는 코스 둘러보기에 공개되고 편집 권한만 이 브라우저에 저장돼요/);
  assert.match(planner, /저장한 코스는 코스 둘러보기에 공개돼요/);
  assert.doesNotMatch(writer, /다른 사용자에게 공개되지 않아요/);
  assert.doesNotMatch(planner, />이 브라우저에 저장돼요</);
  for (const source of [writer, list, detail, mypage]) assert.match(source, /이전 코스|이전 버전 코스/);
  assert.match(mypage, /useRoutesError/);
  assert.match(mypage, /retryRoutes/);
});

test("legacy editor keeps its instance while replacing the URL with the server id", () => {
  const writer = readFileSync(new URL("../components/route-writer.tsx", import.meta.url), "utf8");
  assert.match(writer, /legacySourceId === sourceId/);
  assert.match(writer, /key=.*legacySourceId.*sourceId/);
  assert.match(writer, /history\.replaceState/);
  assert.ok(writer.indexOf("history.replaceState") < writer.indexOf("savedRouteRef.current = persisted"));
  assert.doesNotMatch(writer, /if \(persisted\.saveWarning\).*return/);
  assert.match(writer, /description: persisted\.saveWarning/);
});
