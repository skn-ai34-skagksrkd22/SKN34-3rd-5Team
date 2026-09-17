// Events between the spotlight guide (components/route-guide.tsx) and the map planner.
export type GuidePoint = { lat: number; lng: number };
/** detail: GuidePoint to show the dashed start-point target, or null to remove it. */
export const GUIDE_ORIGIN_TARGET = "route-guide:origin-target";
/** Fired by the planner once the user pressed the target and the start point was set. */
export const GUIDE_ORIGIN_SET = "route-guide:origin-set";
/** detail: GuideCourseStop[] — the scripted example course the writer puts on the map as a finished course. */
export const GUIDE_COURSE = "route-guide:course";
export type GuideCourseStop = { name: string; category: string; lat: number; lng: number; placeId?: string; address?: string; isMapPoint?: boolean };
