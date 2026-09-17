import type { RouteStop } from "./routes";

export function coursePointLabel(stops: RouteStop[], index: number, separateStart = false): string {
  if (separateStart) return String(index + 1);
  return stops[0]?.isMapPoint || stops[0]?.isDrawnPoint ? (index === 0 ? "출발" : String(index)) : String(index + 1);
}

export function renumberMapPoints(stops: RouteStop[]): RouteStop[] {
  return stops.map((stop, index) => stop.isMapPoint ? {
    ...stop, name: coursePointLabel(stops, index) === "출발" ? "출발지" : `경유지 ${coursePointLabel(stops, index)}`,
  } : stop);
}

export function withCourseStart(stops: RouteStop[], start?: { lat: number; lng: number }): RouteStop[] {
  if (!start) return stops;
  return renumberMapPoints([{ ...start, name: "출발지", category: "출발", placeId: "route:origin", isDrawnPoint: true }, ...stops]);
}

// History records creation order, so reordering or deleting a point in the list
// does not make Undo remove a different point (or an existing searched place).
// Points that reached the list without the planner recording them (e.g. a course from
// the chatbot) are appended in list order, so undo can remove them newest-first as well.
export function withUntrackedPoints(stops: RouteStop[], history: string[]) {
  const known = new Set(history);
  const untracked = stops
    .filter((stop) => stop.isMapPoint || stop.isDrawnPoint)
    .map((stop) => stop.visitId ?? stop.placeId)
    .filter((id): id is string => Boolean(id) && !known.has(id!));
  return untracked.length ? [...history, ...untracked] : history;
}

export function undoDrawnPoint(stops: RouteStop[], history: string[]) {
  const remaining = [...history];
  while (remaining.length) {
    const id = remaining.pop()!;
    const point = stops.find((stop) => (stop.isMapPoint || stop.isDrawnPoint) && (stop.visitId ?? stop.placeId) === id);
    if (point) return { stops: renumberMapPoints(stops.filter((stop) => stop !== point)), history: remaining, removed: point };
  }
  return { stops, history: remaining, removed: undefined };
}
