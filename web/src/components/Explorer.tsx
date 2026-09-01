"use client";

import { useMemo, useState } from "react";
import type { Topology } from "topojson-specification";
import { IndiaMap, type DistrictDatum } from "./IndiaMap";
import { bandFor, fillFor, LEGEND, NO_DATA_FILL, pct } from "@/lib/scale";
import { HUMAN_FLOOR, type ProviderRun } from "@/lib/types";
import { nf, placeLabel, providerLabel } from "@/lib/format";

type Props = {
  topology: Topology;
  runs: ProviderRun[];
  unmapped: Array<{ state: string; district: string; reason: string }>;
  corpusDistricts: number;
};

function valuesFor(run: ProviderRun, language: string | null): Record<string, DistrictDatum> {
  const out: Record<string, DistrictDatum> = {};
  const rows = language
    ? run.by_language_district.filter((a) => a.key[0] === language)
    : run.by_district;
  for (const a of rows) {
    out[language ? a.key[1] : a.key[0]] = {
      value: a.primary,
      clips: a.scored ?? a.clips,
      lowConfidence: a.low_confidence,
    };
  }
  return out;
}

function Panel({
  title,
  children,
  note,
}: {
  title: string;
  children: React.ReactNode;
  note?: string;
}) {
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-sm)]">
      <h3 className="eyebrow mb-3">{title}</h3>
      {children}
      {note && <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">{note}</p>}
    </section>
  );
}

/** The colour ramp drawn as one continuous strip, with the hatch overlays that
 *  carry the same information for anyone who cannot separate the hues.
 *  The patterns are declared here rather than borrowed from the map's SVG, so
 *  the legend renders correctly on its own. */
function Legend() {
  return (
    <div>
      <div className="flex overflow-hidden rounded-md border border-[var(--border-2)]">
        {LEGEND.map((s) => (
          <div key={s.label} className="relative h-6 flex-1" style={{ background: s.fill }}>
            {s.hatch > 0 && (
              <svg aria-hidden className="absolute inset-0 h-full w-full">
                <defs>
                  <pattern
                    id={`legend-hatch-${s.hatch}`}
                    width={6 / s.hatch}
                    height={6 / s.hatch}
                    patternTransform="rotate(45)"
                    patternUnits="userSpaceOnUse"
                  >
                    <line
                      x1="0"
                      y1="0"
                      x2="0"
                      y2={6 / s.hatch}
                      stroke="rgba(0,0,0,0.32)"
                      strokeWidth={s.hatch === 3 ? 1.6 : 1}
                    />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill={`url(#legend-hatch-${s.hatch})`} />
              </svg>
            )}
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex text-[0.6875rem] text-[var(--muted)]">
        {LEGEND.map((s) => (
          <span key={s.label} className="tabular flex-1 text-center">
            {s.short}
          </span>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2.5">
        <span
          aria-hidden
          className="inline-block h-4 w-7 shrink-0 rounded-sm border border-[var(--border-2)]"
          style={{ background: NO_DATA_FILL }}
        />
        <span className="text-xs text-[var(--muted)]">no audio in this corpus</span>
      </div>
    </div>
  );
}

function Rank({
  heading,
  rows,
  onPick,
  selected,
}: {
  heading: string;
  rows: Array<[string, DistrictDatum]>;
  onPick: (d: string) => void;
  selected: string | null;
}) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-medium text-[var(--text-2)]">{heading}</div>
      <ul className="space-y-0.5">
        {rows.map(([district, d]) => (
          <li key={district}>
            <button
              onClick={() => onPick(district)}
              aria-pressed={selected === district}
              className={`flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors duration-200 ${
                selected === district ? "bg-[var(--accent-tint)]" : "hover:bg-[var(--surface-2)]"
              }`}
            >
              <span
                aria-hidden
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ background: fillFor(d.value) }}
              />
              <span className="min-w-0 flex-1 truncate text-xs text-[var(--text-2)]">
                {placeLabel(district)}
              </span>
              <span className="tabular shrink-0 text-xs text-[var(--text)]">{pct(d.value)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Explorer({ topology, runs, unmapped, corpusDistricts }: Props) {
  const [providerName, setProvider] = useState(runs[0]?.provider ?? "");
  const [language, setLanguage] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const run = runs.find((r) => r.provider === providerName) ?? runs[0];

  const languages = useMemo(() => {
    const names = new Set<string>();
    for (const r of runs) for (const a of r.by_language) names.add(a.key[0]);
    return [...names].sort();
  }, [runs]);

  const values = useMemo(() => (run ? valuesFor(run, language) : {}), [run, language]);

  // Every provider's numbers for the current view, so a selected district can
  // be compared across models without changing the map.
  const allValues = useMemo(
    () => Object.fromEntries(runs.map((r) => [r.provider, valuesFor(r, language)])),
    [runs, language],
  );

  const ranked = useMemo(
    () =>
      Object.entries(values)
        .filter((e): e is [string, DistrictDatum] => e[1].value !== null)
        .sort((a, b) => a[1].value! - b[1].value!),
    [values],
  );

  const measured = ranked.length;
  const median = measured ? ranked[Math.floor((measured - 1) / 2)][1].value : null;

  if (!run) {
    return <p className="text-[var(--muted)]">No results yet. Run the harness, then rebuild.</p>;
  }

  const selectedDatum = selected ? values[selected] : undefined;

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-10">
      <div className="min-w-0">
        <div className="mb-6 flex flex-wrap items-end gap-x-8 gap-y-5">
          <div>
            <span id="model-label" className="eyebrow mb-2 block">
              model
            </span>
            <div
              role="group"
              aria-labelledby="model-label"
              className="inline-flex flex-wrap gap-1 rounded-full border border-[var(--border)] bg-[var(--surface-2)] p-1"
            >
              {runs.map((r) => (
                <button
                  key={r.provider}
                  onClick={() => setProvider(r.provider)}
                  aria-pressed={r.provider === providerName}
                  title={r.provider}
                  className={`min-h-9 cursor-pointer rounded-full px-3.5 text-sm transition-colors duration-200 ${
                    r.provider === providerName
                      ? "bg-[var(--surface)] font-medium text-[var(--text)] shadow-[var(--shadow-sm)]"
                      : "text-[var(--muted)] hover:text-[var(--text)]"
                  }`}
                >
                  {providerLabel(r.provider)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="language" className="eyebrow mb-2 block">
              language
            </label>
            <div className="flex items-center gap-2">
              <select
                id="language"
                value={language ?? ""}
                onChange={(e) => {
                  setLanguage(e.target.value || null);
                  setSelected(null);
                }}
                className="select min-h-11 cursor-pointer rounded-lg border border-[var(--border-2)] bg-[var(--surface)] px-3 text-sm text-[var(--text)] transition-colors duration-200 hover:border-[var(--accent)]"
              >
                <option value="">all {languages.length} languages</option>
                {languages.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
              {language && (
                <button
                  onClick={() => {
                    setLanguage(null);
                    setSelected(null);
                  }}
                  className="min-h-11 cursor-pointer px-1 text-sm text-[var(--muted)] underline decoration-[var(--border-2)] underline-offset-4 transition-colors duration-200 hover:text-[var(--text)]"
                >
                  clear
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Every measured district is its own tab stop, which is what makes the
            map usable without a mouse and also puts ~150 stops in front of the
            table. Keyboard users get an escape hatch. */}
        <a href="#after-map" className="skip-link">
          Skip the map
        </a>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 shadow-[var(--shadow-sm)] sm:p-5">
          <IndiaMap
            topology={topology}
            values={values}
            metricLabel="error rate"
            selected={selected}
            onSelect={setSelected}
          />
          <p className="mt-1 text-center text-xs text-[var(--muted)]">
            {measured > 0
              ? `${measured} districts shaded${
                  median !== null ? ` · median ${pct(median)}` : ""
                } · select one to compare models`
              : "no districts measured in this view"}
          </p>
        </div>
        <span id="after-map" tabIndex={-1} />
      </div>

      <aside className="space-y-5 lg:sticky lg:top-[calc(var(--nav-h)+1.5rem)] lg:self-start">
        {selected && selectedDatum && (
          <section className="rounded-xl border border-[var(--accent)]/40 bg-[var(--surface)] p-4 shadow-[var(--shadow-md)]">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="serif truncate text-lg">{placeLabel(selected)}</h3>
                <p className="text-xs text-[var(--muted)]">
                  {language ?? "all languages"} ·{" "}
                  {nf.format(selectedDatum.clips)} clip
                  {selectedDatum.clips === 1 ? "" : "s"}
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                aria-label="Clear selected district"
                className="-mr-1 -mt-1 inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full text-[var(--muted)] transition-colors duration-200 hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
              >
                <svg viewBox="0 0 16 16" aria-hidden className="h-4 w-4">
                  <path
                    d="M4 4l8 8M12 4l-8 8"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>
            <dl className="space-y-2">
              {runs.map((r) => {
                const v = allValues[r.provider]?.[selected]?.value ?? null;
                return (
                  <div key={r.provider} className="flex items-center gap-3">
                    <dt className="w-32 shrink-0 truncate text-xs text-[var(--muted)]">
                      {providerLabel(r.provider)}
                    </dt>
                    <dd className="flex flex-1 items-center gap-2">
                      <span
                        aria-hidden
                        className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface-3)]"
                      >
                        <span
                          className="block h-full rounded-full"
                          style={{
                            width: `${v === null ? 0 : Math.min(100, Math.max(2, v * 100))}%`,
                            background: fillFor(v),
                          }}
                        />
                      </span>
                      <span className="tabular w-14 shrink-0 text-right text-xs text-[var(--text)]">
                        {pct(v)}
                      </span>
                    </dd>
                  </div>
                );
              })}
            </dl>
            {selectedDatum.lowConfidence && (
              <p className="mt-3 rounded-md bg-[var(--surface-2)] px-2.5 py-1.5 text-xs leading-relaxed text-[var(--muted)]">
                Flagged low confidence: too few clips here to separate this
                district from its neighbours.
              </p>
            )}
            {bandFor(selectedDatum.value)?.hatch === 0 &&
              selectedDatum.value !== null &&
              selectedDatum.value <= HUMAN_FLOOR.high && (
                <p className="mt-3 rounded-md bg-[var(--accent-tint)] px-2.5 py-1.5 text-xs leading-relaxed text-[var(--accent-hover)]">
                  At or below the human disagreement floor.
                </p>
              )}
          </section>
        )}

        <Panel
          title="Reading the map"
          note={`The first band stops at ${pct(
            HUMAN_FLOOR.high,
          )} because two independent human transcribers of this same audio disagree with each other by ${pct(
            HUMAN_FLOOR.low,
          )} to ${pct(
            HUMAN_FLOOR.high,
          )}. Below that line no model is measurably better than another. Darker bands carry a hatch as well as a colour.`}
        >
          <Legend />
        </Panel>

        {ranked.length >= 4 && (
          <Panel title="Extremes in this view">
            <div className="space-y-4">
              <Rank
                heading="Lowest error"
                rows={ranked.slice(0, 5)}
                onPick={setSelected}
                selected={selected}
              />
              <Rank
                heading="Highest error"
                rows={ranked.slice(-5).reverse()}
                onPick={setSelected}
                selected={selected}
              />
            </div>
          </Panel>
        )}

        <Panel title="This view">
          <dl className="space-y-2 text-sm">
            {[
              ["districts measured", nf.format(measured)],
              ["districts in the corpus", nf.format(corpusDistricts)],
              ["clips scored", nf.format(run.scored ?? run.clips)],
              ["excluded", nf.format(run.excluded ?? 0)],
            ].map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between gap-4">
                <dt className="text-[var(--muted)]">{k}</dt>
                <dd className="tabular font-medium text-[var(--text)]">{v}</dd>
              </div>
            ))}
          </dl>
        </Panel>

        {unmapped.length > 0 && (
          <Panel
            title="Measured but not drawn"
            note="These districts have Vaani audio but no polygon in the 2021 boundary release. Named here rather than left as a silent gap."
          >
            <ul className="space-y-2 text-xs text-[var(--muted)]">
              {unmapped.map((u) => (
                <li key={`${u.state}-${u.district}`}>
                  <span className="text-[var(--text-2)]">{placeLabel(u.district)}</span>,{" "}
                  {placeLabel(u.state)}
                  <br />
                  <span className="opacity-80">{u.reason}</span>
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </aside>
    </div>
  );
}
