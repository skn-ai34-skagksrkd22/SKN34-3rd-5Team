"use client";

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { uploadCommunityImage } from "@/lib/community-api";
import { communityImageUrl, readRichEditor, richColors, richFonts, richSizes, richText, writeRichEditor, type RichContentDoc } from "@/lib/community-rich-content";
import { memberFetch } from "@/lib/member-auth-request";
import styles from "./community-post-editor.module.css";

type Props = { initial?: RichContentDoc | null; disabled: boolean; onChange: (doc: RichContentDoc, content: string) => void; onUploadingChange: (uploading: boolean) => void; onError: (message: string) => void;
  id?: string; label?: string; placeholder?: string; maxLength?: number; imageUploadDisabled?: boolean; notifyInitial?: boolean };
const fontCommands = { sans: "Arial", serif: "Georgia", mono: "Courier New" } as const;
const htmlSizes = { 12: "1", 14: "2", 16: "3", 18: "4", 20: "5", 24: "6", 32: "7" } as const;

export function CommunityRichEditor({ initial, disabled, onChange, onUploadingChange, onError, id = "community-post-content", label = "게시글 내용",
  placeholder = "야구 이야기를 자유롭게 적어 주세요.", maxLength = 20000, imageUploadDisabled = false, notifyInitial = true }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const changeCallback = useRef(onChange);
  const fileInput = useRef<HTMLInputElement>(null);
  const selection = useRef<Range | null>(null);
  const previewUrls = useRef(new Set<string>());
  const [counts, setCounts] = useState({ text: 0, images: 0 });
  const [uploading, setUploading] = useState(false);

  useEffect(() => { changeCallback.current = onChange; }, [onChange]);

  useEffect(() => () => {
    for (const url of previewUrls.current) URL.revokeObjectURL(url);
    previewUrls.current.clear();
  }, []);

  useEffect(() => {
    if (!root.current) return;
    if (initial && (richText(initial) || initial.blocks.some(block => block.type === "image"))) writeRichEditor(root.current, initial);
    else root.current.replaceChildren();
    const document = readRichEditor(root.current);
    setCounts({ text: document.blocks.filter(block => block.type === "paragraph").reduce((total, block) => total + block.runs.reduce((sum, run) => sum + run.text.length, 0), 0), images: document.blocks.filter(block => block.type === "image").length });
    if (initial && notifyInitial) changeCallback.current(document, richText(document));
    const controller = new AbortController();
    for (const image of root.current.querySelectorAll<HTMLImageElement>("img[data-image-id]")) {
      const imageId = image.dataset.imageId;
      if (!imageId) continue;
      void memberFetch(communityImageUrl(imageId), { signal: controller.signal }).then(async response => {
        if (!response.ok || controller.signal.aborted || !image.isConnected) return;
        const url = URL.createObjectURL(await response.blob());
        previewUrls.current.add(url);
        image.src = url;
      }).catch(() => {});
    }
    return () => controller.abort();
  }, [initial, notifyInitial]);

  function rememberSelection() {
    const active = window.getSelection();
    if (active?.rangeCount && root.current?.contains(active.anchorNode)) selection.current = active.getRangeAt(0).cloneRange();
  }

  function restoreSelection() {
    const editor = root.current;
    if (!editor) return;
    editor.focus();
    const active = window.getSelection();
    if (!active) return;
    active.removeAllRanges();
    if (selection.current && editor.contains(selection.current.commonAncestorContainer)) active.addRange(selection.current);
    else {
      const range = document.createRange();
      range.selectNodeContents(editor); range.collapse(false); active.addRange(range);
    }
  }

  function sync() {
    if (!root.current) return;
    const doc = readRichEditor(root.current);
    const text = doc.blocks.filter(block => block.type === "paragraph").reduce((total, block) => total + block.runs.reduce((sum, run) => sum + run.text.length, 0), 0);
    setCounts({ text, images: doc.blocks.filter(block => block.type === "image").length });
    onChange(doc, richText(doc));
    rememberSelection();
  }

  function command(name: string, value?: string) {
    if (disabled || uploading) return;
    restoreSelection();
    document.execCommand(name, false, value);
    sync();
  }

  async function addImages(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (!files.length || disabled || uploading) return;
    if (imageUploadDisabled) { onError("이미지를 첨부하려면 로그인해 주세요."); return; }
    if (counts.images + files.length > 10) { onError("이미지는 10장까지 첨부할 수 있어요."); return; }
    setUploading(true); onUploadingChange(true); onError("");
    try {
      for (const file of files) {
        const id = await uploadCommunityImage(file);
        const preview = URL.createObjectURL(file);
        previewUrls.current.add(preview);
        restoreSelection();
        const inserted = document.execCommand("insertImage", false, preview);
        const insertedImage = Array.from(root.current?.querySelectorAll("img") ?? []).find(image => image.src === preview);
        if (insertedImage) insertedImage.dataset.imageId = id;
        if ((!inserted || !insertedImage) && root.current) {
          const image = document.createElement("img");
          image.src = preview;
          image.dataset.imageId = id;
          image.alt = "첨부 이미지";
          const active = window.getSelection();
          const range = active?.rangeCount ? active.getRangeAt(0) : document.createRange();
          if (!active?.rangeCount) { range.selectNodeContents(root.current); range.collapse(false); }
          range.insertNode(image);
          range.setStartAfter(image); range.collapse(true);
          active?.removeAllRanges(); active?.addRange(range);
        }
        sync();
      }
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "이미지를 올리지 못했어요.");
    } finally {
      setUploading(false); onUploadingChange(false);
    }
  }

  const controlDisabled = disabled || uploading;
  return <div className={styles.richEditor}>
    <div className={styles.attachmentBar}>
      <button type="button" onMouseDown={rememberSelection} onClick={() => fileInput.current?.click()} disabled={controlDisabled || imageUploadDisabled}>▣ 이미지 첨부</button>
      <span>JPG·PNG·WEBP · 장당 5MB · 최대 10장{uploading ? " · 업로드 중…" : ""}</span>
      <input ref={fileInput} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={event => void addImages(event)} aria-label={`${label} 이미지 선택`} disabled={controlDisabled || imageUploadDisabled} />
    </div>
    <div className={styles.formatBar} role="toolbar" aria-label="본문 서식">
      <label>글꼴<select aria-label="글꼴" defaultValue="sans" onMouseDown={rememberSelection} onChange={event => command("fontName", fontCommands[event.target.value as keyof typeof fontCommands])} disabled={controlDisabled}>{Object.keys(richFonts).map(font => <option key={font} value={font}>{font === "sans" ? "고딕" : font === "serif" ? "명조" : "고정폭"}</option>)}</select></label>
      <label>크기<select aria-label="글자 크기" defaultValue="16" onMouseDown={rememberSelection} onChange={event => command("fontSize", htmlSizes[Number(event.target.value) as keyof typeof htmlSizes])} disabled={controlDisabled}>{richSizes.filter(size => size !== 28).map(size => <option key={size} value={size}>{size}px</option>)}</select></label>
      <label>색상<select aria-label="글자 색상" defaultValue="#26354b" onMouseDown={rememberSelection} onChange={event => command("foreColor", event.target.value)} disabled={controlDisabled}>{richColors.map(color => <option key={color} value={color}>{color === "#26354b" ? "기본" : color === "#e1131b" ? "빨강" : color === "#246bf3" ? "파랑" : color === "#18825c" ? "초록" : "보라"}</option>)}</select></label>
      <span className={styles.toolbarDivider} />
      {[["bold", "굵게", "가"], ["italic", "기울임", "가"], ["underline", "밑줄", "가"]].map(([name, label, icon]) => <button key={name} type="button" title={label} aria-label={label} onMouseDown={event => { event.preventDefault(); rememberSelection(); }} onClick={() => command(name)} disabled={controlDisabled} className={name === "bold" ? styles.boldIcon : name === "italic" ? styles.italicIcon : styles.underlineIcon}>{icon}</button>)}
      <span className={styles.toolbarDivider} />
      {[["justifyLeft", "왼쪽 정렬", "☰"], ["justifyCenter", "가운데 정렬", "≡"], ["justifyRight", "오른쪽 정렬", "☷"]].map(([name, label, icon]) => <button key={name} type="button" title={label} aria-label={label} onMouseDown={event => { event.preventDefault(); rememberSelection(); }} onClick={() => command(name)} disabled={controlDisabled}>{icon}</button>)}
      <span className={styles.toolbarDivider} />
      <button type="button" title="되돌리기" aria-label="되돌리기" onMouseDown={event => event.preventDefault()} onClick={() => command("undo")} disabled={controlDisabled}>↶</button>
      <button type="button" title="앞돌리기" aria-label="앞돌리기" onMouseDown={event => event.preventDefault()} onClick={() => command("redo")} disabled={controlDisabled}>↷</button>
    </div>
    <div ref={root} id={id} className={styles.editable} role="textbox" aria-label={label} aria-multiline="true" contentEditable={!disabled} suppressContentEditableWarning data-placeholder={placeholder} onInput={sync} onKeyUp={rememberSelection} onMouseUp={rememberSelection} onBlur={rememberSelection} onPaste={event => { event.preventDefault(); document.execCommand("insertText", false, event.clipboardData.getData("text/plain")); sync(); }} />
    <p className={styles.count}>{counts.text.toLocaleString()} / {maxLength.toLocaleString()}자 · 이미지 {counts.images} / 10</p>
  </div>;
}
