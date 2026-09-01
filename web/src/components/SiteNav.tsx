"use client";

import { useEffect, useState } from "react";

const SECTIONS = [
  { id: "map", label: "The map" },
  { id: "coverage", label: "Coverage gap" },
  { id: "method", label: "Method" },
];

/**
 * Sticky section nav.
 *
 * The page is one long read with three anchors, so the nav exists to say where
 * you are as much as to move you. The active section is tracked with an
 * IntersectionObserver rather than scroll maths: it costs nothing on the main
 * thread and does not fight smooth scrolling.
 */
export function SiteNav() {
  const [active, setActive] = useState<string>("");
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setActive(visible.target.id);
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0 },
    );
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }

    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  return (
    <div
      className={`sticky top-0 z-40 border-b bg-[var(--bg)]/85 backdrop-blur-md transition-colors duration-200 ${
        scrolled ? "border-[var(--border)]" : "border-transparent"
      }`}
    >
      <nav
        aria-label="Sections"
        className="mx-auto flex h-[var(--nav-h)] max-w-6xl items-center gap-6 px-6"
      >
        <a
          href="#top"
          className="serif shrink-0 text-base text-[var(--text)] transition-colors duration-200 hover:text-[var(--accent)]"
        >
          kya bola?
        </a>

        <ul className="hidden items-center gap-1 sm:flex">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                aria-current={active === s.id ? "true" : undefined}
                className={`inline-flex h-8 items-center rounded-full px-3 text-sm transition-colors duration-200 ${
                  active === s.id
                    ? "bg-[var(--accent-tint)] text-[var(--accent-hover)]"
                    : "text-[var(--muted)] hover:text-[var(--text)]"
                }`}
              >
                {s.label}
              </a>
            </li>
          ))}
        </ul>

        <a
          href="https://github.com/reetbatra/kya-bola"
          className="ml-auto inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-[var(--border-2)] px-3.5 text-sm text-[var(--text-2)] transition-colors duration-200 hover:border-[var(--accent)] hover:text-[var(--accent-hover)]"
        >
          <svg viewBox="0 0 24 24" aria-hidden className="h-4 w-4 fill-current">
            <path d="M12 .5a12 12 0 0 0-3.79 23.4c.6.11.82-.26.82-.58v-2.2c-3.34.72-4.04-1.42-4.04-1.42-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.1-.78.42-1.31.76-1.61-2.67-.3-5.47-1.34-5.47-5.96 0-1.31.47-2.39 1.24-3.23-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.92 1.23 3.23 0 4.63-2.8 5.65-5.48 5.95.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.83.58A12 12 0 0 0 12 .5Z" />
          </svg>
          Source
        </a>
      </nav>
    </div>
  );
}
