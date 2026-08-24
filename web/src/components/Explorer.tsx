"use client";

import { useMemo, useState } from "react";
import type { Topology } from "topojson-specification";
import { IndiaMap } from "./IndiaMap";
import { LEGEND, NO_DATA_FILL, pct } from "@/lib/scale";
import { HUMAN_FLOOR, type ProviderRun } from "@/lib/types";

type Props = {
  topology: Topology;
  runs: ProviderRun[];
  unmapped: Array<{ state: string; district: string; reason: string }>;
};

function valuesFor(run: ProviderRun, language: string | null) {
  const out: Record<string, number | null> = {};
  const rows = language
    ? run.by_language_district.filter((a) => a.key[0] === language)
    : run.by_district;
  for (const a of rows) out[language ? a.key[1] : a.key[0]] = a.primary;
  return out;
}

export function Explorer({ topology, runs, unmapped }: Props) {
  const [providerName, setProvider] = useState(runs[0]?.provider ?? "");
  const [language, setLanguage] = useState<string | null>(null);

  const run = runs.find((r) => r.provider === providerName) ?? runs[0];

  const languages = useMemo(() => {
    const names = new Set<string>();
    for (const r of runs) for (const a of r.by_language) names.add(a.key[0]);
    return [...names].sort();
  }, [runs]);

  const values = useMemo(() => (run ? valuesFor(run, language) : {}), [run, language]);
  const measured = Object.values(values).filter((v) => v !== null).length;

  if (!run) {
    return (
      <p className="text-[var(--muted)]">
        No results yet. Run the harness, then rebuild.
      </p>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
      <div>
        <div className="mb-4 flex flex-wrap gap-2">
          {runs.map((r) => (
            <button
              key={r.provider}
              onClick={() => setProvider(r.provider)}
              className={`rounded-full border px-3 py-1 text-sm transition ${
                r.provider === providerName
                  ? "border-[var(--accent)] bg-[var(--accent)] text-white"
                  : "border-[var(--border)] hover:border-[var(--accent)]"
              }`}
            >
              {r.provider}
            </button>
          ))}
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
          <label htmlFor="language" className="text-[var(--muted)]">
            language
          </label>
          <select
            id="language"
            value={language ?? ""}
            onChange={(e) => setLanguage(e.target.value || null)}
            className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[var(--text)]"
          >
            <option value="">all languages</option>
            {languages.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
          {language && (
            <button
              onClick={() => setLanguage(null)}
              className="text-[var(--muted)] underline underline-offset-4 hover:text-[var(--text)]"
            >
              clear
            </button>
          )}
        </div>

        <IndiaMap topology={topology} values={values} metricLabel="error rate" />
      </div>

      <aside className="space-y-6 text-sm">
        <div>
          <h3 className="mb-2 font-semibold">Reading the map</h3>
          <ul className="space-y-1">
            {LEGEND.map((s) => (
              <li key={s.label} className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-6 rounded-sm"
                  style={{ background: s.fill }}
                />
                <span className="text-[var(--muted)]">{s.label}</span>
              </li>
            ))}
            <li className="flex items-center gap-2">
              <span
                className="inline-block h-3 w-6 rounded-sm"
                style={{ background: NO_DATA_FILL }}
              />
              <span className="text-[var(--muted)]">not measured</span>
            </li>
          </ul>
          <p className="mt-3 text-xs text-[var(--muted)]">
            The first band stops at {pct(HUMAN_FLOOR.high)} because independent human
            transcribers of this same audio disagree with each other by{" "}
            {pct(HUMAN_FLOOR.low)} to {pct(HUMAN_FLOOR.high)}. Below that line no
            model is measurably better than another.
          </p>
        </div>

        <div>
          <h3 className="mb-2 font-semibold">This view</h3>
          <dl className="space-y-1 text-[var(--muted)]">
            <div className="flex justify-between">
              <dt>districts measured</dt>
              <dd className="tabular text-[var(--text)]">{measured}</dd>
            </div>
            <div className="flex justify-between">
              <dt>districts in the corpus</dt>
              <dd className="tabular text-[var(--text)]">165</dd>
            </div>
            <div className="flex justify-between">
              <dt>clips scored</dt>
              <dd className="tabular text-[var(--text)]">{run.scored ?? run.clips}</dd>
            </div>
            <div className="flex justify-between">
              <dt>excluded</dt>
              <dd className="tabular text-[var(--text)]">{run.excluded ?? 0}</dd>
            </div>
          </dl>
        </div>

        {unmapped.length > 0 && (
          <div>
            <h3 className="mb-2 font-semibold">Measured but not drawn</h3>
            <p className="mb-2 text-xs text-[var(--muted)]">
              These districts have Vaani audio but no polygon in the 2021 boundary
              release. They are named here rather than left as a silent gap.
            </p>
            <ul className="space-y-1 text-xs text-[var(--muted)]">
              {unmapped.map((u) => (
                <li key={`${u.state}-${u.district}`}>
                  <span className="text-[var(--text)]">{u.district}</span>, {u.state}
                  <br />
                  <span className="opacity-70">{u.reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>
    </div>
  );
}
