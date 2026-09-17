"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { reportCommunityPost } from "@/lib/community-api";
import { useMemberAuth } from "@/lib/member-auth";
import styles from "./community-interactions.module.css";

type ReportReason = "spam" | "abuse" | "inappropriate" | "privacy" | "other";

export function PostReportButton({ postNumber, postId }: { postNumber: string; postId?: string }) {
  const { user } = useMemberAuth();
  const actorId = user?.id ?? null;
  if (!actorId) return null;
  return <PostReportButtonContent key={`${postId ?? postNumber}:${actorId ?? "anonymous"}`} postNumber={postNumber} postId={postId} actorId={actorId} />;
}

function PostReportButtonContent({ postNumber, postId, actorId }: { postNumber: string; postId?: string; actorId: number | null }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const mounted = useRef(true);
  const [reason, setReason] = useState<ReportReason>("spam");
  const [detail, setDetail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!postId) { setError("게시글 연결이 완료된 뒤 신고할 수 있어요."); return; }
    if (!actorId) { setError("신고하려면 로그인해 주세요."); return; }
    setSubmitting(true); setError(""); setMessage("");
    try {
      const result = await reportCommunityPost(postId, reason, detail.trim());
      if (!mounted.current) return;
      setMessage(result.created ? "신고를 접수했어요." : "이미 접수된 신고예요.");
      dialog.current?.close();
    } catch (caught) {
      if (mounted.current) setError(caught instanceof Error ? caught.message : "신고를 접수하지 못했어요.");
    } finally {
      if (mounted.current) setSubmitting(false);
    }
  }

  return <div className={styles.reportActions}>
    <button ref={trigger} type="button" className={styles.reportButton} onClick={() => { setError(""); dialog.current?.showModal(); }}><span aria-hidden="true">🚨</span> 신고</button>
    {message && <p role="status" className={styles.reportStatus}>{message}</p>}
    <dialog ref={dialog} className={styles.dialog} aria-label="게시글 신고" onClose={() => trigger.current?.focus()}>
      <form onSubmit={event => void submit(event)}>
        <h2>게시글 신고</h2>
        <p>게시글 번호 {postNumber}</p>
        <label>신고 사유<select value={reason} onChange={event => setReason(event.target.value as ReportReason)}><option value="spam">광고·도배</option><option value="abuse">욕설·비방</option><option value="inappropriate">부적절한 내용</option><option value="privacy">개인정보 노출</option><option value="other">기타</option></select></label>
        <label className={styles.reportReason}>상세 사유<textarea value={detail} onChange={event => setDetail(event.target.value)} maxLength={50} rows={3} placeholder="신고 사유를 50자 이내로 입력해 주세요." aria-describedby="report-reason-count" /></label>
        <span id="report-reason-count" className={styles.reportReasonCount}>{detail.length}/50자</span>
        {error && <p role="alert" className={styles.errorNote}>{error}</p>}
        <div className={styles.dialogActions}><button type="button" disabled={submitting} onClick={() => dialog.current?.close()}>취소</button><button type="submit" disabled={submitting}>{submitting ? "접수 중" : "신고 접수"}</button></div>
      </form>
    </dialog>
  </div>;
}
