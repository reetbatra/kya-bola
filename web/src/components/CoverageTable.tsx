"use client";

import { useMemo, useState } from "react";
import { barWidth, fillFor, pct } from "@/lib/scale";
import type { ProviderRun } from "@/lib/types";

type Row = {
  language: string;
  supported: boolean;
  clips: number;
  byProvider: Record<string, number | null>;
  metric: string;
};

type Filter = "all" | "supported" | "unsupported";
type SortKey = "rate" | "language" | "clips";

export function CoverageTable({
  runs,
  supported,
}: {
  runs: ProviderRun[];
  supported: Record<string, boolean>;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<SortKey>("rate");

  const primary = runs[0]?.provider;

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
      return { language, supported: supported[language] ?? false, clips, byProvider, metric };
    });
  }, [runs, supported]);

  const visible = useMemo(() => {
    const filtered = rows.filter((r) =>
      filter === "all" ? true : filter === "supported" ? r.supported : !r.supported,
    );
    return filtered.sort((a, b) => {
      if (sort === "language") return a.language.localeCompare(b.language);
      if (sort === "clips") return b.clips - a.clips;
      return (b.byProvider[primary] ?? -1) - (a.byProvider[primary] ?? -1);
    });
  }, [rows, filter, sort, primary]);

  const unsupportedCount = Object.values(supported).filter((v) => !v).length;

  const tabs: Array<{ key: Filter; label: string }> = [
    { key: "all", label: "all languages" },
    { key: "supported", label: "officially supported" },
    { key: "unsupported", label: `no official support (${unsupportedCount})` },
  ];

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-4">
        <div role="group" aria-label="Filter languages" className="flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              aria-pressed={filter === t.key}
              className={`min-h-11 cursor-pointer rounded-full border px-4 text-sm transition-colors duration-200 ${
                filter === t.key
                  ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--on-accent)]"
                  : "border-[var(--border)] hover:border-[var(--accent)]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="sort" className="text-[var(--muted)]">
            sort
          </label>
          <select
            id="sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="min-h-11 cursor-pointer rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-[var(--text)]"
          >
            <option value="rate">worst first</option>
            <option value="language">A to Z</option>
            <option value="clips">most clips</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <caption className="sr-only">
            Error rate by language and provider, with whether each language is
            officially supported.
          </caption>
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-left">
              <th scope="col" className="px-4 py-3 font-semibold">language</th>
              <th scope="col" className="px-4 py-3 font-semibold">official support</th>
              <th scope="col" className="px-4 py-3 text-right font-semibold">clips</th>
              {runs.map((r) => (
                <th key={r.provider} scope="col" className="px-4 py-3 font-semibold">
                  {r.provider}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr
                key={row.language}
                className="border-b border-[var(--border)]/60 transition-colors duration-200 last:border-0 hover:bg-[var(--surface-2)]"
              >
                <th scope="row" className="px-4 py-2.5 text-left font-normal">
                  {row.language}
                </th>
                <td className="px-4 py-2.5">
                  {/* Text, not just a colour, so the distinction survives greyscale. */}
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs ${
                      row.supported
                        ? "bg-[var(--surface-2)] text-[var(--text)]"
                        : "text-[var(--muted)]"
                    }`}
                  >
                    {row.supported ? "listed" : "not listed"}
                  </span>
                </td>
                <td className="tabular px-4 py-2.5 text-right text-[var(--muted)]">
                  {row.clips || "—"}
                </td>
                {runs.map((r) => {
                  const v = row.byProvider[r.provider];
                  return (
                    <td key={r.provider} className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="tabular w-16 text-right">{pct(v)}</span>
                        <span
                          aria-hidden
                          className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]"
                        >
                          <span
                            className="block h-full rounded-full"
                            style={{ width: `${barWidth(v)}%`, background: fillFor(v) }}
                          />
                        </span>
                        <span className="w-7 text-xs text-[var(--muted)]">{row.metric}</span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 space-y-2 text-xs leading-relaxed text-[var(--muted)]">
        <p>
          CER is reported as primary for Dravidian languages, where one long
          agglutinated token can carry a whole clause and word error rate
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
