import type { RouteStop } from "./routes";

// Undo/redo for the planner's visit list. The list itself is owned by the writer, so the
// history only watches the `stops` it receives: any new array is a user step, except the
// one we asked for ourselves (`expected`) while stepping back or forward.
export const STOP_HISTORY_LIMIT = 50;

export type StopHistory = { current: RouteStop[]; past: RouteStop[][]; future: RouteStop[][]; expected: RouteStop[] | null };

export function createStopHistory(stops: RouteStop[]): StopHistory {
  return { current: stops, past: [], future: [], expected: null };
}

const sameStops = (a: RouteStop[], b: RouteStop[]) => a.length === b.length && JSON.stringify(a) === JSON.stringify(b);

export function observeStops(history: StopHistory, stops: RouteStop[]): StopHistory {
  if (stops === history.current) return history;
  if (stops === history.expected) return { ...history, current: stops, expected: null };
  if (sameStops(stops, history.current)) return { ...history, current: stops };
  return { current: stops, past: [...history.past, history.current].slice(-STOP_HISTORY_LIMIT), future: [], expected: null };
}

export function undoStops(history: StopHistory) {
  const stops = history.past.at(-1);
  if (!stops) return null;
  return { stops, history: { current: history.current, past: history.past.slice(0, -1), future: [history.current, ...history.future], expected: stops } };
}

export function redoStops(history: StopHistory) {
  const stops = history.future[0];
  if (!stops) return null;
  return { stops, history: { current: history.current, past: [...history.past, history.current], future: history.future.slice(1), expected: stops } };
}
