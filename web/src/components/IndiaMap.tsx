"use client";

import { useMemo, useRef, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import type { FeatureCollection, Geometry } from "geojson";
import { bandFor, fillFor, NO_DATA_FILL, pct } from "@/lib/scale";
import { nf, placeLabel } from "@/lib/format";

type DistrictProps = { name: string; vaani?: string; state?: string };

export type DistrictDatum = {
  value: number | null;
  clips: number;
  lowConfidence: boolean;
};

type Props = {
  topology: Topology;
  values: Record<string, DistrictDatum>;
  metricLabel: string;
  selected: string | null;
  onSelect: (district: string | null) => void;
};

const WIDTH = 620;
const HEIGHT = 700;
const TOOLTIP_W = 208;

export function IndiaMap({ topology, values, metricLabel, selected, onSelect }: Props) {
  const [hover, setHover] = useState<{
    x: number;
    y: number;
    flip: boolean;
    title: string;
    state: string;
    detail: string;
    fill: string | null;
  } | null>(null);
  const wrap = useRef<HTMLDivElement>(null);

  const { features, path } = useMemo(() => {
    const key = Object.keys(topology.objects)[0];
    const fc = feature(topology, topology.objects[key]) as FeatureCollection<
      Geometry,
      DistrictProps
    >;
    const projection = geoMercator().fitSize([WIDTH, HEIGHT], fc);
    return { features: fc.features, path: geoPath(projection) };
  }, [topology]);

  // Measured districts paint last so their edges are never clipped by a grey
  // neighbour drawn over them.
  const ordered = useMemo(() => {
    const withData: typeof features = [];
    const without: typeof features = [];
    for (const f of features) {
      (f.properties.vaani && values[f.properties.vaani] ? withData : without).push(f);
    }
    return [...without, ...withData];
  }, [features, values]);

  return (
    <figure className="relative m-0 w-full" ref={wrap}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full overflow-visible"
        role="img"
        aria-label={`Map of India shaded by ${metricLabel} per district. The table below carries the same numbers.`}
      >
        <defs>
          {/* Hatching gives every band a second, non-colour cue. */}
          {[1, 2, 3].map((level) => (
            <pattern
              key={level}
              id={`hatch-${level}`}
              width={6 / level}
              height={6 / level}
              patternTransform="rotate(45)"
              patternUnits="userSpaceOnUse"
            >
              <line
                x1="0"
                y1="0"
                x2="0"
                y2={6 / level}
                stroke="rgba(0,0,0,0.32)"
                strokeWidth={level === 3 ? 1.6 : 1}
              />
            </pattern>
          ))}
        </defs>

        <g>
          {ordered.map((f, i) => {
            const vaani = f.properties.vaani;
            const datum = vaani ? values[vaani] : undefined;
            const value = datum?.value ?? null;
            const measured = datum !== undefined && value !== null;
            const band = bandFor(measured ? value : undefined);
            const isSelected = measured && vaani === selected;

            const title = placeLabel(measured ? (vaani as string) : f.properties.name);
            const state = placeLabel(f.properties.state);
            const detail = measured
              ? `${pct(value)} ${metricLabel} · ${nf.format(datum!.clips)} clip${
                  datum!.clips === 1 ? "" : "s"
                }${datum!.lowConfidence ? " · few clips" : ""}`
              : "no audio in this corpus";

            const show = (clientX: number, clientY: number) => {
              const box = wrap.current?.getBoundingClientRect();
              if (!box) return;
              const x = clientX - box.left;
              setHover({
                x,
                y: clientY - box.top,
                flip: x + TOOLTIP_W + 24 > box.width,
                title,
                state,
                detail,
                fill: measured ? fillFor(value) : null,
              });
            };

            return (
              <g key={`${f.properties?.name ?? "d"}-${i}`}>
                <path
                  d={path(f) ?? undefined}
                  fill={measured ? fillFor(value) : NO_DATA_FILL}
                  stroke={isSelected ? "var(--text)" : "var(--map-stroke)"}
                  strokeWidth={isSelected ? 1.6 : 0.3}
                  tabIndex={measured ? 0 : undefined}
                  role={measured ? "button" : undefined}
                  aria-label={measured ? `${title}. ${detail}` : undefined}
                  aria-pressed={measured ? isSelected : undefined}
                  className={
                    measured
                      ? "cursor-pointer transition-opacity duration-150 hover:opacity-70"
                      : ""
                  }
                  onMouseMove={(e) => measured && show(e.clientX, e.clientY)}
                  onMouseLeave={() => setHover(null)}
                  onFocus={(e) => {
                    if (!measured) return;
                    const r = e.currentTarget.getBoundingClientRect();
                    show(r.left + r.width / 2, r.top + r.height / 2);
                  }}
                  onBlur={() => setHover(null)}
                  onClick={() => measured && onSelect(isSelected ? null : (vaani as string))}
                  onKeyDown={(e) => {
                    if (!measured) return;
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(isSelected ? null : (vaani as string));
                    }
                  }}
                >
                  <title>{`${title}: ${detail}`}</title>
                </path>
                {measured && band && band.hatch > 0 && (
                  <path
                    d={path(f) ?? undefined}
                    fill={`url(#hatch-${band.hatch})`}
                    stroke="none"
                    pointerEvents="none"
                  />
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {hover && (
        <div
          role="status"
          style={{
            width: TOOLTIP_W,
            left: hover.flip ? hover.x - TOOLTIP_W - 14 : hover.x + 14,
            top: hover.y + 14,
          }}
          className="pointer-events-none absolute z-20 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 shadow-[var(--shadow-lg)]"
        >
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: hover.fill ?? NO_DATA_FILL }}
            />
            <span className="truncate text-sm font-medium text-[var(--text)]">{hover.title}</span>
          </div>
          {hover.state && (
            <div className="mt-0.5 pl-[1.125rem] text-xs text-[var(--muted)]">{hover.state}</div>
          )}
          <div className="tabular mt-1 pl-[1.125rem] text-xs text-[var(--text-2)]">
            {hover.detail}
          </div>
        </div>
      )}
    </figure>
  );
}
