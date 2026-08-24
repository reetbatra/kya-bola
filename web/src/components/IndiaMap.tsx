"use client";

import { useMemo, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import type { FeatureCollection, Geometry } from "geojson";
import { fillFor, NO_DATA_FILL, pct } from "@/lib/scale";

type Props = {
  topology: Topology;
  /** Vaani district name -> error rate for the selected provider and language. */
  values: Record<string, number | null>;
  metricLabel: string;
};

type Props_ = { name: string; vaani?: string; state?: string };

const WIDTH = 620;
const HEIGHT = 700;

export function IndiaMap({ topology, values, metricLabel }: Props) {
  const [hover, setHover] = useState<{ x: number; y: number; label: string } | null>(null);

  const { features, path } = useMemo(() => {
    const key = Object.keys(topology.objects)[0];
    const fc = feature(topology, topology.objects[key]) as FeatureCollection<Geometry, Props_>;
    // fitSize keeps the whole country in frame regardless of the source
    // projection, and Mercator is what readers expect for a national map.
    const projection = geoMercator().fitSize([WIDTH, HEIGHT], fc);
    return { features: fc.features, path: geoPath(projection) };
  }, [topology]);

  return (
    <div className="relative w-full">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Map of India shaded by ${metricLabel} per district`}
      >
        <g>
          {features.map((f, i) => {
            const vaani = f.properties.vaani;
            const value = vaani ? values[vaani] : undefined;
            const measured = value !== undefined && value !== null;
            return (
              <path
                key={f.properties?.name ? `${f.properties.name}-${i}` : i}
                d={path(f) ?? undefined}
                fill={measured ? fillFor(value) : NO_DATA_FILL}
                stroke="var(--map-stroke)"
                strokeWidth={0.3}
                className={measured ? "cursor-pointer transition-opacity hover:opacity-75" : ""}
                onMouseMove={(e) => {
                  const box = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
                  setHover({
                    x: e.clientX - box.left,
                    y: e.clientY - box.top,
                    label: measured
                      ? `${vaani}: ${pct(value)} ${metricLabel}`
                      : `${f.properties.name}: not measured`,
                  });
                }}
                onMouseLeave={() => setHover(null)}
              />
            );
          })}
        </g>
      </svg>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs shadow-lg"
          style={{ left: hover.x + 12, top: hover.y + 12 }}
        >
          {hover.label}
        </div>
      )}
    </div>
  );
}
