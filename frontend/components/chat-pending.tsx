export function ChatPending({ busy, streaming, className }: { busy: boolean; streaming: string; className: string }) {
  if (!busy || streaming) return null;
  return <div className={className} role="status"><span>응답 준비 중…</span><i /><i /><i /></div>;
}
