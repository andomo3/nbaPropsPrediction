import React from 'react';
import { Link } from 'react-router-dom';
import { Eyebrow, GUTTER, Prose } from './terminal/ui';

const ELSEWHERE = [
    {
        to: '/season-report',
        title: 'Season report card',
        blurb: 'How the model actually did over a full season — hit rate, ROI, drawdown, and where it broke down.',
    },
    {
        to: '/leaderboard',
        title: 'Predictability leaderboard',
        blurb: 'Which players the model reads most reliably, scored on R², variance and hit-rate excess.',
    },
    {
        to: '/intelligence',
        title: 'Player intelligence',
        blurb: 'Edge calibration, floor/ceiling, matchup splits and the statistical verdict, player by player.',
    },
];

/** "2025-10-22" → "Wed 22 Oct 2025", parsed at midday so the date never shifts. */
function formatStart(iso) {
    if (!iso) return null;
    const d = new Date(`${iso}T12:00:00`);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleDateString('en-GB', {
        weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
    });
}

/**
 * The board with nothing on it.
 *
 * An empty slate has two very different causes, so it gets two different
 * screens: the season is over (come back when it tips off) or tonight simply
 * has no modelled games. Either way the visitor leaves with somewhere to go —
 * every season already played is still fully browsable.
 */
export default function BoardEmpty({ season, statLabel, boardDate }) {
    // Only claim the season is over when the backend actually says so. A
    // response without season context (older backend) falls back to the
    // neutral "nothing on tonight" copy rather than asserting an off-season.
    const offSeason = season?.status === 'off_season';
    const nextStart = formatStart(season?.next_start);
    const lastCompleted = season?.last_completed;

    let eyebrow;
    let headline;
    let body;

    if (offSeason && nextStart) {
        eyebrow = 'Off-season · no slate';
        headline = `The board goes live on ${nextStart}.`;
        body = 'Every night of the season this page lists the modelled props, the projected edge against the posted line, and the call. Until tip-off there is nothing to model.';
    } else if (offSeason) {
        eyebrow = 'Off-season · no slate';
        headline = 'The board goes live when the next season tips off.';
        body = lastCompleted
            ? `The ${lastCompleted} season is complete and no later season has been modelled yet. Every night of the season this page lists the modelled props, the projected edge against the posted line, and the call.`
            : 'Every night of the season this page lists the modelled props, the projected edge against the posted line, and the call. There are no games to model right now.';
    } else {
        eyebrow = 'No slate tonight';
        headline = `No ${statLabel.toLowerCase()} props have been modelled for tonight.`;
        body = 'The board is generated each morning from the night\'s schedule. If games are on, check back shortly.';
    }

    return (
        <>
            {/* Hero rhythm: eyebrow → 32 → headline → 32 → body → 56 → meta,
                inside 88px of section padding. The headline is capped at 20ch
                so it breaks into a shape rather than a line. */}
            <section className={`${GUTTER} pt-[88px] pb-24 border-b border-hair`}>
                <div className="max-w-[880px]">
                    <Eyebrow section>{boardDate ? `${boardDate} · ${eyebrow}` : eyebrow}</Eyebrow>

                    <h1 className="mt-8 max-w-headline text-[34px] sm:text-[44px] lg:text-[56px] font-semibold tracking-headline text-ink-0 leading-[1.1] text-balance">
                        {headline}
                    </h1>

                    <Prose size="lead" className="mt-8 text-ink-4">
                        {body}
                    </Prose>

                    {offSeason && lastCompleted && (
                        <div className="mt-14 flex items-center gap-3">
                            <span className="w-1.5 h-1.5 rounded-full bg-[var(--ink-8)] shrink-0" />
                            <span className="num text-sm tracking-[0.06em] text-ink-7">
                                Last modelled season · {lastCompleted}
                            </span>
                        </div>
                    )}

                    {/* Only worth showing in-season — off-season there is
                        nothing for the command to generate. */}
                    {!offSeason && (
                        <p className="mt-14 num text-[13px] text-ink-9">
                            Running this yourself? python manage.py generate_daily_picks
                        </p>
                    )}
                </div>
            </section>

            <section className={`${GUTTER} pt-14 pb-14`}>
                <Eyebrow section>In the meantime</Eyebrow>

                <div className="mt-8">
                    {ELSEWHERE.map((item) => (
                        <Link
                            key={item.to}
                            to={item.to}
                            className="grid grid-cols-[minmax(0,1fr)_40px] items-start py-9 border-b border-hair hover:bg-white/[0.025] transition-colors duration-[130ms]"
                        >
                            <div className="flex flex-col gap-3.5">
                                <span className="text-[19px] sm:text-[22px] font-semibold tracking-[-0.015em] text-ink-1 leading-none">
                                    {item.title}
                                </span>
                                <Prose size="link" className="text-ink-6">{item.blurb}</Prose>
                            </div>
                            <span className="text-lg text-ink-8 text-right leading-none pt-1">→</span>
                        </Link>
                    ))}
                </div>
            </section>
        </>
    );
}
