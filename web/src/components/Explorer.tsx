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
  corpusDistricts: number;
};

function valuesFor(run: ProviderRun, language: string | null) {
  const out: Record<string, number | null> = {};
  const rows = language
    ? run.by_language_district.filter((a) => a.key[0] === language)
    : run.by_district;
  for (const a of rows) out[language ? a.key[1] : a.key[0]] = a.primary;
  return out;
}

export function Explorer({ topology, runs, unmapped, corpusDistricts }: Props) {
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
    return <p className="text-[var(--muted)]">No results yet. Run the harness, then rebuild.</p>;
  }

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div>
        <div className="mb-5 flex flex-wrap items-end gap-x-6 gap-y-4">
          <div>
            <span
              id="model-label"
              className="mb-1.5 block text-xs uppercase tracking-wide text-[var(--muted)]"
            >
              model
            </span>
            <div role="group" aria-labelledby="model-label" className="flex flex-wrap gap-2">
              {runs.map((r) => (
                <button
                  key={r.provider}
                  onClick={() => setProvider(r.provider)}
                  aria-pressed={r.provider === providerName}
                  className={`min-h-11 cursor-pointer rounded-full border px-4 text-sm transition-colors duration-200 ${
                    r.provider === providerName
                      ? "border-[var(--accent)] bg-[var(--accent)] text-[var(--on-accent)]"
                      : "border-[var(--border)] hover:border-[var(--accent)]"
                  }`}
                >
                  {r.provider}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label
              htmlFor="language"
              className="mb-1.5 block text-xs uppercase tracking-wide text-[var(--muted)]"
            >
              language
            </label>
            <select
              id="language"
              value={language ?? ""}
              onChange={(e) => setLanguage(e.target.value || null)}
              className="min-h-11 cursor-pointer rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--text)]"
            >
              <option value="">all languages</option>
              {languages.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </div>
        </div>

        <IndiaMap topology={topology} values={values} metricLabel="error rate" />
      </div>

      <aside className="space-y-8 text-sm lg:sticky lg:top-8 lg:self-start">
        <div>
          <h3 className="serif mb-3 text-base">Reading the map</h3>
          <ul className="space-y-1.5">
            {LEGEND.map((s) => (
              <li key={s.label} className="flex items-center gap-2.5">
                <span
                  aria-hidden
                  className="inline-block h-3.5 w-7 shrink-0 rounded-sm"
                  style={{ background: s.fill }}
                />
                <span className="text-[var(--muted)]">{s.label}</span>
              </li>
            ))}
            <li className="flex items-center gap-2.5">
              <span
                aria-hidden
                className="inline-block h-3.5 w-7 shrink-0 rounded-sm"
                style={{ background: NO_DATA_FILL }}
              />
              <span className="text-[var(--muted)]">no audio in this corpus</span>
            </li>
          </ul>
          <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">
            The first band stops at {pct(HUMAN_FLOOR.high)} because two independent
            human transcribers of this same audio disagree with each other by{" "}
            {pct(HUMAN_FLOOR.low)} to {pct(HUMAN_FLOOR.high)}. Below that line no
            model is measurably better than another. Darker bands carry a hatch as
            well as a colour.
          </p>
        </div>

        <div>
          <h3 className="serif mb-3 text-base">This view</h3>
          <dl className="space-y-1.5 text-[var(--muted)]">
            <div className="flex justify-between gap-4">
              <dt>districts measured</dt>
              <dd className="tabular text-[var(--text)]">{measured}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>districts in the corpus</dt>
              <dd className="tabular text-[var(--text)]">{corpusDistricts}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>clips scored</dt>
              <dd className="tabular text-[var(--text)]">{run.scored ?? run.clips}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>excluded</dt>
              <dd className="tabular text-[var(--text)]">{run.excluded ?? 0}</dd>
            </div>
          </dl>
        </div>

        {unmapped.length > 0 && (
          <div>
            <h3 className="serif mb-2 text-base">Measured but not drawn</h3>
            <p className="mb-2.5 text-xs leading-relaxed text-[var(--muted)]">
              These districts have Vaani audio but no polygon in the 2021 boundary
              release. Named here rather than left as a silent gap.
            </p>
            <ul className="space-y-2 text-xs text-[var(--muted)]">
              {unmapped.map((u) => (
                <li key={`${u.state}-${u.district}`}>
                  <span className="text-[var(--text)]">{u.district}</span>, {u.state}
                  <br />
                  <span className="opacity-75">{u.reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>
    </div>
  );
}
