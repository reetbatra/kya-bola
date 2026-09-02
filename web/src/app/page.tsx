import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { Explorer } from "@/components/Explorer";
import { CoverageTable } from "@/components/CoverageTable";
import { SupportList } from "@/components/SupportList";
import { loadResults, loadTopology, loadUnmapped, loadCalibration } from "@/lib/data";
import { pct } from "@/lib/scale";
import { nf, providerLabel } from "@/lib/format";

const CORPUS_DISTRICTS = 165;

function languageMeta() {
  const path = join(process.cwd(), "public", "languages.json");
  if (!existsSync(path)) return { supported: {} as Record<string, boolean> };
  return JSON.parse(readFileSync(path, "utf8")) as { supported: Record<string, boolean> };
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="border-l-2 border-[var(--border-2)] pl-4">
      <div className="serif tabular text-3xl leading-none text-[var(--text)] sm:text-4xl">
        {value}
      </div>
      <div className="mt-2 text-sm leading-snug text-[var(--muted)]">{label}</div>
    </div>
  );
}

function SectionHead({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-8">
      <p className="eyebrow mb-2.5">{eyebrow}</p>
      <h2 id={`${id}-heading`} className="text-3xl sm:text-4xl">
        {title}
      </h2>
      <p className="prose-note mt-3 text-[var(--text-2)]">{children}</p>
    </div>
  );
}

export default function Home() {
  const results = loadResults();
  const topology = loadTopology();
  const unmapped = loadUnmapped();
  const calibration = loadCalibration() as
    | { district_mean?: number; district_std?: number; inter_annotator_wer?: number; clips?: number; districts?: number; provider?: string }
    | null;
  const { supported } = languageMeta();

  const total = Object.keys(supported).length;
  const unsupported = Object.values(supported).filter((v) => !v).length;
  const measuredDistricts = new Set(
    results.runs.flatMap((r) => r.by_district.map((a) => a.key[0])),
  ).size;
  const totalClips = results.runs.reduce((n, r) => n + (r.scored ?? r.clips ?? 0), 0);

  return (
    <main id="main" className="mx-auto max-w-6xl px-6 pb-24 pt-12 sm:pt-20">
      <header id="top" className="mb-20 scroll-mt-24">
        <p className="eyebrow mb-4">
          A benchmark built on Project Vaani · ARTPARK and IISc
        </p>
        <h1 className="max-w-[16ch] text-5xl leading-[1.05] sm:text-7xl">kya bola?</h1>
        <p className="prose-note mt-6 text-lg leading-relaxed text-[var(--text-2)] sm:text-xl">
          Every speech recognition vendor publishes one accuracy number per
          language. Hindi in Delhi and Hindi in Araria are not the same problem,
          and one number hides the difference. This measures it district by
          district.
        </p>
        {total > 0 && (
          <p className="prose-note mt-4 text-lg leading-relaxed text-[var(--muted)]">
            It also asks something nobody has published an answer to. The corpus
            behind this holds {total} languages. Commercial speech APIs
            officially support {total - unsupported}. Here is what happens to the
            other {unsupported}.
          </p>
        )}

        <div className="mt-12 grid grid-cols-2 gap-x-6 gap-y-8 border-t border-[var(--border)] pt-8 sm:grid-cols-4">
          <Stat value={String(total || "—")} label="languages in the corpus" />
          <Stat value={String(unsupported || "—")} label="with no API support" />
          <Stat value={nf.format(measuredDistricts)} label="districts measured" />
          <Stat
            value={calibration?.inter_annotator_wer ? pct(calibration.inter_annotator_wer) : "—"}
            label="human disagreement floor"
          />
        </div>

        {results.runs.length > 0 && (
          <p className="mt-6 text-sm text-[var(--muted)]">
            {nf.format(totalClips)} clips scored across{" "}
            {results.runs.map((r) => providerLabel(r.provider)).join(", ")}.
          </p>
        )}
      </header>

      <section id="map" className="mb-24 scroll-mt-24" aria-labelledby="map-heading">
        <SectionHead id="map" eyebrow="District view" title="The map">
          Error rate per district. Greener is better. Grey is not a gap in the
          measurement: Project Vaani has recorded {CORPUS_DISTRICTS} of
          India&rsquo;s districts so far, and the rest of the country has no
          transcribed audio in this corpus to score against.
        </SectionHead>
        <Explorer
          topology={topology}
          runs={results.runs}
          unmapped={unmapped}
          corpusDistricts={CORPUS_DISTRICTS}
        />
      </section>

      {results.runs.length > 0 && (
        <section id="coverage" className="mb-24 scroll-mt-24" aria-labelledby="coverage-heading">
          <SectionHead id="coverage" eyebrow="Language view" title="The coverage gap">
            Languages an API does not claim to support are still sent to it, with
            language detection on. A refusal or an empty answer counts as a failed
            clip, because that is what a developer building for those speakers
            would experience.
          </SectionHead>
          <SupportList runs={results.runs} supported={supported} />
          <CoverageTable runs={results.runs} supported={supported} />
        </section>
      )}

      {calibration && (
        <section id="method" className="mb-24 scroll-mt-24" aria-labelledby="method-heading">
          <SectionHead id="method" eyebrow="Calibration" title="Is this trustworthy?">
            Before measuring anything new, this harness reproduced a published
            result. The Vaani team benchmarked{" "}
            {calibration.provider ? providerLabel(calibration.provider) : "Sarvam Saaras v3"} on
            their own Hindi evaluation set and reported a district mean word error
            rate of 18.3% with a standard deviation of 4.6. Running their clips
            through this pipeline gives:
          </SectionHead>

          <div className="prose-note overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-sm)]">
            <dl>
              {[
                {
                  term: "district mean, this harness",
                  value: `${pct(calibration.district_mean)}${
                    calibration.district_std != null
                      ? ` ± ${(calibration.district_std * 100).toFixed(1)}`
                      : ""
                  }`,
                  strong: true,
                },
                { term: "district mean, published", value: "18.3% ± 4.6" },
                {
                  term: "two humans, same audio",
                  value: pct(calibration.inter_annotator_wer),
                  note: "the floor",
                },
              ].map((row) => (
                <div
                  key={row.term}
                  className="flex items-baseline justify-between gap-4 border-b border-[var(--border)] px-5 py-3.5 last:border-0"
                >
                  <dt className="text-[var(--muted)]">
                    {row.term}
                    {row.note && (
                      <span className="ml-2 rounded-full bg-[var(--accent-tint)] px-2 py-0.5 text-xs text-[var(--accent-hover)]">
                        {row.note}
                      </span>
                    )}
                  </dt>
                  <dd
                    className={`tabular shrink-0 ${
                      row.strong ? "font-semibold text-[var(--text)]" : "text-[var(--text-2)]"
                    }`}
                  >
                    {row.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <p className="prose-note mt-4 text-sm leading-relaxed text-[var(--muted)]">
            That last row is the floor. Two people transcribing the same audio
            disagree by that much, so no model can score below it and no gap
            narrower than it is a real difference between two systems.
            {calibration.clips && calibration.districts
              ? ` Measured over ${nf.format(calibration.clips)} clips across ${nf.format(
                  calibration.districts,
                )} districts.`
              : ""}
          </p>
        </section>
      )}

      <footer className="border-t border-[var(--border)] pt-10">
        <div className="prose-note space-y-4 text-sm leading-relaxed text-[var(--muted)]">
          <p>
            Built on{" "}
            <a
              className="text-[var(--text-2)] underline decoration-[var(--border-2)] underline-offset-4 transition-colors duration-200 hover:text-[var(--accent-hover)] hover:decoration-[var(--accent)]"
              href="https://huggingface.co/datasets/ARTPARK-IISc/Vaani"
            >
              Project Vaani
            </a>{" "}
            by ARTPARK and IISc, used under CC-BY-4.0. District polygons from{" "}
            <a
              className="text-[var(--text-2)] underline decoration-[var(--border-2)] underline-offset-4 transition-colors duration-200 hover:text-[var(--accent-hover)] hover:decoration-[var(--accent)]"
              href="https://www.geoboundaries.org/"
            >
              geoBoundaries
            </a>{" "}
            under ODbL 1.0. Method, caveats and every test in the{" "}
            <a
              className="text-[var(--text-2)] underline decoration-[var(--border-2)] underline-offset-4 transition-colors duration-200 hover:text-[var(--accent-hover)] hover:decoration-[var(--accent)]"
              href="https://github.com/reetbatra/kya-bola"
            >
              repository
            </a>
            .
          </p>
          <p>
            Audio is spontaneous, image-prompted speech recorded in real conditions,
            not read speech in a studio. Error rates here are legitimately higher
            than the numbers vendors publish on clean benchmarks. That is the point.
          </p>
        </div>
      </footer>
    </main>
  );
}
