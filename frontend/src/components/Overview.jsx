import React from 'react';
import { Link } from 'react-router-dom';
import { Eyebrow, FootNotes, GUTTER, PageHead, Prose } from './terminal/ui';

/**
 * How it works.
 *
 * Every claim on this page is checked against the code it describes:
 * `FEATURE_COLUMNS` in ml/train_regression.py, the conventions in
 * docs/ML_FEATURE_GUIDE.md, and the serving constants in constants.py.
 * If the pipeline changes, this page changes with it.
 */

const STEPS = [
    {
        n: '01',
        title: 'Ingest',
        body: 'Games and box scores are synced from ESPN into PostgreSQL. The schema keeps teams, players, games and per-period player stats separate from the posted prop lines, so a projection can always be traced back to the rows it was built from.',
        tags: ['Team', 'Player', 'Game', 'PlayerStats', 'PlayerPropLine'],
    },
    {
        n: '02',
        title: 'Engineer features',
        body: 'Each stat gets its own feature set: 15 for points, 12 for rebounds, 13 for assists. Rolling L5 and L10 means, an EMA over the last five, a 10-game standard deviation, minutes and shooting form, season average, a hot/cold term, opponent output allowed over their last ten, days of rest and home/away.',
        tags: ['pts_L5', 'pts_ema_L5', 'pts_std_L10', 'min_L10', 'fg_pct_L5', 'opp_pts_allowed_L10', 'days_rest', 'is_home'],
    },
    {
        n: '03',
        title: 'Guard against leakage',
        body: 'Every rolling figure is shifted by one game before it is computed, so only games strictly earlier than the one being predicted can contribute. Sub-10-minute appearances are masked out before any rolling window runs, and rest days are capped at ten on both the training and the serving path so the model never meets a value it did not train on.',
        tags: ['shift(1)', 'garbage-time masked', 'rest clipped at 10'],
    },
    {
        n: '04',
        title: 'Project',
        body: 'A gradient-boosted regression per stat predicts the raw value of the next game, not a category. Models are validated walk-forward — trained on earlier seasons, tested on the next one — so the reported error is always out-of-sample in time.',
        tags: ['XGBoost', 'walk-forward folds', 'ridge / RF / rolling-average baselines'],
    },
    {
        n: '05',
        title: 'Turn it into a call',
        body: 'The projection is compared with the posted line. The gap is the edge; the projection and its uncertainty become a probability for the called side, clamped so the model never claims near-certainty. Only props whose edge clears the floor are called — the rest are marked PASS.',
        tags: ['edge = projection − line', 'probability clamped to 1–99%'],
    },
    {
        n: '06',
        title: 'Grade it honestly',
        body: 'Every call is settled against the real result at flat one-unit stakes and −110 pricing, which needs a 52.4% hit rate to break even. A binomial test says whether a hit rate above that is distinguishable from luck, and the report card shows the filtered and unfiltered curves side by side so the filter has to earn its keep.',
        tags: ['break-even 52.4%', 'binomial test', 'filtered vs unfiltered'],
    },
];

const LIMITS = [
    'Closing-line prices only. No shopping across books, and no vig modelled beyond a flat −110.',
    'The published picks feed is filtered by confidence, so any performance it shows is conditional on that filter, not the model\'s unconditional accuracy.',
    'Conditional splits — rest, form, matchup — are exploratory. They are not corrected for multiple comparisons, and small samples are marked as such.',
    'Player availability is taken as given. Late scratches and in-game injuries are outside the model.',
];

function Step({ n, title, body, tags, last }) {
    return (
        <div
            className={`${GUTTER} py-7 grid grid-cols-1 gap-x-8 gap-y-4 lg:grid-cols-[56px_minmax(0,1fr)_minmax(0,320px)] ${
                last ? '' : 'border-b border-hair'
            }`}
        >
            <span className="num text-[13px] font-medium text-ink-8 tracking-eyebrow lg:pt-1">{n}</span>

            <div className="flex flex-col gap-3 min-w-0">
                <h2 className="text-[19px] font-semibold tracking-[-0.015em] text-ink-1">{title}</h2>
                <Prose className="text-ink-5">{body}</Prose>
            </div>

            <div className="flex flex-wrap gap-1.5 content-start lg:justify-end">
                {tags.map((t) => (
                    <span
                        key={t}
                        className="num text-[11px] text-ink-6 border border-hair-control rounded px-2 py-1"
                    >
                        {t}
                    </span>
                ))}
            </div>
        </div>
    );
}

export default function Overview() {
    return (
        <>
            <PageHead eyebrow="Under the hood" title="How it works" />

            <section className={`${GUTTER} py-10 border-b border-hair`}>
                <Prose size="lead" className="text-ink-4">
                    Perchance projects a player&apos;s next-game points, rebounds and assists, compares
                    each projection with the posted line, and reports how often that call has actually
                    been right. Six steps, and the last one is the one that matters.
                </Prose>
            </section>

            <div>
                {STEPS.map((s, i) => (
                    <Step key={s.n} {...s} last={i === STEPS.length - 1} />
                ))}
            </div>

            <section className="border-t border-hair">
                <div className={`${GUTTER} pt-7 pb-4`}>
                    <Eyebrow wide>What this does not do</Eyebrow>
                </div>
                <ul className={`${GUTTER} pb-7 flex flex-col gap-3 max-w-3xl`}>
                    {LIMITS.map((l) => (
                        <li key={l} className="max-w-measure text-[15px] sm:text-base leading-[1.65] text-ink-5 pl-4 relative text-pretty">
                            <span className="absolute left-0 text-ink-9">·</span>
                            {l}
                        </li>
                    ))}
                </ul>
            </section>

            <section className="border-t border-hair">
                <div className={`${GUTTER} pt-7 pb-4`}>
                    <Eyebrow wide>See it applied</Eyebrow>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3">
                    {[
                        { to: '/season-report', title: 'Season report card', blurb: 'The grading step, run over a full season.' },
                        { to: '/intelligence', title: 'Player intelligence', blurb: 'Whether the edge converts, player by player.' },
                        { to: '/simulator', title: 'Season simulator', blurb: 'Where the uncertainty around a projection comes from.' },
                    ].map((item, i, arr) => (
                        <Link
                            key={item.to}
                            to={item.to}
                            className={`px-5 sm:px-gutter py-6 flex flex-col gap-2 border-t border-hair md:border-t-0 ${
                                i < arr.length - 1 ? 'md:border-r' : ''
                            } border-hair group hover:bg-white/[0.02] transition-colors`}
                        >
                            <div className="flex items-baseline justify-between gap-3">
                                <span className="text-[15px] font-semibold text-ink-1">{item.title}</span>
                                <span className="num text-[13px] text-ink-7 group-hover:text-acid transition-colors">→</span>
                            </div>
                            <p className="text-[13px] leading-[1.55] text-ink-6">{item.blurb}</p>
                        </Link>
                    ))}
                </div>
            </section>

            <div className="border-t border-hair">
                <FootNotes
                    items={[
                        'Feature definitions: docs/ML_FEATURE_GUIDE.md',
                        'Assumptions and known limits: docs/METHODOLOGY.md',
                        'Modelled output for research. Not betting advice.',
                    ]}
                />
            </div>
        </>
    );
}
