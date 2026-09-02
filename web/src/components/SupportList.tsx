import type { ProviderRun } from "@/lib/types";

/**
 * The support list, held against what actually happened.
 *
 * The two languages are chosen from the data, not written in, so this stays
 * true when the harness is rerun. Both sides need a real sample: a cell with
 * twenty clips can say anything, and a claim about a vendor's coverage should
 * not rest on one. Santali is the sharpest contrast in the run at 84.2% and it
 * is deliberately not used here, because seventeen scored clips is not enough
 * to carry it.
 */

const CLIP_FLOOR = 60;

type Row = { language: string; wer: number; clips: number; metric: string };

function rows(run: ProviderRun, supported: Record<string, boolean>, listed: boolean): Row[] {
  return run.by_language
    .filter((e) => Boolean(supported[e.key[0]]) === listed)
    .filter((e) => e.primary != null && e.scored >= CLIP_FLOOR)
    .map((e) => ({
      language: e.key[0],
      wer: (e.primary as number) * 100,
      clips: e.scored,
      metric: e.primary_metric,
    }))
    .sort((a, b) => a.wer - b.wer);
}

function median(ns: number[]) {
  if (!ns.length) return null;
  const s = [...ns].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function SupportList({
  runs,
  supported,
}: {
  runs: ProviderRun[];
  supported: Record<string, boolean>;
}) {
  const run = runs.find((r) => r.provider === "sarvam:saaras:v3") ?? runs[0];
  if (!run) return null;

  const listed = rows(run, supported, true);
  const unlisted = rows(run, supported, false);
  if (!listed.length || !unlisted.length) return null;

  const best = unlisted[0]; // best language nobody claims to support
  const worst = listed[listed.length - 1]; // worst language they do
  if (best.wer >= worst.wer) return null; // no crossover, no point to make

  const medListed = median(listed.map((r) => r.wer));
  const medUnlisted = median(unlisted.map((r) => r.wer));
  const beating = unlisted.filter((r) => r.wer < worst.wer).length;

  return (
    <figure className="my-10">
      <div className="overflow-hidden rounded-lg border border-[var(--border)]">
        {[
          { r: best, listed: false },
          { r: worst, listed: true },
        ].map(({ r, listed: isListed }) => (
          <div
            key={r.language}
            className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-[var(--border)] px-5 py-4 last:border-0 sm:flex-nowrap"
          >
            <span className="serif min-w-[7rem] text-xl text-[var(--text)]">{r.language}</span>
            <span
              className="rounded-full border px-2.5 py-0.5 text-xs whitespace-nowrap"
              style={
                isListed
                  ? {
                      borderColor: "var(--accent)",
                      color: "var(--accent)",
                      background: "var(--accent-tint)",
                    }
                  : { borderColor: "var(--border-2)", color: "var(--muted)" }
              }
            >
              {isListed ? "on the support list" : "not on the support list"}
            </span>
            <span className="text-sm text-[var(--muted)] tabular">
              {r.clips} clips
            </span>
            <span className="serif tabular ml-auto text-2xl text-[var(--text)] sm:text-3xl">
              {r.wer.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>

      <figcaption className="mt-4 max-w-[62ch] text-sm leading-relaxed text-[var(--muted)]">
        Both on Sarvam Saaras v3, both scored the same way.{" "}
        <span className="text-[var(--text)]">{best.language}</span> is on nobody&rsquo;s support
        list and beats <span className="text-[var(--text)]">{worst.language}</span>, which is on
        it, by {(worst.wer - best.wer).toFixed(1)} points.
        {medListed != null && medUnlisted != null && (
          <>
            {" "}
            It is not a one-off. The median listed language sits at {medListed.toFixed(0)}% and the
            median unlisted one at {medUnlisted.toFixed(0)}%, and yet{" "}
            {beating === unlisted.length
              ? `every one of the ${unlisted.length} unlisted languages`
              : `${beating} of the ${unlisted.length} unlisted languages`}{" "}
            with a comparable sample scores better than the worst listed one. The two ranges
            overlap enough that the list barely predicts whether a language works.
          </>
        )}{" "}
        Only languages with at least {CLIP_FLOOR} scored clips are eligible for this comparison, so
        it cannot rest on a thin cell.
      </figcaption>
    </figure>
  );
}
