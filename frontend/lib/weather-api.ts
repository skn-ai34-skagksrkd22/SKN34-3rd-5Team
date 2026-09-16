export type StadiumWeather = {
  label: "맑음" | "구름많음" | "흐림" | "비" | "비/눈" | "눈" | "소나기";
  temperature: number;
  forecastAt: string;
  issuedAt: string;
  fetchedAt: string;
  source: "기상청 단기예보";
};

const venues: [string, string[]][] = [
  ["JAMSIL", ["잠실"]], ["GOCHEOK", ["고척"]], ["MUNHAK", ["문학", "인천", "랜더스"]],
  ["SUWON", ["수원", "위즈"]], ["DAEJEON", ["대전", "한화생명"]], ["DAEGU", ["대구", "라이온즈"]],
  ["GWANGJU", ["광주", "챔피언스"]], ["SAJIK", ["사직"]], ["CHANGWON", ["창원", "NC파크"]],
];

const labels = new Set(["맑음", "구름많음", "흐림", "비", "비/눈", "눈", "소나기"]);

export function weatherStadiumCode(name: string) {
  return venues.find(([, aliases]) => aliases.some(alias => name.includes(alias)))?.[0];
}

export function parseStadiumWeather(value: unknown): StadiumWeather | null {
  if (!value || typeof value !== "object") return null;
  const weather = value as Record<string, unknown>;
  if (typeof weather.label !== "string" || !labels.has(weather.label)
    || typeof weather.temperature !== "number" || !Number.isFinite(weather.temperature)
    || typeof weather.forecastAt !== "string" || !Number.isFinite(Date.parse(weather.forecastAt))
    || typeof weather.issuedAt !== "string" || !Number.isFinite(Date.parse(weather.issuedAt))
    || typeof weather.fetchedAt !== "string" || !Number.isFinite(Date.parse(weather.fetchedAt))
    || weather.source !== "기상청 단기예보") return null;
  return weather as StadiumWeather;
}

export async function fetchStadiumWeather(
  stadium: string,
  date: string,
  time: string,
  fetcher: typeof fetch = fetch,
  signal?: AbortSignal,
) {
  const query = new URLSearchParams({ stadium, date, time });
  try {
    const response = await fetcher(`/api/weather/?${query}`, {
      cache: "no-store",
      redirect: "error",
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(12000)]) : AbortSignal.timeout(12000),
    });
    if (!response.ok) return null;
    const body: unknown = await response.json();
    return parseStadiumWeather(body && typeof body === "object" ? (body as Record<string, unknown>).weather : null);
  } catch {
    return null;
  }
}
