import { distanceMeters, indoorNameLabel, isStadiumFacility, NEARBY_RADIUS, PLACE_CATEGORIES, type NearbyPlace, type NearbyStadium, type PlaceCategory } from "./nearby-places";

export type TourItem = {
  contentid?: string; contenttypeid?: string; title?: string;
  mapx?: string; mapy?: string; addr1?: string; addr2?: string; tel?: string;
  cat3?: string; lclsSystm3?: string;
};
export type TourResult = { status: "ok" | "partial" | "unconfigured" | "error"; places: NearbyPlace[]; truncated: boolean; stale?: boolean; warning?: string; fetchedAt?: string | null; lastSyncedAt?: string | null };
export const TOUR_CONTENT_TYPES = ["12", "14", "28"] as const;

// Names verified against TourAPI categoryCode2 (A02 > A0206).
const CULTURE_LABELS: Record<string, string> = {
  A02060100: "박물관", A02060200: "기념관", A02060300: "전시관",
  A02060400: "컨벤션센터", A02060500: "미술관/화랑", A02060600: "공연장",
  A02060700: "문화원", A02060800: "외국문화원", A02060900: "도서관",
  A02061000: "대형서점", A02061100: "문화전수시설", A02061200: "영화관",
  A02061300: "어학당", A02061400: "학교",
};

export function tourCategory(item: TourItem): PlaceCategory | null {
  const type = item.contenttypeid;
  if (!TOUR_CONTENT_TYPES.some((supported) => supported === type)) return null;
  // Some dated events are registered as facilities. Do not show them as permanent places.
  if (/(?:19|20)\d{2}.*(?:페어|축제|박람회|페스티벌)/.test(item.title ?? "")) return null;
  // Sports facilities can include the ballpark itself or outdoor stadiums.
  if (/야구장|야구경기장|축구장|종합운동장/.test(item.title ?? "")) return null;
  if (/야외|실외|물놀이장|수영장/.test(item.title ?? "")) return type === "28" ? null : "sight";
  if (/공원|산책|둘레길|숲길|수목원|생태숲/.test(item.title ?? "") || ["A03022700"].includes(item.cat3 ?? "")) return "walk";
  if (/박물관|미술관|전시관|전시실|과학관|문학관|기념관|공연장|극장|영화관|아쿠아리움|수족관|도서관|갤러리|아트홀|보드게임|방탈출|볼링|실내/.test(item.title ?? "")) return "indoor";
  // Cultural facilities also include outdoor venues: do not call all of them indoor.
  if (type === "14" && ["A02060100", "A02060200", "A02060300", "A02060500", "A02060600", "A02060700"].includes(item.cat3 ?? "")) return "indoor";
  return type === "28" ? null : "sight";
}

export function normalizeTourPlace(item: TourItem, stadium: NearbyStadium): NearbyPlace | null {
  if (!item || typeof item !== "object") return null;
  const id = typeof item.contentid === "string" ? item.contentid : "";
  const name = typeof item.title === "string" ? item.title.trim() : "";
  const x = typeof item.mapx === "string" ? item.mapx.trim() : "";
  const y = typeof item.mapy === "string" ? item.mapy.trim() : "";
  const lat = Number(y), lng = Number(x);
  if (!/^\d+$/.test(id) || !name || !x || !y || !Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  const address = typeof item.addr1 === "string" ? item.addr1.trim() : "";
  const distance = distanceMeters(stadium, { lat, lng });
  if (distance > NEARBY_RADIUS || isStadiumFacility({ id, place_name: name, road_address_name: address, address_name: address, category_group_name: "", x, y }, stadium)) return null;
  const kind = tourCategory(item);
  if (!kind) return null;
  const category = PLACE_CATEGORIES.find((entry) => entry.id === kind)!.label;
  const subcategory = kind === "indoor" ? CULTURE_LABELS[item.cat3 ?? ""] ?? indoorNameLabel(name) : undefined;
  return { placeId: `tour:${id}`, tourContentId: id, name, lat, lng, category, kind, cuisine: "기타", address, phone: typeof item.tel === "string" ? item.tel : "", detail: `${subcategory ?? category} · 한국관광공사`, distance, subcategory };
}

export function parseTourPage(value: unknown): { items: TourItem[]; total: number } {
  if (!value || typeof value !== "object") throw new Error("Invalid tourism response");
  const response = (value as { response?: { header?: { resultCode?: string }; body?: { items?: { item?: TourItem | TourItem[] } | string; totalCount?: number | string } } }).response;
  if (!response || !["0000", "00"].includes(response.header?.resultCode ?? "")) throw new Error("Tourism API rejected the request");
  const total = Number(response.body?.totalCount);
  if (!Number.isFinite(total) || total < 0) throw new Error("Invalid tourism result count");
  const items = response.body?.items;
  const item = typeof items === "object" ? items?.item : undefined;
  const result = Array.isArray(item) ? item : item && typeof item === "object" ? [item] : [];
  if (total > 0 && result.length === 0) throw new Error("Missing tourism results");
  return { items: result, total };
}
