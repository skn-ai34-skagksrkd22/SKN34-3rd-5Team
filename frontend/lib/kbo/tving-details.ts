import {
  KBO_TEAM_CODES,
  type KboAthleteDetail, type KboAthleteProfile, type KboAthleteSeasonRecord,
  type KboCareerColumn, type KboCareerRow, type KboGraphRecord, type KboLabelValue,
  type KboRosterAthlete, type KboRosterPosition, type KboTeamAthleteType,
  type KboTeamCode, type KboTeamDetail, type KboTeamDetailGame,
  type KboTeamRankingGroup, type KboTeamShortcut,
} from "./details-types";

const TEAM_CODES = new Set<string>(KBO_TEAM_CODES);
const POSITIONS: KboRosterPosition[] = ["pitcher", "infielder", "outfielder", "catcher"];
const ATHLETE_TYPES: KboTeamAthleteType[] = ["pitcher", "hitter"];
type JsonObject = Record<string, unknown>;

function fail(message: string): never { throw new Error(`티빙 KBO 상세 응답 확인 실패: ${message}`); }
function object(value: unknown, field: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(field);
  return value as JsonObject;
}
function array(value: unknown, field: string, max = 1000): unknown[] {
  if (!Array.isArray(value) || value.length > max) fail(field);
  return value;
}
function safeText(value: unknown, field: string, max = 120, empty = false): string {
  if (typeof value !== "string") fail(field);
  const result = value.trim();
  if ((!empty && !result) || result.length > max || /[\p{Cc}\p{Cf}<>]/u.test(result)) fail(field);
  return result;
}
function optionalText(value: unknown, field: string, max = 500): string {
  return value === undefined || value === null || value === "" ? "" : safeText(value, field, max, true);
}
function imageUrl(value: unknown, field: string): string | null {
  if (value === undefined || value === null || value === "") return null;
  const result = safeText(value, field, 1000);
  let url: URL;
  try { url = new URL(result); } catch { fail(field); }
  if (url.protocol !== "https:" || url.hostname !== "image.tving.com") fail(field);
  return result;
}
function integer(value: unknown, field: string): number {
  if ((typeof value !== "number" && typeof value !== "string") || !/^\d+$/.test(String(value))) fail(field);
  const number = Number(value);
  if (!Number.isSafeInteger(number)) fail(field);
  return number;
}
function successData(payload: unknown): JsonObject {
  const response = object(payload, "응답 형식");
  if (response.code !== "0000") fail("상세 요청이 정상 처리되지 않았습니다");
  return object(response.data, "data");
}
function band(data: JsonObject, type: string): JsonObject {
  const bands = array(data.bands, "bands", 30).map((value) => object(value, "band"));
  const matches = bands.filter((item) => item.bandType === type);
  if (matches.length !== 1) fail(`${type} 누락 또는 중복`);
  return matches[0];
}
function optionalBand(data: JsonObject, type: string): JsonObject | null {
  const bands = array(data.bands, "bands", 30).map((value) => object(value, "band"));
  const matches = bands.filter((item) => item.bandType === type);
  if (matches.length > 1) fail(`${type} 중복`);
  return matches[0] ?? null;
}
function teamCode(value: unknown, field: string): KboTeamCode {
  const code = safeText(value, field, 2).toUpperCase();
  if (!TEAM_CODES.has(code)) fail(field);
  return code as KboTeamCode;
}
function records(value: unknown, field: string): KboLabelValue[] {
  return array(value, field, 30).map((entry) => {
    const item = object(entry, field);
    return { title: safeText(item.title, `${field} 이름`, 40), value: safeText(item.value, `${field} 값`, 60) };
  });
}
function rankingGroups(value: unknown): KboTeamRankingGroup[] {
  return array(value, "팀 내 순위", 30).map((entry) => {
    const group = object(entry, "팀 내 순위 항목");
    const athletes = array(group.athletes, "팀 내 순위 선수", 10).map((athleteValue) => {
      const athlete = object(athleteValue, "팀 내 순위 선수");
      const code = optionalText(athlete.code, "선수 코드", 40);
      const name = optionalText(athlete.name, "선수 이름", 80);
      if (!code || !name) return null;
      const rank = integer(athlete.rank, "팀 내 선수 순위");
      if (rank < 1 || rank > 10) fail("팀 내 선수 순위");
      return { rank, code, name, value: optionalText(athlete.value, "팀 내 선수 기록", 40), imageUrl: imageUrl(athlete.imageUrl, "선수 사진") };
    }).filter((athlete): athlete is NonNullable<typeof athlete> => athlete !== null);
    return { title: safeText(group.title, "팀 내 순위 이름", 40), athletes };
  });
}
function roster(value: unknown): KboRosterAthlete[] {
  const athletes = array(value, "선수단", 100).map((entry) => {
    const item = object(entry, "선수단 선수");
    return {
      code: safeText(item.code, "선수 코드", 40), name: safeText(item.name, "선수 이름", 80),
      imageUrl: imageUrl(item.imageUrl, "선수 사진"), backNumber: optionalText(item.backNumber, "등번호", 20),
    };
  });
  if (new Set(athletes.map((athlete) => athlete.code)).size !== athletes.length) fail("선수단 중복 선수");
  return athletes;
}
function compactDateTime(value: unknown): { startsAt: string; time: string } {
  const raw = String(integer(value, "경기 시각"));
  if (!/^\d{12}$/.test(raw)) fail("경기 시각 형식");
  const date = `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
  const time = `${raw.slice(8, 10)}:${raw.slice(10, 12)}`;
  const parsed = new Date(`${date}T${time}:00+09:00`);
  if (!Number.isFinite(parsed.getTime()) || Number(raw.slice(8, 10)) > 23 || Number(raw.slice(10, 12)) > 59) fail("경기 시각 형식");
  return { startsAt: `${date}T${time}:00+09:00`, time };
}
function gameTeam(value: unknown): KboTeamDetailGame["home"] {
  const item = object(value, "경기 팀");
  const scoreValue = item.score;
  const score = scoreValue === undefined || scoreValue === null ? null : integer(scoreValue, "점수");
  return { code: safeText(item.code, "경기 팀 코드", 3), name: safeText(item.name, "경기 팀 이름", 30), score };
}
function schedule(value: unknown): KboTeamDetailGame[] {
  return array(value, "팀 경기 일정", 30).map((entry) => {
    const item = object(entry, "팀 경기");
    const { startsAt, time } = compactDateTime(item.dateTime);
    const rawStatus = safeText(item.status, "경기 상태", 30);
    const showScore = ["NOW", "END", "SUSPENDED"].includes(rawStatus);
    const away = gameTeam(item.away); const home = gameTeam(item.home);
    if (!showScore) { away.score = null; home.score = null; }
    return { id: safeText(item.code, "경기 코드", 60), startsAt, time, stadium: safeText(item.stadium, "경기장", 50), status: rawStatus, away, home };
  });
}
function shortcuts(value: unknown): KboTeamShortcut[] {
  return array(value, "다른 구단", 10).map((entry) => {
    const item = object(entry, "다른 구단");
    return { code: teamCode(item.code, "다른 구단 코드"), name: safeText(item.name, "다른 구단 이름", 30), imageUrl: imageUrl(item.imageUrl, "구단 로고") };
  });
}

export function parseTvingTeamDetail(
  code: KboTeamCode, payload: unknown,
  nestedRankings: Record<KboTeamAthleteType, unknown>, nestedRosters: Record<KboRosterPosition, unknown>,
): KboTeamDetail {
  const data = successData(payload);
  const seasonBand = band(data, "KBO_TEAM_SEASON_RECORD");
  const scheduleBand = band(data, "SPORTS_TEAM_SCHEDULE");
  const shortcutBand = band(data, "SPORTS_TEAM_SHORTCUT");
  const seasonItems = array(seasonBand.items, "시즌 기록", 2);
  if (seasonItems.length !== 1) fail("시즌 기록");
  const season = object(seasonItems[0], "시즌 기록");
  const rankings = Object.fromEntries(ATHLETE_TYPES.map((type) => {
    const nested = successData(nestedRankings[type]);
    return [type, rankingGroups(nested.items)];
  })) as Record<KboTeamAthleteType, KboTeamRankingGroup[]>;
  const rosters = Object.fromEntries(POSITIONS.map((position) => {
    const nested = successData(nestedRosters[position]);
    return [position, roster(nested.items)];
  })) as Record<KboRosterPosition, KboRosterAthlete[]>;
  const allAthletes = POSITIONS.flatMap((position) => rosters[position]);
  if (new Set(allAthletes.map((athlete) => athlete.code)).size !== allAthletes.length) fail("포지션 간 중복 선수");
  return {
    code, teamName: safeText(seasonBand.teamName, "구단 이름", 50), shortName: safeText(seasonBand.teamShortName, "구단 짧은 이름", 30),
    teamImageUrl: imageUrl(data.teamImageUrl, "구단 로고"), backgroundImage: imageUrl(data.backgroundImage, "구단 배경"),
    seasonTitle: safeText(seasonBand.bandName, "시즌 제목", 80), mainRecords: records(season.mainRecords, "주요 기록"),
    boxRecords: records(season.boxRecords, "세부 기록"), schedule: schedule(scheduleBand.items), rankings, rosters,
    shortcuts: shortcuts(shortcutBand.items),
  };
}

function profile(value: unknown): KboAthleteProfile {
  const item = object(value, "선수 프로필");
  const team = object(item.team, "선수 소속팀");
  return {
    code: safeText(item.code, "선수 코드", 40), name: safeText(item.name, "선수 이름", 80),
    imageUrl: imageUrl(item.imageUrl, "선수 사진"),
    positions: array(item.positions, "선수 포지션", 8).map((position) => safeText(position, "선수 포지션", 40)),
    backNumber: optionalText(item.backNumber, "등번호", 20), joinDate: optionalText(item.joinDate, "입단일", 40),
    birthDate: optionalText(item.birthDate, "생년월일", 40),
    body: array(item.body ?? [], "신체", 5).map((entry) => safeText(entry, "신체", 30)),
    education: optionalText(item.education, "경력", 200), draftOrder: optionalText(item.draftOrder, "지명 순위", 100),
    team: { name: safeText(team.name, "소속팀 이름", 50), code: teamCode(team.code, "소속팀 코드"), color: optionalText(team.color, "소속팀 색상", 20), logoUrl: imageUrl(team.logoUrl, "소속팀 로고") },
  };
}
function graphRecords(value: unknown): KboGraphRecord[] {
  return array(value ?? [], "그래프 기록", 10).flatMap((groupValue) => {
    const group = object(groupValue, "그래프 기록");
    const type = safeText(group.type, "그래프 유형", 30);
    if (!["line_filled", "line", "dot", "bar"].includes(type)) fail("그래프 유형");
    return array(group.graphs, "그래프", 10).map((graphValue) => {
      const graph = object(graphValue, "그래프");
      return {
        type: type as KboGraphRecord["type"], color: optionalText(graph.color, "그래프 색상", 20),
        points: array(graph.points, "그래프 점", 100).map((pointValue) => {
          const point = object(pointValue, "그래프 점");
          return { x: safeText(point.xvalue, "그래프 X값", 60), y: safeText(point.yvalue, "그래프 Y값", 60), description: point.description === undefined || point.description === null || point.description === "" ? null : safeText(point.description, "그래프 설명", 100) };
        }),
      };
    });
  });
}
function seasonRecords(value: unknown): KboAthleteSeasonRecord[] {
  return array(value, "시즌 기록", 30).map((entry) => {
    const item = object(entry, "시즌 기록");
    const label = item.label === undefined ? {} : object(item.label, "기록 표시");
    return {
      title: safeText(item.title, "시즌 기록 이름", 60), value: safeText(item.value, "시즌 기록 값", 60),
      rank: item.rank === undefined || item.rank === null || item.rank === "" ? null : safeText(item.rank, "시즌 기록 순위", 40),
      isFirstRank: label.isFirstRank === true, graphs: graphRecords(item.graphRecords),
    };
  });
}
function careerColumns(value: unknown): KboCareerColumn[] {
  const columns = array(value, "통산 기록 열", 60).map((entry) => {
    const item = object(entry, "통산 기록 열");
    return { name: safeText(item.name, "통산 기록 열 이름", 40), key: safeText(item.variableName, "통산 기록 열 키", 60) };
  });
  if (!columns.length || columns[0].key !== "season" || new Set(columns.map((column) => column.key)).size !== columns.length) fail("통산 기록 열");
  return columns;
}
function careerRows(value: unknown, columns: KboCareerColumn[]): KboCareerRow[] {
  return array(value, "통산 기록 행", 100).map((entry) => {
    const item = object(entry, "통산 기록 행");
    return Object.fromEntries(columns.map((column) => [column.key, optionalText(item[column.key], `통산 기록 ${column.name}`, 60)]));
  });
}

export function parseTvingAthleteDetail(code: string, payload: unknown): KboAthleteDetail {
  const data = successData(payload);
  const profileBand = band(data, "KBO_ATHLETE_PROFILE");
  const seasonBand = optionalBand(data, "KBO_ATHLETE_SEASON_RECORD");
  const careerBand = optionalBand(data, "KBO_ATHLETE_WHOLE_RECORD");
  const profileItems = array(profileBand.items, "선수 프로필", 2);
  if (profileItems.length !== 1) fail("선수 프로필");
  const parsedProfile = profile(profileItems[0]);
  if (parsedProfile.code !== code) fail("요청 선수와 프로필이 다릅니다");
  const columns = careerBand ? careerColumns(careerBand.column) : [];
  return {
    profile: parsedProfile, seasonTitle: seasonBand ? safeText(seasonBand.bandName, "시즌 기록 제목", 80) : "시즌 기록",
    seasonRecords: seasonBand ? seasonRecords(seasonBand.items) : [], careerTitle: careerBand ? safeText(careerBand.bandName, "통산 기록 제목", 80) : "통산 기록",
    careerColumns: columns, careerRows: careerBand ? careerRows(careerBand.items, columns) : [],
  };
}

export function isKboTeamCode(value: string): value is KboTeamCode { return TEAM_CODES.has(value.toUpperCase()); }
export function isKboAthleteCode(value: string): boolean { return /^\d{4,12}$/.test(value); }
