"use client";

import { useState } from "react";
import { pct } from "@/lib/scale";
import type { ProviderRun } from "@/lib/types";

type Row = {
  language: string;
  supported: boolean;
  clips: number;
  byProvider: Record<string, number | null>;
  metric: string;
};

export function CoverageTable({
  runs,
  supported,
  clipCounts,
}: {
  runs: ProviderRun[];
  supported: Record<string, boolean>;
  clipCounts: Record<string, number>;
}) {
  const [only, setOnly] = useState<"all" | "supported" | "unsupported">("all");

  const languages = new Set<string>();
  for (const r of runs) for (const a of r.by_language) languages.add(a.key[0]);

  const rows: Row[] = [...languages]
    .map((language) => {
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
    })
    .filter((r) =>
      only === "all" ? true : only === "supported" ? r.supported : !r.supported,
    )
    .sort((a, b) => (b.byProvider[runs[0]?.provider] ?? 0) - (a.byProvider[runs[0]?.provider] ?? 0));

  const totalUnsupported = Object.values(supported).filter((v) => !v).length;

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2 text-sm">
        {(["all", "supported", "unsupported"] as const).map((k) => (
          <button
            key={k}
            onClick={() => setOnly(k)}
            className={`rounded border px-3 py-1 ${
              only === k ? "border-[var(--accent)]" : "border-[var(--border)]"
            }`}
          >
            {k === "supported"
              ? "officially supported"
              : k === "unsupported"
                ? `no official support (${totalUnsupported})`
                : "all languages"}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left">
              <th className="py-2 pr-4 font-semibold">language</th>
              <th className="py-2 pr-4 font-semibold">official support</th>
              <th className="py-2 pr-4 text-right font-semibold">clips</th>
              {runs.map((r) => (
                <th key={r.provider} className="py-2 pr-4 text-right font-semibold">
                  {r.provider}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.language} className="border-b border-[var(--border)]/60">
                <td className="py-2 pr-4">{row.language}</td>
                <td className="py-2 pr-4 text-[var(--muted)]">
                  {row.supported ? "yes" : "no"}
                </td>
                <td className="tabular py-2 pr-4 text-right text-[var(--muted)]">
                  {row.clips || "-"}
                </td>
                {runs.map((r) => (
                  <td key={r.provider} className="tabular py-2 pr-4 text-right">
                    {pct(row.byProvider[r.provider])}
                    <span className="ml-1 text-xs text-[var(--muted)]">{row.metric}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-[var(--muted)]">
        CER is reported as primary for Dravidian languages, where one long
        agglutinated token can carry a whole clause and word error rate
        over-punishes a single wrong morpheme.
      </p>
    </div>
  );
}
