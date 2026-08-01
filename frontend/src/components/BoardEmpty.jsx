import React from 'react';
import { Link } from 'react-router-dom';
import { Eyebrow, GUTTER } from './terminal/ui';

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
export default function BoardEmpty({ season, statLabel }) {
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
            ? `The ${lastCompleted} season is complete and no later season has been modelled yet. Every night of the season this page lists the modelled props, the projected edge against the posted line, and the call — but there are no games to model right now.`
            : 'Every night of the season this page lists the modelled props, the projected edge against the posted line, and the call. There are no games to model right now.';
    } else {
        eyebrow = 'No slate tonight';
        headline = `No ${statLabel.toLowerCase()} props have been modelled for tonight.`;
        body = 'The board is generated each morning from the night\'s schedule. If games are on, check back shortly.';
    }

    return (
        <>
            <section className={`${GUTTER} py-16 sm:py-24 border-b border-hair`}>
                <div className="flex flex-col gap-5 max-w-2xl">
                    <Eyebrow wide>{eyebrow}</Eyebrow>
                    <h2 className="text-[26px] sm:text-[34px] font-semibold tracking-tightest text-ink-0 leading-[1.15] text-pretty">
                        {headline}
                    </h2>
                    <p className="text-[15px] sm:text-base leading-[1.6] text-ink-5 text-pretty">
                        {body}
                    </p>

                    {offSeason && lastCompleted && (
                        <div className="flex items-center gap-3 pt-1">
                            <span className="w-2 h-2 rounded-full bg-[var(--ink-8)] shrink-0" />
                            <span className="num text-[13px] text-ink-7">
                                Last modelled season · {lastCompleted}
                            </span>
                        </div>
                    )}

                    {/* Only worth showing in-season — off-season there is
                        nothing for the command to generate. */}
                    {!offSeason && (
                        <p className="num text-[13px] text-ink-9 pt-1">
                            Running this yourself? python manage.py generate_daily_picks
                        </p>
                    )}
                </div>
            </section>

            <section className="border-b border-hair">
                <div className={`${GUTTER} pt-6 pb-4`}>
                    <Eyebrow wide>In the meantime</Eyebrow>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3">
                    {ELSEWHERE.map((item, i) => (
                        <Link
                            key={item.to}
                            to={item.to}
                            className={`px-5 sm:px-gutter py-6 flex flex-col gap-2 border-t border-hair md:border-t-0 ${
                                i < ELSEWHERE.length - 1 ? 'md:border-r' : ''
                            } border-hair group hover:bg-white/[0.02] transition-colors`}
                        >
                            <div className="flex items-baseline justify-between gap-3">
                                <span className="text-[15px] font-semibold text-ink-1">{item.title}</span>
                                <span className="num text-[13px] text-ink-7 group-hover:text-acid transition-colors">
                                    →
                                </span>
                            </div>
                            <p className="text-[13px] leading-[1.55] text-ink-6">{item.blurb}</p>
                        </Link>
                    ))}
                </div>
            </section>
        </>
    );
}
