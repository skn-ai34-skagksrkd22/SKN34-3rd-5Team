import { communityImageUrl, richFonts, type RichContentDoc } from "@/lib/community-rich-content";
import styles from "./community-post-content.module.css";

export function CommunityPostContent({ content, document }: { content: string; document?: RichContentDoc | null }) {
  if (!document) return <div>{content}</div>;
  return <div className={styles.richContent}>
    {document.blocks.map((block, index) => block.type === "image"
      ? <figure key={`${index}-${block.id}`}><img src={communityImageUrl(block.id)} alt="게시글 첨부 이미지" loading="lazy" /></figure>
      : <p key={index} style={{ textAlign: block.align }}>{block.runs.length ? block.runs.map((run, runIndex) =>
        <span key={runIndex} style={{ fontFamily: richFonts[run.font], fontSize: run.size, color: run.color, fontWeight: run.bold ? 700 : 400, fontStyle: run.italic ? "italic" : "normal", textDecoration: run.underline ? "underline" : "none" }}>{run.text}</span>) : "\u00a0"}</p>)}
  </div>;
}
