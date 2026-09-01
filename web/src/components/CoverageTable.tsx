"use client";

import { useDeferredValue, useId, useMemo, useState } from "react";
import { barWidth, fillFor, pct } from "@/lib/scale";
import type { ProviderRun } from "@/lib/types";
import { nf, providerLabel } from "@/lib/format";

type Row = {
  language: string;
  supported: boolean;
  clips: number;
  byProvider: Record<string, number | null>;
  best: string | null;
  metric: string;
};

type Filter = "all" | "supported" | "unsupported";
type SortKey = "language" | "clips" | string;

/** Column header that also carries the current sort direction. Declared at
 *  module scope so React keeps its identity across renders. */
function SortButton({
  label,
  sortKey,
  active,
  desc,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  active: boolean;
  desc: boolean;
  onSort: (key: SortKey) => void;
}) {
  return (
    <button
      onClick={() => onSort(sortKey)}
      className={`group inline-flex cursor-pointer items-center gap-1 transition-colors duration-200 ${
        active ? "text-[var(--text)]" : "text-[var(--muted)] hover:text-[var(--text)]"
      }`}
    >
      {label}
      <svg
        viewBox="0 0 10 10"
        aria-hidden
        className={`h-2.5 w-2.5 transition-opacity duration-200 ${
          active ? "opacity-100" : "opacity-0 group-hover:opacity-50"
        } ${desc ? "" : "rotate-180"}`}
      >
        <path d="M5 8L1.5 3.5h7L5 8Z" fill="currentColor" />
      </svg>
    </button>
  );
}

export function CoverageTable({
  runs,
  supported,
}: {
  runs: ProviderRun[];
  supported: Record<string, boolean>;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  // Sort key and direction are one piece of state: they always change together,
  // and splitting them lets two clicks in the same tick read a stale key and
  // fail to flip.
  const [order, setOrder] = useState<{ key: SortKey; desc: boolean }>({
    key: runs[0]?.provider ?? "language",
    desc: true,
  });
  const { key: sort, desc } = order;
  const searchId = useId();
  const deferred = useDeferredValue(query);

  const rows = useMemo<Row[]>(() => {
    const names = new Set<string>();
    for (const r of runs) for (const a of r.by_language) names.add(a.key[0]);

    return [...names].map((language) => {
      const byProvider: Record<string, number | null> = {};
      let clips = 0;
      let metric = "wer";
      for (const r of runs) {
        const hit = r.by_language.find((a) => a.key[0] === language);
        byProvider[r.provider] = hit?.primary ?? null;
        clips = Math.max(clips, hit?.scored ?? 0);
        if (hit) metric = hit.primary_metric;
      }
      // Lowest error wins the row. Recorded so the table can mark it without
      // recomputing per cell.
      const scored = Object.entries(byProvider).filter(
        (e): e is [string, number] => e[1] !== null,
      );
      const best =
        scored.length > 1
          ? scored.reduce((a, b) => (b[1] < a[1] ? b : a))[0]
          : null;

      return {
        language,
        supported: supported[language] ?? false,
        clips,
        byProvider,
        best,
        metric,
      };
    });
  }, [runs, supported]);

  const visible = useMemo(() => {
    const needle = deferred.trim().toLowerCase();
    const filtered = rows.filter((r) => {
      if (needle && !r.language.toLowerCase().includes(needle)) return false;
      return filter === "all" ? true : filter === "supported" ? r.supported : !r.supported;
    });
    const dir = desc ? 1 : -1;
    return [...filtered].sort((a, b) => {
      if (sort === "language") return a.language.localeCompare(b.language) * -dir;
      if (sort === "clips") return (b.clips - a.clips) * dir;
      // Unscored languages sort to the bottom in both directions rather than
      // being treated as a zero error rate.
      const av = a.byProvider[sort];
      const bv = b.byProvider[sort];
      if (av === null && bv === null) return a.language.localeCompare(b.language);
      if (av === null) return 1;
      if (bv === null) return -1;
      return (bv - av) * dir;
    });
  }, [rows, filter, deferred, sort, desc]);

  const unsupportedCount = Object.values(supported).filter((v) => !v).length;

  const tabs: Array<{ key: Filter; label: string; count: number }> = [
    { key: "all", label: "all", count: rows.length },
    { key: "supported", label: "officially supported", count: rows.length - unsupportedCount },
    { key: "unsupported", label: "no official support", count: unsupportedCount },
  ];

  // `desc` means the arrow points down, in whatever the column's own terms are:
  // largest first for numbers, Z to A for names. A column being sorted for the
  // first time opens on its useful default, which for names is A to Z.
  function toggleSort(key: SortKey) {
    setOrder((o) => (o.key === key ? { key, desc: !o.desc } : { key, desc: key !== "language" }));
  }

  function ariaSort(key: SortKey): "ascending" | "descending" | "none" {
    if (sort !== key) return "none";
    return desc ? "descending" : "ascending";
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-3">
        <div
          role="group"
          aria-label="Filter languages"
          className="inline-flex flex-wrap gap-1 rounded-full border border-[var(--border)] bg-[var(--surface-2)] p-1"
        >
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              aria-pressed={filter === t.key}
              className={`min-h-9 cursor-pointer rounded-full px-3.5 text-sm transition-colors duration-200 ${
                filter === t.key
                  ? "bg-[var(--surface)] font-medium text-[var(--text)] shadow-[var(--shadow-sm)]"
                  : "text-[var(--muted)] hover:text-[var(--text)]"
              }`}
            >
              {t.label}
              <span className="tabular ml-1.5 text-xs opacity-60">{t.count}</span>
            </button>
          ))}
        </div>

        <div className="relative ml-auto">
          <label htmlFor={searchId} className="sr-only">
            Filter by language name
          </label>
          <svg
            viewBox="0 0 16 16"
            aria-hidden
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--muted)]"
          >
            <circle
              cx="7"
              cy="7"
              r="4.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
            />
            <path d="M10.5 10.5 14 14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          <input
            id={searchId}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find a language"
            className="min-h-11 w-56 rounded-lg border border-[var(--border-2)] bg-[var(--surface)] pl-9 pr-3 text-sm text-[var(--text)] transition-colors duration-200 placeholder:text-[var(--muted)] hover:border-[var(--accent)] focus:border-[var(--accent)]"
          />
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-sm)]">
        <table className="w-full min-w-[680px] border-collapse text-sm">
          <caption className="sr-only">
            Error rate by language and provider, with whether each language is
            officially supported. Column headers sort the table.
          </caption>
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-left">
              <th
                scope="col"
                aria-sort={ariaSort("language")}
                className="sticky left-0 z-10 bg-[var(--surface-2)] px-4 py-3 text-xs font-semibold uppercase tracking-wide"
              >
                <SortButton
                  label="language" sortKey="language"
                  active={sort === "language"}
                  desc={desc}
                  onSort={toggleSort}
                />
              </th>
              <th scope="col" className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                support
              </th>
              <th
                scope="col"
                aria-sort={ariaSort("clips")}
                className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide"
              >
                <SortButton
                  label="clips" sortKey="clips"
                  active={sort === "clips"}
                  desc={desc}
                  onSort={toggleSort}
                />
              </th>
              {runs.map((r) => (
                <th
                  key={r.provider}
                  scope="col"
                  aria-sort={ariaSort(r.provider)}
                  title={r.provider}
                  className="px-4 py-3 text-xs font-semibold uppercase tracking-wide"
                >
                  <SortButton
                    label={providerLabel(r.provider)}
                    sortKey={r.provider}
                    active={sort === r.provider}
                    desc={desc}
                    onSort={toggleSort}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr
                key={row.language}
                className="group border-b border-[var(--border)] transition-colors duration-150 last:border-0 hover:bg-[var(--bg-tint)]"
              >
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-[var(--surface)] px-4 py-2.5 text-left font-medium text-[var(--text)] transition-colors duration-150 group-hover:bg-[var(--bg-tint)]"
                >
                  {row.language}
                </th>
                <td className="px-4 py-2.5">
                  {/* Text, not just a colour, so the distinction survives greyscale. */}
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs ${
                      row.supported
                        ? "bg-[var(--accent-tint)] text-[var(--accent-hover)]"
                        : "border border-[var(--border-2)] text-[var(--muted)]"
                    }`}
                  >
                    {row.supported ? "listed" : "not listed"}
                  </span>
                </td>
                <td className="tabular px-4 py-2.5 text-right text-[var(--muted)]">
                  {row.clips ? nf.format(row.clips) : "—"}
                </td>
                {runs.map((r) => {
                  const v = row.byProvider[r.provider];
                  const isBest = row.best === r.provider;
                  return (
                    <td key={r.provider} className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span
                          className={`tabular w-16 text-right ${
                            isBest ? "font-semibold text-[var(--text)]" : "text-[var(--text-2)]"
                          }`}
                        >
                          {pct(v)}
                          {isBest && <span className="sr-only"> (best of the models)</span>}
                        </span>
                        <span
                          aria-hidden
                          className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface-3)]"
                        >
                          <span
                            className="block h-full rounded-full"
                            style={{ width: `${barWidth(v)}%`, background: fillFor(v) }}
                          />
                        </span>
                        <span className="w-7 text-xs uppercase text-[var(--muted)]">
                          {row.metric}
                        </span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>

        {visible.length === 0 && (
          <p className="px-4 py-10 text-center text-sm text-[var(--muted)]">
            No language matches “{query}” in this filter.
          </p>
        )}
      </div>

      <div className="prose-note mt-4 space-y-2 text-xs leading-relaxed text-[var(--muted)]">
        <p>
          The bolder figure in each row is the lowest error rate of the models
          tested. CER is reported as primary for Dravidian languages, where one
          long agglutinated token can carry a whole clause and word error rate
          over-punishes a single wrong morpheme.
        </p>
        <p>
          Rates above 100% are real, not a bug. Word error rate counts insertions
          as well as substitutions and deletions, so a model returning more words
          than were spoken can exceed the length of the reference. It usually
          means the model is producing fluent text in the wrong language rather
          than declining to answer.
        </p>
      </div>
    </div>
  );
}
