import assert from "node:assert/strict";
import { after, test } from "node:test";
import { createRequire } from "node:module";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const frontend = dirname(dirname(fileURLToPath(import.meta.url)));
const scratch = mkdtempSync(join(tmpdir(), "kbo-details-test-"));
after(() => rmSync(scratch, { recursive: true, force: true }));
for (const name of ["details-types", "tving-details"]) {
  const { outputText } = ts.transpileModule(readFileSync(join(frontend, "lib", "kbo", `${name}.ts`), "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  });
  writeFileSync(join(scratch, `${name}.js`), outputText);
}
const requireTestModule = createRequire(join(scratch, "entry.cjs"));
const { parseTvingTeamDetail, parseTvingAthleteDetail } = requireTestModule("./tving-details.js");

const success = (data) => ({ code: "0000", message: "Success", data });
const player = (code, name) => ({ code, name, imageUrl: `https://image.tving.com/ntgs/sports/kbo/player/${code}.png`, backNumber: "NO.1" });
const rankings = (prefix) => success({ items: [{ title: prefix === "P" ? "다승" : "타율", athletes: [{ rank: 1, name: `${prefix}선수`, code: `${prefix === "P" ? "1" : "2"}0001`, value: "1.00" }, { rank: 2, name: "", code: "", value: "" }] }] });
const rosters = {
  pitcher: success({ items: [player("10001", "투수")] }),
  infielder: success({ items: [player("20001", "내야수")] }),
  outfielder: success({ items: [player("30001", "외야수")] }),
  catcher: success({ items: [player("40001", "포수")] }),
};
const teamPayload = () => success({
  teamImageUrl: "https://image.tving.com/ntgs/sports/kbo/team/LG.svg",
  backgroundImage: "https://image.tving.com/ntgs/sports/kbo/team/LG_DETAIL_PC.jpg",
  bands: [
    { bandType: "KBO_TEAM_SEASON_RECORD", bandName: "2026 시즌 1위", teamName: "LG 트윈스", teamShortName: "LG", items: [{ mainRecords: [{ title: "경기 수", value: "10" }], boxRecords: [{ title: "타율", value: "0.300" }] }] },
    { bandType: "SPORTS_CLIP_VERTICAL", bandName: "최신 영상", items: [{ videoUrl: "https://example.com/play" }] },
    { bandType: "SPORTS_TEAM_SCHEDULE", items: [{ code: "game-1", dateTime: 202609101830, stadium: "잠실", status: "PREV", away: { code: "LG", name: "LG", score: 0 }, home: { code: "OB", name: "두산", score: 0 } }] },
    { bandType: "SPORTS_TEAM_SHORTCUT", items: [{ code: "OB", name: "두산", imageUrl: "https://image.tving.com/ntgs/sports/kbo/team/OB.svg" }] },
  ],
});

test("team detail combines every nested ranking and roster tab while dropping video bands", () => {
  const parsed = parseTvingTeamDetail("LG", teamPayload(), { pitcher: rankings("P"), hitter: rankings("H") }, rosters);
  assert.equal(parsed.teamName, "LG 트윈스");
  assert.equal(parsed.rankings.pitcher[0].athletes.length, 1, "empty top-three placeholders are omitted");
  assert.equal(parsed.rankings.hitter[0].athletes[0].name, "H선수");
  assert.deepEqual(Object.fromEntries(Object.entries(parsed.rosters).map(([key, value]) => [key, value[0].name])), {
    pitcher: "투수", infielder: "내야수", outfielder: "외야수", catcher: "포수",
  });
  assert.equal(parsed.schedule[0].away.score, null, "placeholder scores for upcoming games are hidden");
  assert.doesNotMatch(JSON.stringify(parsed), /SPORTS_CLIP|videoUrl|최신 영상/);
});

const athleteProfile = (code = "68220") => ({
  bandType: "KBO_ATHLETE_PROFILE", items: [{ name: "곽빈", code, imageUrl: "https://image.tving.com/ntgs/sports/kbo/player/68220.png", positions: ["투수", "우투우타"], backNumber: "NO.47", joinDate: "2018년 01월", birthDate: "1999년 05월 28일", body: ["187cm", "95kg"], education: "배명고-두산", draftOrder: "두산 1차", team: { name: "두산 베어스", code: "OB", color: "#000038", logoUrl: "https://image.tving.com/ntgs/sports/kbo/team/OB.svg" } }],
});
const athletePayload = () => success({ bands: [
  athleteProfile(),
  { bandType: "KBO_ATHLETE_SEASON_RECORD", bandName: "2026 시즌 기록", items: [{ title: "평균자책", value: "2.26", rank: "1위", label: { isFirstRank: true }, graphRecords: [{ type: "line", graphs: [{ color: "#ED1C24", points: [{ xvalue: "9월", yvalue: "1.29", description: "2경기 1.29" }] }] }] }] },
  { bandType: "KBO_ATHLETE_WHOLE_RECORD", bandName: "통산 기록", column: [{ name: "시즌", variableName: "season" }, { name: "평균자책", variableName: "earnedRunAverage" }], items: [{ season: "통산", earnedRunAverage: "3.69" }, { season: "2026", earnedRunAverage: "2.26" }] },
  { bandType: "SPORTS_CLIP_VERTICAL", bandName: "선수 영상", items: [{ totalPlayTime: 30 }] },
] });

test("athlete detail keeps clickable graph points and complete career columns but no video data", () => {
  const parsed = parseTvingAthleteDetail("68220", athletePayload());
  assert.equal(parsed.profile.name, "곽빈");
  assert.deepEqual(parsed.seasonRecords[0].graphs[0].points[0], { x: "9월", y: "1.29", description: "2경기 1.29" });
  assert.deepEqual(parsed.careerRows[1], { season: "2026", earnedRunAverage: "2.26" });
  assert.doesNotMatch(JSON.stringify(parsed), /SPORTS_CLIP|totalPlayTime|선수 영상/);
});

test("a roster athlete with no appearance record is still collected as a valid profile", () => {
  const parsed = parseTvingAthleteDetail("52003", success({ bands: [athleteProfile("52003"), { bandType: "SPORTS_CLIP_VERTICAL", bandName: "선수 영상", items: [] }] }));
  assert.deepEqual(parsed.seasonRecords, []);
  assert.deepEqual(parsed.careerColumns, []);
  assert.deepEqual(parsed.careerRows, []);
});
