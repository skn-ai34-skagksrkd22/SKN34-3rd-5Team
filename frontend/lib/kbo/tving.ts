import type {
  KboAthleteRankingBase, KboGame, KboGameStatus, KboHitterRanking,
  KboIndividualRankings, KboPitcherRanking, KboStanding,
} from "./types";

// These are the public statistics requests used by TVING's KBO schedule and
// ranking pages. No member cookie, playback endpoint, or API credential is used.
const TEAM_NAMES: Record<string, string> = {
  SS: "삼성", KT: "KT", LG: "LG", HT: "KIA", OB: "두산",
  NC: "NC", HH: "한화", LT: "롯데", SK: "SSG", WO: "키움",
};
// The public 2026-07-11 schedule includes the All-Star game (WE vs EA).
// These teams may appear in games, but never in the ten-club regular-season table.
const SCHEDULE_TEAM_NAMES: Record<string, string> = { ...TEAM_NAMES, WE: "나눔", EA: "드림" };
const STATUS: Record<string, { status: KboGameStatus; label: string }> = {
  PREV: { status: "scheduled", label: "경기 예정" },
  READY: { status: "scheduled", label: "경기 준비" },
  NOW: { status: "live", label: "경기 중" },
  END: { status: "final", label: "경기 종료" },
  CANCEL: { status: "cancelled", label: "경기 취소" },
  SUSPENDED: { status: "suspended", label: "경기 중단" },
};
type JsonObject = Record<string, unknown>;

function fail(message: string): never {
  throw new Error(`티빙 KBO 응답 확인 실패: ${message}`);
}

function object(value: unknown, field: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(field);
  return value as JsonObject;
}

function string(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) fail(field);
  return value.trim();
}

function integer(value: unknown, field: string): number {
  if (typeof value !== "number" && typeof value !== "string") fail(field);
  if (!/^\d+$/.test(String(value))) fail(field);
  const result = Number(value);
  if (!Number.isSafeInteger(result)) fail(field);
  return result;
}

function decimal(value: unknown, field: string, max?: number): string {
  const result = string(value, field);
  if (!/^\d+(?:\.\d+)?$/.test(result) || !Number.isFinite(Number(result))) fail(field);
  if (max !== undefined && Number(result) > max) fail(field);
  return result;
}

function safeText(value: unknown, field: string, maxLength = 60): string {
  const result = string(value, field);
  if (result.length > maxLength || /[\p{Cc}\p{Cf}<>]/u.test(result)) fail(field);
  return result;
}

function statistic(value: unknown, field: string): string {
  const result = string(value, field);
  if (result.length > 24 || !/^-?\d+(?:\.\d+)?$/.test(result) || !Number.isFinite(Number(result))) fail(field);
  return result;
}

function innings(value: unknown): string {
  const result = string(value, "이닝");
  if (!/^\d+(?: [12]\/3)?$/.test(result)) fail("이닝");
  return result;
}

function athleteBase(item: JsonObject): KboAthleteRankingBase {
  const player = safeText(item.name, "선수 이름");
  const playerCode = safeText(item.code, "선수 코드", 40);
  const teamName = safeText(item.teamName, "선수 소속팀", 20);
  const teamCode = Object.keys(TEAM_NAMES).find(code => TEAM_NAMES[code] === teamName);
  const rank = integer(item.rank, "개인 순위");
  if (!teamCode || rank < 1 || rank > 500) fail("선수 순위 정보");
  return { rank, playerCode, player, teamCode, team: teamName };
}

function athleteItems(payload: unknown, label: string): JsonObject[] {
  const items = successData(payload).items;
  if (!Array.isArray(items) || items.length < 1 || items.length > 500) fail(`${label} 개인 순위 목록`);
  return items.map(value => object(value, `${label} 개인 순위`));
}

function compactDate(date: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) fail("요청 날짜");
  const parsed = new Date(`${date}T00:00:00Z`);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date) fail("요청 날짜");
  return date.replaceAll("-", "");
}

function successData(payload: unknown): JsonObject {
  const response = object(payload, "응답 형식");
  if (response.code !== "0000") fail("통계 요청이 정상 처리되지 않았습니다");
  return object(response.data, "data");
}

function band(payload: unknown, kind: string): JsonObject {
  const data = successData(payload);
  if (!Array.isArray(data.bands)) fail("bands 누락");
  const matches = data.bands.filter((item) => object(item, "band").bandType === kind);
  if (matches.length !== 1) fail(`${kind} 누락 또는 중복`);
  return object(matches[0], kind);
}

function team(value: unknown, showScore: boolean): KboGame["home"] {
  const item = object(value, "경기 팀");
  const name = string(item.name, "팀 이름");
  const code = typeof item.code === "string" ? item.code : Object.keys(SCHEDULE_TEAM_NAMES).find((key) => SCHEDULE_TEAM_NAMES[key] === name);
  if (!code || SCHEDULE_TEAM_NAMES[code] !== name) fail("알 수 없는 팀");
  const pitcherName = typeof item.pitcherName === "string" ? item.pitcherName.trim() : "";
  // Pitcher announcements are optional. Missing or malformed ancillary fields
  // must not erase a valid game or invent a player name.
  const startingPitcher = pitcherName && pitcherName.length <= 60
    && !/[\p{Cc}\p{Cf}<>]/u.test(pitcherName)
    && !/^(?:-|—|미정|미발표|TBD|N\/A)$/iu.test(pitcherName)
    ? pitcherName : null;
  return { code, name, score: showScore ? integer(item.score, "경기 점수 누락") : null, startingPitcher };
}

function game(value: unknown, date: string): KboGame {
  const item = object(value, "경기");
  const id = string(item.code, "경기 고유번호");
  const rawTime = String(integer(item.dateTime, "경기 시각"));
  if (!/^\d{12}$/.test(rawTime) || rawTime.slice(0, 8) !== compactDate(date)) fail("다른 날짜의 경기");
  const hour = Number(rawTime.slice(8, 10));
  const minute = Number(rawTime.slice(10, 12));
  if (hour > 23 || minute > 59) fail("유효하지 않은 경기 시각");
  const rawStatus = string(item.status, "경기 상태");
  const mapped = STATUS[rawStatus];
  // An unfamiliar status must never turn a partial feed into 'all games ended'.
  if (!mapped) fail("알 수 없는 경기 상태");
  const showScore = ["live", "final", "suspended"].includes(mapped.status);
  const away = team(item.away, showScore);
  const home = team(item.home, showScore);
  if (away.code === home.code) fail("동일한 홈/원정 팀");
  const time = `${rawTime.slice(8, 10)}:${rawTime.slice(10, 12)}`;
  return {
    id, date, startsAt: `${date}T${time}:00+09:00`, time,
    stadium: string(item.stadium, "구장"), away, home,
    status: mapped.status, statusLabel: mapped.label,
  };
}

function calendarDays(payload: unknown, date: string): number[] {
  const data = successData(payload);
  if (!Array.isArray(data.calendar)) fail("월별 경기일 누락");
  const [year, month] = date.split("-").map(Number);
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const days = data.calendar.map((value) => integer(value, "월별 경기일"));
  if (days.some((day) => day < 1 || day > daysInMonth) || new Set(days).size !== days.length) fail("월별 경기일 형식");
  return days;
}

/** Calendar entries are days of the requested month, not dates to infer from a
 * schedule redirect. The server/API owns the project's supported-year policy.
 */
export function parseTvingCalendar(payload: unknown, month: string): number[] {
  if (!/^\d{4}-\d{2}$/.test(month)) fail("요청 월");
  const date = `${month}-01`;
  compactDate(date);
  return calendarDays(payload, date).sort((a, b) => a - b);
}

/** A mismatched focusDate requires a separately fetched calendar for the requested month.
 * TVING redirects a day without games to the next game date, even in JSON responses.
 */
export function parseTvingSchedule(payload: unknown, date: string, monthCalendar?: unknown): KboGame[] {
  const requested = compactDate(date);
  const schedule = band(payload, "SPORTS_SCHEDULE");
  const focused = String(integer(schedule.focusDate, "일정 기준 날짜"));
  if (!/^\d{8}$/.test(focused)) fail("일정 기준 날짜 형식");
  if (!Array.isArray(schedule.items)) fail("경기 목록 누락");
  if (focused !== requested) {
    if (monthCalendar === undefined) fail("요청 날짜와 일정 기준 날짜가 다릅니다");
    if (calendarDays(monthCalendar, date).includes(Number(requested.slice(6)))) fail("해당 날짜 경기 목록이 누락되었습니다");
    return [];
  }
  const games = schedule.items.map((item) => game(item, date));
  if (new Set(games.map((item) => item.id)).size !== games.length) fail("중복된 경기 고유번호");
  // Never collapse by the two team names: a doubleheader has distinct game IDs.
  if (games.length === 0) {
    // An empty items array alone may be a partial response, even when the date
    // matches. Require a valid calendar that explicitly excludes this day.
    const calendar = schedule.calendar === undefined
      ? monthCalendar
      : { code: "0000", data: { calendar: schedule.calendar } };
    if (calendar === undefined) fail("빈 경기 목록의 월별 경기일 확인이 필요합니다");
    if (calendarDays(calendar, date).includes(Number(requested.slice(6)))) {
      fail("경기일로 표시됐지만 경기 목록이 비어 있습니다");
    }
  }
  return games.sort((a, b) => a.time.localeCompare(b.time) || a.id.localeCompare(b.id));
}

export function parseTvingStandings(payload: unknown, date: string): KboStanding[] {
  compactDate(date);
  const ranking = band(payload, "SPORTS_TEAM_RANKING_CALENDAR");
  const year = object(ranking.focusYearSeason, "순위 시즌");
  const season = object(ranking.focusGameSeason, "순위 리그");
  if (String(year.code) !== date.slice(0, 4) || String(season.code) !== "0") fail("요청한 정규리그 시즌과 다릅니다");
  if (!Array.isArray(ranking.items) || ranking.items.length !== 10) fail("정규리그 10팀 순위가 완전하지 않습니다");
  const rows = ranking.items.map((value): KboStanding => {
    const item = object(value, "팀 순위");
    const code = string(item.code, "순위 팀 코드");
    const name = string(item.name, "순위 팀 이름");
    if (TEAM_NAMES[code] !== name) fail("순위 팀 정보");
    const played = integer(item.games, "경기 수");
    const wins = integer(item.wins, "승");
    const draws = integer(item.draws, "무");
    const losses = integer(item.losses, "패");
    const rank = integer(item.rank, "순위");
    if (rank < 1 || rank > 10 || played !== wins + draws + losses) fail("순위 집계 불일치");
    return {
      rank, teamCode: code, team: name, played, wins, draws, losses,
      winRate: decimal(item.winningPercentage, "승률", 1),
      gamesBehind: decimal(item.gamesBehind, "게임차"),
      streak: string(item.winningStreak, "연속"),
      battingAverage: decimal(item.battingAverage, "타율", 1),
      era: decimal(item.earnedRunAverage, "평균자책"),
      lastTen: string(item.recentGames, "최근 10경기"),
    };
  });
  if (new Set(rows.map((row) => row.teamCode)).size !== 10) fail("순위에 중복된 팀이 있습니다");
  return rows.sort((a, b) => a.rank - b.rank);
}

export function parseTvingPitcherRankings(payload: unknown): KboPitcherRanking[] {
  const rows = athleteItems(payload, "투수").map((item): KboPitcherRanking => ({
    ...athleteBase(item),
    earnedRunAverage: statistic(item.earnedRunAverage, "평균자책"),
    fip: statistic(item.fip, "FIP"),
    whip: statistic(item.whip, "WHIP"),
    war: statistic(item.war, "투수 WAR"),
    qualityStarts: statistic(item.qs, "QS"),
    games: statistic(item.games, "투수 경기"),
    wins: statistic(item.wins, "승"),
    losses: statistic(item.losses, "패"),
    saves: statistic(item.save, "세이브"),
    holds: statistic(item.hold, "홀드"),
    innings: innings(item.inning),
    strikeouts: statistic(item.strikeOut, "탈삼진"),
    hitsAllowed: statistic(item.hit, "피안타"),
    homeRunsAllowed: statistic(item.homeRun, "피홈런"),
    walks: statistic(item.baseOnBalls, "볼넷"),
    hitByPitch: statistic(item.hitByPitch, "사구"),
    wildPitches: statistic(item.wildPitch, "폭투"),
    runsAllowed: statistic(item.run, "실점"),
    winningPercentage: statistic(item.winningPercentage, "투수 승률"),
  }));
  if (new Set(rows.map(row => row.playerCode)).size !== rows.length) fail("중복된 투수 코드");
  return rows.sort((a, b) => a.rank - b.rank);
}

export function parseTvingHitterRankings(payload: unknown): KboHitterRanking[] {
  const rows = athleteItems(payload, "타자").map((item): KboHitterRanking => ({
    ...athleteBase(item),
    battingAverage: statistic(item.battingAverage, "타율"),
    ops: statistic(item.ops, "OPS"),
    wrcPlus: statistic(item.wrcPlus, "wRC+"),
    war: statistic(item.war, "타자 WAR"),
    games: statistic(item.games, "타자 경기"),
    atBats: statistic(item.atBat, "타수"),
    hits: statistic(item.hit, "안타"),
    doubles: statistic(item.doubles, "2루타"),
    triples: statistic(item.triples, "3루타"),
    homeRuns: statistic(item.homeRun, "홈런"),
    runsBattedIn: statistic(item.runBattedIn, "타점"),
    runs: statistic(item.run, "득점"),
    stolenBases: statistic(item.stolenBase, "도루"),
    walks: statistic(item.baseOnBalls, "볼넷"),
    strikeouts: statistic(item.strikeOut, "삼진"),
    doublePlays: statistic(item.doublePlay, "병살"),
    onBasePercentage: statistic(item.onBasePercentage, "출루율"),
    sluggingPercentage: statistic(item.sluggingPercentage, "장타율"),
  }));
  if (new Set(rows.map(row => row.playerCode)).size !== rows.length) fail("중복된 타자 코드");
  return rows.sort((a, b) => a.rank - b.rank);
}

export function parseTvingIndividualRankings(pitchers: unknown, hitters: unknown): KboIndividualRankings {
  return { pitchers: parseTvingPitcherRankings(pitchers), hitters: parseTvingHitterRankings(hitters) };
}
