"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { ChatPopup } from "@/components/chat-popup";
import Editor from "@/components/editor";
import { NearbyRoutePlanner } from "@/components/nearby-route-planner";
import { adaptStadium } from "@/lib/baseball/adapters";
import { fetchBaseballStadiums } from "@/lib/baseball/client";
import type { Stadium } from "@/lib/stadiums";
import { routeContentToText, type RouteContentFormat } from "@/lib/route-content";
import { useChat } from "@/components/chat-provider";
import { retryRoutes, saveRoute, useRoutes, useRoutesError, useRoutesReady, type RouteStop, type TripRoute } from "@/lib/routes";
import { withCourseStart } from "@/lib/drawn-course";
import { browserDraftStorage, createDraftAutosave, readRouteDraft, recoverRouteDraft, removeRouteDraft, saveRouteDraft, type MemoryRouteDraft, type RouteDraftData } from "@/lib/route-draft";
import type { TravelMode } from "@/lib/course-directions";
import { courseToStops } from "@/lib/chat/course";
import type { ChatCourse } from "@/lib/chat/types";
import { MAX_ROUTE_STOPS, sameStop } from "@/lib/nearby-places";

function WriterIcon({ kind }: { kind: "spark" | "pin" | "arrow" | "save" }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {kind === "spark" && <><path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z" /><path d="m20 2 .6 1.4L22 4l-1.4.6L20 6l-.6-1.4L18 4l1.4-.6L20 2Z" /></>}
      {kind === "pin" && <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2.5" /></>}
      {kind === "arrow" && <><path d="M5 12h14M13 6l6 6-6 6" /></>}
      {kind === "save" && <><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h12l4 4v12a2 2 0 0 1-2 2Z" /><path d="M7 3v6h10V3M7 21v-8h10v8" /></>}
    </svg>
  );
}

type WriterTab = "write" | "chat";
type PlannerMode = "places" | "draw";
type Confirmation = { title: string; description: string; label: string; action: () => void; cancelLabel?: string; cancelAction?: () => void };
const writerTabs: { id: WriterTab; label: string }[] = [{ id: "write", label: "루트 작성" }, { id: "chat", label: "챗봇" }];
const writerDrafts = new Map<string, MemoryRouteDraft>();
const noClientChange = () => () => {};
const clientReady = () => true;
const serverReady = () => false;
const stadiumKey = (value: string) => value.replace(/\s/g, "").toUpperCase();
const matchesStadium = (stadium: Stadium, value: string) => stadium.code === stadiumKey(value) || stadiumKey(stadium.name) === stadiumKey(value);

export default function RouteWriter({ editId, copyId, initialStadium }: { editId?: string; copyId?: string; initialStadium?: string }) {
  const hydrated = useSyncExternalStore(noClientChange, clientReady, serverReady);
  const routes = useRoutes();
  const ready = useRoutesReady();
  const loadError = useRoutesError();
  const [stadiums, setStadiums] = useState<Stadium[] | null>(null);
  const [stadiumError, setStadiumError] = useState("");
  const [invalidCount, setInvalidCount] = useState(0);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetchBaseballStadiums(controller.signal).then(page => {
      const available = page.results.map(adaptStadium).filter((item): item is Stadium => item !== null);
      setStadiums(available); setInvalidCount(page.results.length - available.length);
    }).catch(cause => { if (!controller.signal.aborted) setStadiumError(cause instanceof Error ? cause.message : "구장 목록을 불러오지 못했어요."); });
    return () => controller.abort();
  }, [attempt]);
  const sourceId = copyId ?? editId;
  const existing = sourceId ? routes.find((route) => route.id === sourceId || route.legacySourceId === sourceId) : undefined;
  if (sourceId && !ready) return <main className="container writer-empty"><p role="status"><span className="writer-spinner" aria-hidden="true" />저장된 루트를 불러오고 있어요.</p></main>;
  if (sourceId && !existing && loadError) return <main className="container writer-empty"><span className="eyebrow">MY ROUTE</span><h1>{loadError}</h1><p>이전 버전의 브라우저 코스만 목록에 남아 있을 수 있어요.</p><button type="button" className="button button-primary" onClick={() => void retryRoutes()}>다시 불러오기</button></main>;
  if (sourceId && (!existing || (editId && !existing.owned))) return <main className="container writer-empty"><span className="eyebrow">MY ROUTE</span><h1>수정할 루트를 찾을 수 없어요</h1><p>이 브라우저에서 편집 권한을 보관한 루트인지 확인하거나 새 루트를 만들어보세요.</p><Link href="/routes" className="button button-secondary">루트 목록으로</Link></main>;
  if (!hydrated) return <main className="container writer-empty"><p role="status"><span className="writer-spinner" aria-hidden="true" />임시저장 내용을 확인하고 있어요.</p></main>;
  if (stadiumError) return <main className="container writer-empty" role="alert"><h1>구장 목록을 불러오지 못했어요</h1><p>{stadiumError} 작성 중이던 기기 내 초안은 지우지 않았어요.</p><button type="button" onClick={() => { setStadiums(null); setStadiumError(""); setAttempt(value => value + 1); }}>다시 시도</button></main>;
  if (!stadiums) return <main className="container writer-empty"><p role="status"><span className="writer-spinner" aria-hidden="true" />DB에서 구장 목록을 불러오고 있어요.</p></main>;
  if (!stadiums.length) return <main className="container writer-empty"><h1>선택할 수 있는 구장이 없어요</h1><p>{invalidCount ? "적재된 구장 좌표를 확인해 주세요." : "구장 데이터가 적재된 뒤 다시 시도해 주세요."} 기존 초안은 유지됩니다.</p></main>;
  const requested = existing?.stadium ?? initialStadium;
  const initial = requested ? stadiums.find(item => matchesStadium(item, requested)) : stadiums.at(0);
  if (!initial) return <main className="container writer-empty"><h1>선택한 구장을 사용할 수 없어요</h1><p>구장이 삭제됐거나 좌표를 확인할 수 없어요. 다른 구장을 직접 선택해 주세요. 기존 초안은 유지했습니다.</p><Link href="/routes/new" className="button button-secondary">구장 다시 선택하기</Link></main>;
  return <WriterForm key={`${copyId ? "copy:" : "edit:"}${existing?.legacySourceId ?? sourceId ?? initial.code}`} stadiums={stadiums} initial={initial} copying={Boolean(copyId)} existing={existing} />;
}

function WriterForm({ stadiums, initial, existing, copying = false }: { stadiums: Stadium[]; initial: Stadium; existing?: TripRoute; copying?: boolean }) {
  const router = useRouter();
  const { onContextChange, registerCourseTarget, takePendingCourse } = useChat();
  const draftKey = existing ? `${copying ? "copy" : "edit"}:${existing.id}` : `new:${initial.code}`;
  const [storage] = useState(browserDraftStorage);
  const [storedDraft] = useState(() => readRouteDraft(storage, draftKey));
  const [memoryDraft] = useState(() => writerDrafts.get(draftKey));
  const [recovery] = useState(() => recoverRouteDraft(storedDraft, memoryDraft));
  const [restoredDraft] = useState(() => {
    const candidate = recovery.data;
    return candidate && stadiums.some(stadium => stadium.code === candidate.stadiumCode) ? candidate : undefined;
  });
  const [stadiumCode, setStadiumCode] = useState(restoredDraft?.stadiumCode ?? initial.code);
  const [title, setTitle] = useState(restoredDraft?.title ?? existing?.title ?? "");
  const [content, setContent] = useState(restoredDraft?.content ?? existing?.content ?? "");
  const [contentFormat, setContentFormat] = useState<RouteContentFormat>(restoredDraft ? restoredDraft.contentFormat : existing?.contentFormat);
  const [duration] = useState(restoredDraft?.duration ?? existing?.duration ?? "반나절");
  const [tags] = useState<string[]>(restoredDraft?.tags ?? existing?.tags ?? ["첫 직관"]);
  const [stops, setStops] = useState<RouteStop[]>(restoredDraft?.stops ?? existing?.stops ?? []);
  const [start, setStart] = useState<TripRoute["start"]>(restoredDraft ? restoredDraft.start : existing?.start);
  const [tab, setTab] = useState<WriterTab>(restoredDraft?.tab ?? "write");
  const [travelMode, setTravelMode] = useState<TravelMode>(restoredDraft?.travelMode ?? "walk");
  const [plannerMode, setPlannerMode] = useState<PlannerMode>(() => stops.some(stop => stop.isMapPoint && stop.category === "동선 지점") ? "draw" : "places");
  const [plannerCompleted, setPlannerCompleted] = useState(false);
  const [error, setError] = useState("");
  const [draftStatus, setDraftStatus] = useState(() => storedDraft.error ? "브라우저 저장 공간을 읽지 못했어요. 변경 내용은 이 화면에만 남아 있어요." : storedDraft.raw && (!storedDraft.draft || !restoredDraft) ? "기존 임시저장 데이터를 확인할 수 없어 덮어쓰지 않았어요." : memoryDraft ? "이 화면에 남아 있던 미저장 변경을 복원했어요." : restoredDraft && storedDraft.draft ? `${new Date(storedDraft.draft.updatedAt).toLocaleString("ko-KR")} 임시저장을 복원했어요.` : "변경 사항 없음");
  const [saving, setSaving] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  // 챗봇 코스를 담은 횟수·구장. 지도(planner)가 이 값이 바뀌면 "내 코스" 탭을 열고 코스 전체를 보여준다.
  const [courseApplied, setCourseApplied] = useState<{ version: number; stadiumCode: string } | null>(null);
  // 챗봇이 채워 준 제목·본문. 사용자가 손대지 않았으면 다음 추천 코스로 다시 바꿔 준다.
  const autoFilled = useRef<{ title?: string; content?: string }>({});
  const dirty = useRef(recovery.dirty);
  const savingRef = useRef(false);
  const expectedRaw = useRef(recovery.expectedRaw);
  const draftContext = useRef(draftKey);
  const autosaveRef = useRef<ReturnType<typeof createDraftAutosave> | null>(null);
  const savedRouteRef = useRef<TripRoute | undefined>(existing && !copying && existing.owned ? existing : undefined);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const current = stadiums.find((stadium) => stadium.code === stadiumCode);
  const plainContent = routeContentToText(content, contentFormat);
  const canSave = Boolean(title.trim() && plainContent.length <= 12000 && stops.length);
  const latest = useRef<RouteDraftData>({ stadiumCode, title, content, contentFormat, duration, tags, stops, start, tab, travelMode });
  useLayoutEffect(() => {
    latest.current = { stadiumCode, title, content, contentFormat, duration, tags, stops, start, tab, travelMode };
    if (dirty.current) writerDrafts.set(draftContext.current, { data: latest.current, expectedRaw: expectedRaw.current });
  }, [stadiumCode, title, content, contentFormat, duration, tags, stops, start, tab, travelMode]);

  const flushDraft = useCallback(() => {
    if (!dirty.current) return true;
    const context = draftContext.current;
    const result = saveRouteDraft(storage, context, latest.current, expectedRaw.current);
    if (result.status === "saved") {
      expectedRaw.current = result.raw; dirty.current = false; writerDrafts.delete(context);
      setDraftStatus(`${new Date(result.draft.updatedAt).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })} 임시저장됨`);
      return true;
    }
    if (result.status === "unchanged") { expectedRaw.current = result.raw; dirty.current = false; writerDrafts.delete(context); setDraftStatus("변경 없이 임시저장 상태예요."); return true; }
    writerDrafts.set(context, { data: latest.current, expectedRaw: expectedRaw.current });
    setDraftStatus(result.status === "conflict" ? "다른 탭의 새 임시저장을 발견해 자동 저장을 멈췄어요. 새로고침 후 확인해 주세요." : "브라우저 저장 공간에 임시저장하지 못했어요. 변경 내용은 이 화면에만 남아 있어요.");
    return false;
  }, [storage]);

  useEffect(() => {
    let active = false;
    const activate = window.setTimeout(() => { active = true; }, 0);
    const autosave = createDraftAutosave(flushDraft);
    autosaveRef.current = autosave;
    if (dirty.current) autosave.changed();
    const pagehide = () => autosave.flush();
    const visibility = () => { if (document.visibilityState === "hidden") autosave.flush(); };
    window.addEventListener("pagehide", pagehide);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      clearTimeout(activate);
      autosave.stop(active);
      if (autosaveRef.current === autosave) autosaveRef.current = null;
      window.removeEventListener("pagehide", pagehide);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [flushDraft]);

  useEffect(() => {
    if (current) onContextChange({ stadium: current.name, intent: "route" });
  }, [current, onContextChange]);

  useEffect(() => {
    const protect = (event: BeforeUnloadEvent) => { if (dirty.current && !flushDraft()) event.preventDefault(); };
    const protectLink = (event: MouseEvent) => {
      if (!dirty.current || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element | null)?.closest<HTMLAnchorElement>("a[href]");
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) return;
      const next = new URL(anchor.href, window.location.href);
      if (next.origin === window.location.origin && next.pathname === window.location.pathname && next.search === window.location.search) return;
      if (flushDraft()) return;
      event.preventDefault(); event.stopPropagation();
      setConfirmation({ title: "임시저장하지 못한 변경이 있어요", description: "브라우저 저장에 실패해 최신 변경은 이 화면에만 있어요. 나가면 해당 변경을 잃을 수 있어요.", label: "그래도 나가기", action: () => { dirty.current = false; if (next.origin === window.location.origin) router.push(`${next.pathname}${next.search}${next.hash}`); else window.location.assign(next.href); } });
    };
    window.addEventListener("beforeunload", protect);
    document.addEventListener("click", protectLink, true);
    return () => { window.removeEventListener("beforeunload", protect); document.removeEventListener("click", protectLink, true); };
  }, [router, flushDraft]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!confirmation || !dialog) return;
    const opener = document.activeElement as HTMLElement | null;
    if (!dialog.open) dialog.showModal();
    return () => { if (dialog.open) dialog.close(); opener?.focus(); };
  }, [confirmation]);

  const markDirty = useCallback(() => { dirty.current = true; writerDrafts.set(draftContext.current, { data: latest.current, expectedRaw: expectedRaw.current }); setDraftStatus("저장되지 않은 변경이 있어요. 1초 뒤 자동 저장하고, 작성 중에는 5초마다 확인해요."); setError(""); autosaveRef.current?.changed(); }, []);
  const changeStops = useCallback((next: RouteStop[]) => { setStops(next); markDirty(); }, [markDirty]);
  const changeStart = useCallback((next: TripRoute["start"]) => {
    const previous = latest.current.start;
    if (next?.lat === previous?.lat && next?.lng === previous?.lng) return;
    setStart(next); markDirty();
  }, [markDirty]);
  const changeTravelMode = useCallback((next: TravelMode) => {
    if (next === latest.current.travelMode) return;
    setTravelMode(next); markDirty();
  }, [markDirty]);
  const applyCourse = useCallback((course: ChatCourse, how: "replace" | "append") => {
    const target = course.stadiumCode ? stadiums.find(stadium => matchesStadium(stadium, course.stadiumCode!)) : stadiums.find(stadium => stadium.code === latest.current.stadiumCode);
    if (!target) return null;
    const before = latest.current;
    const sameStadium = target.code === before.stadiumCode;
    const base = how === "append" && sameStadium ? before.stops : [];
    const incoming = courseToStops(course).filter(stop => !base.some(existing => sameStop(existing, stop)));
    setStadiumCode(target.code);
    setStops([...base, ...incoming].slice(0, MAX_ROUTE_STOPS));
    if (!sameStadium) setStart(undefined);
    if (course.travelMode) setTravelMode(course.travelMode);
    const filled = autoFilled.current;
    if (course.title && (!before.title.trim() || before.title === filled.title)) { setTitle(course.title); filled.title = course.title; }
    if (course.content && (!routeContentToText(before.content, before.contentFormat).trim() || (before.contentFormat === undefined && before.content === filled.content))) {
      setContent(course.content); setContentFormat(undefined); filled.content = course.content;
    }
    setTab("write");
    setPlannerMode("places"); // 챗봇 코스는 장소 핀 방식으로 그린다 (동선 모드면 전환)
    setCourseApplied(previous => ({ version: (previous?.version ?? 0) + 1, stadiumCode: target.code }));
    markDirty();
    return () => {
      setStadiumCode(before.stadiumCode); setStops(before.stops); setStart(before.start); setTravelMode(before.travelMode);
      setTitle(before.title); setContent(before.content); setContentFormat(before.contentFormat);
      setCourseApplied(previous => ({ version: (previous?.version ?? 0) + 1, stadiumCode: before.stadiumCode }));
      markDirty();
    };
  }, [stadiums, markDirty]);
  const applyCourseRef = useRef(applyCourse);
  useLayoutEffect(() => { applyCourseRef.current = applyCourse; }, [applyCourse]);
  useEffect(() => {
    registerCourseTarget({ stadiumCode, stopCount: stops.length, apply: (course, how) => applyCourseRef.current(course, how) });
  }, [registerCourseTarget, stadiumCode, stops.length]);
  useEffect(() => () => registerCourseTarget(null), [registerCourseTarget]);
  useEffect(() => {
    // 전체 채팅 화면에서 "루트 작성 지도에서 열기"로 넘어온 코스
    const pending = takePendingCourse();
    if (pending) applyCourseRef.current(pending, "replace");
  }, [takePendingCourse]);
  if (!current) return <main className="container writer-empty"><h1>초안의 구장을 사용할 수 없어요</h1><p>구장이 삭제됐거나 좌표를 확인할 수 없어요. 초안은 지우지 않았습니다.</p><Link href="/routes/new" className="button button-secondary">새 루트에서 구장 선택하기</Link></main>;
  const selectedStadium = current;
  function changeStadium(code: string) {
    if (code === stadiumCode) return;
    const change = () => { setStadiumCode(code); setStops([]); setStart(undefined); setPlannerCompleted(false); markDirty(); };
    if (!stops.length) { change(); return; }
    setConfirmation({ title: "다른 구장 주변을 둘러볼까요?", description: "구장을 바꾸면 선택한 방문 장소가 비워져요. 작성한 제목과 이야기는 그대로 남아요.", label: "구장 바꾸기", action: change });
  }
  function changeTab(next: WriterTab) { if (next !== tab) { setTab(next); markDirty(); } }
  function tabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % writerTabs.length;
    else if (event.key === "ArrowLeft") next = (index + writerTabs.length - 1) % writerTabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = writerTabs.length - 1;
    else return;
    event.preventDefault(); changeTab(writerTabs[next].id); document.getElementById(`writer-tab-${writerTabs[next].id}`)?.focus();
  }
  async function saveCourse(askReview = true) {
    if (savingRef.current) return;
    setError("");
    if (!canSave) { setError("코스 이름과 방문 장소를 확인해 주세요. 본문은 선택 사항이며 12,000자까지 작성할 수 있어요."); return; }
    savingRef.current = true; setSaving(true);
    const saved = savedRouteRef.current;
    const route: TripRoute = {
      id: saved?.id ?? "", title: title.trim(), stadium: selectedStadium.name, description: (plainContent.trim() || withCourseStart(stops, start).map((stop) => stop.name).join(" → ")).replace(/\s+/g, " ").slice(0, 100),
      content: content.trim(), ...(contentFormat ? { contentFormat } : {}), tags, duration, cover: existing?.cover ?? "/images/stadium-night.jpg", stops, ...(start ? { start } : {}),
      author: "익명", likes: saved?.likes ?? 0, views: saved?.views ?? 0, owned: true,
      isSample: false, createdAt: saved?.createdAt ?? new Date().toISOString(), ...(saved?.legacy ? { legacy: true } : {}), ...(saved?.legacySourceId ? { legacySourceId: saved.legacySourceId } : {}),
    };
    try {
      await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
      const persisted = await saveRoute(route);
      const oldContext = draftContext.current;
      removeRouteDraft(storage, oldContext, expectedRaw.current); writerDrafts.delete(oldContext);
      const canonicalContext = `edit:${persisted.id}`;
      draftContext.current = canonicalContext; expectedRaw.current = null;
      const url = new URL(window.location.href); url.searchParams.delete("copy"); url.searchParams.delete("stadium"); url.searchParams.set("edit", persisted.id); window.history.replaceState(window.history.state, "", url);
      savedRouteRef.current = persisted; dirty.current = false;
      setDraftStatus("공개 저장을 완료했어요. 이후 변경은 이 코스의 새 임시저장으로 보관해요.");
      savingRef.current = false; setSaving(false);
      if (persisted.saveWarning) setError(persisted.saveWarning);
      const showSavedCourse = () => router.push(`/routes/${encodeURIComponent(persisted.id)}`);
      if (askReview) {
        setConfirmation({
          title: "코스 후기를 작성하시겠어요?",
          description: persisted.saveWarning ? `코스가 커뮤니티에 저장됐어요. ${persisted.saveWarning}` : "코스가 커뮤니티에 저장됐어요. 후기를 추가로 작성할 수 있어요.",
          label: "예", cancelLabel: "아니요", cancelAction: showSavedCourse,
          action: () => {
            setTab("write");
            requestAnimationFrame(() => requestAnimationFrame(() => {
              const panel = document.getElementById("writer-panel-write");
              panel?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
              panel?.focus({ preventScroll: true });
            }));
          },
        });
      } else if (!persisted.saveWarning) router.push("/routes");
    } catch (caught) { savingRef.current = false; setSaving(false); dirty.current = true; autosaveRef.current?.changed(); setError(caught instanceof Error ? caught.message : "저장하지 못했어요. 다시 시도해 주세요. 작성 내용은 이 화면에 남아 있어요."); }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void saveCourse(false);
  }

  return (
    <main className="writer-page">
      <div className="container">
        <div className="writer-page-heading">
          <div><span className="eyebrow">MAKE YOUR GAME DAY</span><h1>{existing && !copying && !existing.isSample ? "나의 루트 수정하기" : "나만의 직관 루트 만들기"}</h1></div>
          <Link href="/routes" className="writer-back">← 루트 둘러보기</Link>
        </div>
        <div className="writer-mobile-tabs" role="tablist" aria-label="루트 작성 도구">{writerTabs.map((item, index) => <button type="button" role="tab" key={item.id} id={`writer-tab-${item.id}`} aria-controls={item.id === "write" ? "writer-panel-write writer-panel-planner" : "writer-panel-chat"} aria-selected={tab === item.id} tabIndex={tab === item.id ? 0 : -1} onClick={() => changeTab(item.id)} onKeyDown={(event) => tabKey(event, index)}>{item.label}</button>)}</div>
        <form ref={formRef} onSubmit={submit} className="writer-form" aria-busy={saving}>
          <fieldset disabled={saving} className="writer-layout" data-active-tab={tab}>
            <legend className="sr-only">직관 루트 작성</legend>
            <section className="writer-card writer-planner-panel" id="writer-panel-planner" aria-labelledby="planner-heading">
              <div className="planner-heading-row">
                <div className="planner-mode-heading">
                  <h2 id="planner-heading" className="sr-only">코스 만들기 방법</h2>
                  <div className="planner-mode-tabs" role="group" aria-labelledby="planner-heading">
                    <button type="button" aria-pressed={plannerMode === "places"} disabled={plannerCompleted} onClick={() => setPlannerMode("places")}><span>01</span><strong>직접 코스 만들기</strong></button>
                    <button type="button" aria-pressed={plannerMode === "draw"} disabled={plannerCompleted} onClick={() => setPlannerMode("draw")}><span>02</span><strong>동선으로 코스 짜기</strong></button>
                  </div>
                  <p>{plannerMode === "places" ? "가고 싶은 장소를 골라 방문 순서대로 코스를 만들어보세요." : "지도 위를 차례로 눌러 한 가지 색상의 동선을 그려보세요."}</p>
                </div>
                <div className="writer-field planner-stadium-field"><label className="sr-only" htmlFor="route-stadium">구장 선택</label><select id="route-stadium" aria-label="구장 선택" value={stadiumCode} disabled={plannerCompleted} onChange={(event) => changeStadium(event.target.value)}>{stadiums.map((stadium) => <option key={stadium.code} value={stadium.code}>{stadium.name}</option>)}</select></div>
              </div>
              <NearbyRoutePlanner key={`${stadiumCode}:${plannerMode}`} plannerMode={plannerMode} stadium={current} stops={stops} onChange={changeStops} initialStart={start} onStartChange={changeStart} initialTravelMode={travelMode} travelMode={travelMode} courseApplied={courseApplied} onTravelModeChange={changeTravelMode} courseName={title} onCourseNameChange={(name) => { setTitle(name); markDirty(); }} onSaveCourse={() => saveCourse()} saving={saving} saveError={error} startWithAllPlaces={copying} onCompletionChange={setPlannerCompleted} />
            </section>
            <div className="writer-writing writer-panel" id="writer-panel-write" role="tabpanel" aria-labelledby="writer-tab-write" tabIndex={0}>
              <section className="writer-card">
                <div className="writer-section-title"><span>02</span><h2><label htmlFor="route-content">나만의 이야기를 담아보세요</label></h2></div>
                <div className="writer-field"><label htmlFor="route-title">루트 제목 <em>*</em></label><input id="route-title" value={title} onChange={(event) => { setTitle(event.target.value); markDirty(); }} maxLength={80} placeholder="예: 친구와 함께, 잠실에서 보내는 하루" required /><span className="writer-field-hint">함께 가는 사람에게 소개하듯 제목을 지어보세요. <b>{title.length}/80</b></span></div>
                <Editor id="route-content" value={content} format={contentFormat} disabled={saving} onChange={(value, format) => { setContent(value); setContentFormat(format); markDirty(); }} />
                <p className="writer-field-hint writer-content-tip">방문 순서, 이동 계획, 준비물을 적으면 함께 가는 사람에게 더 도움이 돼요.</p>
              </section>
            </div>

            <aside className="writer-chat-panel writer-panel" id="writer-panel-chat" role="tabpanel" aria-labelledby="writer-tab-chat" tabIndex={0}>
              <ChatPopup embedded title="채팅으로 만드는 직관 코스" conversationLabel={null} welcomeTitle="어떤 조건의 코스를 원하시나요?" welcomeDescription={null} welcomeLink={{ href: "/routes", label: "코스 둘러보기" }} />
            </aside>
          </fieldset>
          <div className="writer-save-area">
            {error && <div role="alert" className="writer-error">{error}</div>}
            <p className="writer-draft-status" role="status" aria-live="polite"><strong>{draftStatus}</strong><span>이 브라우저에만 임시저장되며 공개되지 않아요. 변경 1초 후 자동 저장하며 작성 중에는 5초마다 확인해요.</span></p>
            <div className="writer-save-row"><p><strong>{canSave ? "나의 직관 루트가 준비됐어요." : "코스 이름과 방문 장소를 채워주세요."}</strong><span>{existing?.legacy ? "이전 코스는 다시 저장하면 커뮤니티에 공개돼요." : "코스는 커뮤니티에 공개되고 편집 권한만 이 브라우저에 저장돼요."}</span></p><div className="writer-save-actions"><button className="button button-secondary" type="button" disabled={saving} onClick={() => { dirty.current = true; flushDraft(); }}>임시저장</button><button className="button button-primary" type="submit" disabled={!canSave || saving}>{saving ? <><span className="writer-spinner" aria-hidden="true" />저장하고 있어요</> : <><WriterIcon kind="save" />작성 완료</>}</button></div></div>
          </div>
        </form>
        <dialog ref={dialogRef} className="writer-confirm-dialog" aria-labelledby="writer-confirm-title" aria-describedby="writer-confirm-description" onCancel={(event) => { event.preventDefault(); setConfirmation(null); }}>
          {confirmation && <><span className="writer-confirm-icon"><WriterIcon kind="save" /></span><h2 id="writer-confirm-title">{confirmation.title}</h2><p id="writer-confirm-description">{confirmation.description}</p><div className="writer-confirm-actions"><button type="button" className="button button-secondary" autoFocus onClick={() => { const action = confirmation.cancelAction; setConfirmation(null); action?.(); }}>{confirmation.cancelLabel ?? "계속 작성하기"}</button><button type="button" className="button button-primary" onClick={() => { const action = confirmation.action; setConfirmation(null); action(); }}>{confirmation.label}</button></div></>}
        </dialog>
      </div>
    </main>
  );
}
