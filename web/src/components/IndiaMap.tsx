"use client";

import { useMemo, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import type { FeatureCollection, Geometry } from "geojson";
import { bandFor, fillFor, NO_DATA_FILL, pct } from "@/lib/scale";

type DistrictProps = { name: string; vaani?: string; state?: string };

type Props = {
  topology: Topology;
  values: Record<string, number | null>;
  metricLabel: string;
};

const WIDTH = 620;
const HEIGHT = 700;

export function IndiaMap({ topology, values, metricLabel }: Props) {
  const [hover, setHover] = useState<{ x: number; y: number; label: string } | null>(null);

  const { features, path } = useMemo(() => {
    const key = Object.keys(topology.objects)[0];
    const fc = feature(topology, topology.objects[key]) as FeatureCollection<
      Geometry,
      DistrictProps
    >;
    const projection = geoMercator().fitSize([WIDTH, HEIGHT], fc);
    return { features: fc.features, path: geoPath(projection) };
  }, [topology]);

  return (
    <figure className="relative m-0 w-full">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full"
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
          {features.map((f, i) => {
            const vaani = f.properties.vaani;
            const value = vaani ? values[vaani] : undefined;
            const measured = value !== undefined && value !== null;
            const band = bandFor(value ?? undefined);
            const label = measured
              ? `${vaani}: ${pct(value)} ${metricLabel}`
              : `${f.properties.name}: no audio in this corpus`;

            return (
              <g key={`${f.properties?.name ?? "d"}-${i}`}>
                <path
                  d={path(f) ?? undefined}
                  fill={measured ? fillFor(value) : NO_DATA_FILL}
                  stroke="var(--map-stroke)"
                  strokeWidth={0.3}
                  className={
                    measured
                      ? "cursor-pointer transition-opacity duration-200 hover:opacity-70"
                      : ""
                  }
                  onMouseMove={(e) => {
                    const box = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
                    setHover({ x: e.clientX - box.left, y: e.clientY - box.top, label });
                  }}
                  onMouseLeave={() => setHover(null)}
                >
                  <title>{label}</title>
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
          className="pointer-events-none absolute z-20 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-xs shadow-lg"
          style={{ left: hover.x + 14, top: hover.y + 14 }}
        >
          {hover.label}
        </div>
      )}
    </figure>
  );
}
