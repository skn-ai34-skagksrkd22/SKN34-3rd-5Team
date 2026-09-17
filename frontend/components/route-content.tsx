"use client";

import { createElement, useMemo, useSyncExternalStore, type ReactNode } from "react";
import { routeContentToText, safeRouteLink, type RouteContentFormat } from "@/lib/route-content";
import { CommunityPostContent } from "@/components/community-post-content";
import type { RichContentDoc } from "@/lib/community-rich-content";

const subscribe = () => () => {};
const allowedTags = new Set(["p", "br", "strong", "b", "em", "i", "u", "s", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "a", "hr", "table", "thead", "tbody", "tr", "th", "td", "figure", "figcaption"]);
const omitContents = new Set(["script", "style", "iframe", "object", "embed", "svg", "math", "template", "form", "input", "button", "textarea", "select"]);

/** Rebuild supported rich text as React nodes. Never inject user-supplied HTML. */
function renderNode(node: Node, key: string, depth = 0): ReactNode {
  if (depth > 24) return null;
  if (node.nodeType === 3) return node.textContent;
  if (node.nodeType !== 1) return null;
  const element = node as Element;
  const tag = element.tagName.toLowerCase();
  if (omitContents.has(tag)) return null;
  const children = Array.from(element.childNodes).map((child, index) => renderNode(child, `${key}-${index}`, depth + 1));
  if (!allowedTags.has(tag)) return children;
  const props: Record<string, unknown> = { key };
  if (tag === "a") {
    const href = safeRouteLink(element.getAttribute("href"));
    if (!href) return children;
    Object.assign(props, { href, target: "_blank", rel: "noopener noreferrer" });
  }
  if (tag === "th" || tag === "td") {
    for (const [source, target] of [["colspan", "colSpan"], ["rowspan", "rowSpan"]]) {
      const value = Number(element.getAttribute(source));
      if (Number.isInteger(value) && value > 1 && value <= 12) props[target] = value;
    }
  }
  return createElement(tag, props, ...children);
}

export function RouteContent({ content, format, contentDoc }: { content: string; format?: RouteContentFormat; contentDoc?: RichContentDoc | null }) {
  const hydrated = useSyncExternalStore(subscribe, () => true, () => false);
  const richContent = useMemo(() => {
    if (!hydrated || format !== "html") return null;
    const document = new DOMParser().parseFromString(content, "text/html");
    return Array.from(document.body.childNodes).map((node, index) => renderNode(node, String(index)));
  }, [content, format, hydrated]);
  if (contentDoc) return <div className="route-rich-content"><CommunityPostContent content={content} document={contentDoc} /></div>;
  if (richContent) return <div className="route-rich-content">{richContent}</div>;
  return <div className="route-plain-content">{routeContentToText(content, format).split(/\n\n+/).map((paragraph, index) => <p key={index} style={{ whiteSpace: "pre-wrap" }}>{paragraph}</p>)}</div>;
}
