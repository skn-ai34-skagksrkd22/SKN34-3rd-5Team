export const KBO_TEAM_CODES = ["SS", "KT", "LG", "HT", "OB", "NC", "HH", "LT", "SK", "WO"] as const;
export type KboTeamCode = typeof KBO_TEAM_CODES[number];
export type KboRosterPosition = "pitcher" | "infielder" | "outfielder" | "catcher";
export type KboTeamAthleteType = "pitcher" | "hitter";

export type KboLabelValue = { title: string; value: string };

export type KboTeamDetailGame = {
  id: string;
  startsAt: string;
  time: string;
  stadium: string;
  status: string;
  away: { code: string; name: string; score: number | null };
  home: { code: string; name: string; score: number | null };
};

export type KboTeamTopAthlete = {
  rank: number;
  name: string;
  code: string;
  value: string;
  imageUrl: string | null;
};

export type KboTeamRankingGroup = {
  title: string;
  athletes: KboTeamTopAthlete[];
};

export type KboRosterAthlete = {
  code: string;
  name: string;
  imageUrl: string | null;
  backNumber: string;
};

export type KboTeamShortcut = {
  code: KboTeamCode;
  name: string;
  imageUrl: string | null;
};

export type KboTeamDetail = {
  code: KboTeamCode;
  teamName: string;
  shortName: string;
  teamImageUrl: string | null;
  backgroundImage: string | null;
  seasonTitle: string;
  mainRecords: KboLabelValue[];
  boxRecords: KboLabelValue[];
  schedule: KboTeamDetailGame[];
  rankings: Record<KboTeamAthleteType, KboTeamRankingGroup[]>;
  rosters: Record<KboRosterPosition, KboRosterAthlete[]>;
  shortcuts: KboTeamShortcut[];
};

export type KboAthleteProfile = {
  code: string;
  name: string;
  imageUrl: string | null;
  positions: string[];
  backNumber: string;
  joinDate: string;
  birthDate: string;
  body: string[];
  education: string;
  draftOrder: string;
  team: { name: string; code: KboTeamCode; color: string; logoUrl: string | null };
};

export type KboGraphPoint = { x: string; y: string; description: string | null };
export type KboGraphRecord = { type: "line_filled" | "line" | "dot" | "bar"; color: string; points: KboGraphPoint[] };

export type KboAthleteSeasonRecord = {
  title: string;
  value: string;
  rank: string | null;
  isFirstRank: boolean;
  graphs: KboGraphRecord[];
};

export type KboCareerColumn = { name: string; key: string };
export type KboCareerRow = Record<string, string>;

export type KboAthleteDetail = {
  profile: KboAthleteProfile;
  seasonTitle: string;
  seasonRecords: KboAthleteSeasonRecord[];
  careerTitle: string;
  careerColumns: KboCareerColumn[];
  careerRows: KboCareerRow[];
};

export type KboDetailEntry<T> = { data: T; fetchedAt: string; generation: string };
export type KboDetailProgress = {
  state: "idle" | "collecting" | "partial" | "complete";
  generation: string | null;
  startedAt: string | null;
  completedAt: string | null;
  teamTotal: number;
  teamDone: number;
  athleteTotal: number;
  athleteDone: number;
  failures: string[];
};

export type KboDetailStore = {
  version: 1;
  teams: Partial<Record<KboTeamCode, KboDetailEntry<KboTeamDetail>>>;
  athletes: Record<string, KboDetailEntry<KboAthleteDetail>>;
  progress: KboDetailProgress;
  lastCompletedGeneration: string | null;
  lastGameGeneration: string | null;
};

export type KboDetailSnapshot<T> = T & {
  fetchedAt: string;
  providerFetchedAt: string;
  lastSyncedAt: string | null;
  source: { name: "TVING"; url: string };
  collecting: boolean;
  progress: KboDetailProgress;
  stale: boolean;
  warning: string | null;
};

export type KboDetailApiResponse<T> = { data: KboDetailSnapshot<T> | null; error: string | null };
