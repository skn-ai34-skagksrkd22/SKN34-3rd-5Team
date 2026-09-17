"use client";

import { useEffect } from "react";

/** Align editorial pages with the visible space between the brand and account button. */
export function HeaderContentBounds() {
  useEffect(() => {
    const header = document.querySelector<HTMLElement>(".site-header");
    const brand = header?.querySelector<HTMLElement>(".header-inner > .brand");
    if (!header || !brand) return;

    const root = document.documentElement;
    let observedButton: HTMLElement | null = null;
    const resizeObserver = new ResizeObserver(update);

    function update() {
      const button = header!.querySelector<HTMLElement>(".header-signup");
      if (button !== observedButton) {
        if (observedButton) resizeObserver.unobserve(observedButton);
        if (button) resizeObserver.observe(button);
        observedButton = button;
      }
      if (!button) { root.classList.remove("header-bounds-ready"); return; }

      const left = brand!.getBoundingClientRect().right;
      const right = button.getBoundingClientRect().left;
      if (right - left < 400) { root.classList.remove("header-bounds-ready"); return; }
      root.style.setProperty("--header-content-left", `${left}px`);
      root.style.setProperty("--header-content-width", `${right - left}px`);
      root.classList.add("header-bounds-ready");
    }

    resizeObserver.observe(header);
    resizeObserver.observe(brand);
    const mutationObserver = new MutationObserver(update);
    mutationObserver.observe(header, { childList: true, subtree: true });
    window.addEventListener("resize", update);
    update();
    return () => {
      window.removeEventListener("resize", update);
      mutationObserver.disconnect();
      resizeObserver.disconnect();
      root.classList.remove("header-bounds-ready");
      root.style.removeProperty("--header-content-left");
      root.style.removeProperty("--header-content-width");
    };
  }, []);

  return null;
}
