import React, { useMemo, useState } from 'react';
import {
    ComposedChart, Area, Line, XAxis, YAxis,
    CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts';
import {
    Band, Eyebrow, FootNotes, GhostSelect, GUTTER,
    PageHead, Prose, StateBlock, Tabs,
} from './terminal/ui';
import useFetch from './terminal/useFetch';
import { PLAYERS, STATS, API_BASE } from '../utils/constants';
import { C, fmt } from '../utils/format';

const STAT_UNITS = { pts: 'pts', reb: 'reb', ast: 'ast' };
const PATHS = 1000;

const STAT_TABS = STATS.map((s) => ({ value: s.key, label: s.label }));
const PLAYER_OPTIONS = PLAYERS.map((p) => ({ value: p, label: p }));

const axis = { fontSize: 11, fill: 'var(--ink-8)', fontFamily: 'IBM Plex Mono' };

/** How a φ close to zero should be read, in words. */
function phiReading(phi) {
    if (phi > 0.15) return 'hot and cold streaks persist';
    if (phi > 0.1) return 'mild momentum';
    if (phi < -0.1) return 'strong mean reversion';
    return 'near-random game-to-game variation';
}

function FanTooltip({ active, payload, label, stat }) {
    if (!active || !payload?.length) return null;
    const d = payload[0]?.payload ?? {};

    return (
        <div className="bg-popover border border-hair-control rounded-lg px-3 py-2 min-w-[150px]">
            <p className="num text-[11px] tracking-eyebrow uppercase text-ink-8 mb-1.5">
                Game {label}
            </p>
            {d.isActual ? (
                <p className="text-sm text-ink-5">
                    Actual{' '}
                    <span className="num font-medium" style={{ color: C.acid }}>
                        {d.actual} {STAT_UNITS[stat]}
                    </span>
                </p>
            ) : (
                <div className="flex flex-col gap-0.5">
                    {[['p90', d.p90], ['p75', d.p75], ['p50', d.p50], ['p25', d.p25], ['p10', d.p10]].map(
                        ([k, v]) => (
                            <p key={k} className="text-xs text-ink-5 flex justify-between gap-4">
                                <span className="num">{k}</span>
                                <span
                                    className="num"
                                    style={{ color: k === 'p50' ? C.ink0 : C.ink3, fontWeight: k === 'p50' ? 500 : 400 }}
                                >
                                    {fmt(v)}
                                </span>
                            </p>
                        ),
                    )}
                </div>
            )}
            {d.opponent && <p className="text-xs text-ink-8 mt-1.5">vs {d.opponent}</p>}
        </div>
    );
}

/**
 * Simulated probability of clearing each line. The accent marks the single
 * strongest lean in the table; anything inside a few points of a coin flip is
 * greyed out, because that is what it is.
 */
function PropTable({ propTable, seasonAvg, stat }) {
    if (!propTable?.length) return null;

    const lean = (p) => Math.abs(p * 100 - 50);
    const strongest = Math.max(...propTable.map((r) => lean(r.prob_over)));

    return (
        <Band className="py-12">
            <Eyebrow section>Prop probability</Eyebrow>
            <Prose size="wide" className="mt-4 text-ink-6">
                Simulated probability of going over each line across the next 20 games, from{' '}
                {PATHS.toLocaleString()} Monte Carlo paths.
            </Prose>

            <div className="mt-7 grid grid-cols-1 sm:grid-cols-2 gap-x-16">
                {propTable.map(({ line, prob_over }) => {
                    const pct = Math.round(prob_over * 100);
                    const l = lean(prob_over);
                    const color = l >= strongest ? C.acid : l >= 7 ? C.ink2 : C.ink5;
                    const isAvg = Math.abs(line - seasonAvg) < 1.5;
                    return (
                        <div
                            key={line}
                            className="grid grid-cols-[minmax(0,1fr)_72px_84px] gap-5 items-baseline py-4 border-b border-hair-row"
                        >
                            <span className="text-base text-ink-3">
                                {line} {STAT_UNITS[stat]}
                                {isAvg && <span className="num text-xs text-ink-8 ml-2">avg</span>}
                            </span>
                            <span className="num text-[13px] text-ink-8 text-right">
                                {pct >= 50 ? 'OVER' : 'UNDER'}
                            </span>
                            <span className="num text-lg font-medium text-right" style={{ color }}>
                                {pct}%
                            </span>
                        </div>
                    );
                })}
            </div>
        </Band>
    );
}

export default function Simulator() {
    const [player, setPlayer] = useState(PLAYERS[0]);
    const [stat, setStat] = useState('pts');

    const { data, loading, error } = useFetch(
        `${API_BASE}/api/simulator/?player_name=${encodeURIComponent(player)}&stat=${stat}`,
    );

    /*
     * Actual games and projected quantiles share one series. The bands are
     * genuine ranges — [p10, p90] and [p25, p75] — not areas dropped to the
     * axis baseline, which would shade everything below p10 as if it were
     * inside the interval.
     */
    const chartData = useMemo(() => {
        if (!data) return [];
        const actual = data.actual.map((g) => ({
            gameNum: g.game_num,
            actual: g.value,
            opponent: g.opponent,
            isActual: true,
        }));
        const projected = data.projections.map((g) => ({
            gameNum: g.game_num,
            p10: g.p10, p25: g.p25, p50: g.p50, p75: g.p75, p90: g.p90,
            band_10_90: [g.p10, g.p90],
            band_25_75: [g.p25, g.p75],
            isActual: false,
        }));
        return [...actual, ...projected];
    }, [data]);

    const tickInterval = chartData.length > 40 ? 9 : chartData.length > 20 ? 4 : 2;
    const splitX = data ? Math.round(data.games_played + 0.5) : null;
    const unit = STAT_UNITS[stat];

    return (
        <>
            <PageHead
                eyebrow={
                    data
                        ? `AR(1) MONTE CARLO · ${PATHS.toLocaleString()} PATHS · NEXT 20 GAMES`
                        : 'AR(1) MONTE CARLO'
                }
                title="Season simulator"
                controls={
                    <>
                        <GhostSelect
                            value={player}
                            onChange={setPlayer}
                            options={PLAYER_OPTIONS}
                            label="Player"
                        />
                        <Tabs options={STAT_TABS} value={stat} onChange={setStat} ariaLabel="Stat" />
                    </>
                }
            />

            <StateBlock
                loading={loading}
                error={error}
                empty={!loading && !error && !data ? 'No simulation available for this player and stat.' : null}
            >
                {data && (
                    <>
                        <Band className="py-12">
                            <div className="grid grid-cols-2 gap-x-8 gap-y-10 lg:grid-cols-4 lg:gap-x-12">
                                {[
                                    {
                                        label: 'Season avg',
                                        value: `${fmt(data.season_avg)}`,
                                        sub: `${unit} · 2025–26 actual`,
                                    },
                                    {
                                        label: 'Games played',
                                        value: data.games_played,
                                        sub: 'in the modelled set',
                                    },
                                    {
                                        label: 'AR(1) φ',
                                        symbol: true,
                                        value: fmt(data.ar1_phi, 3),
                                        sub: phiReading(data.ar1_phi),
                                    },
                                    {
                                        label: 'AR(1) σ',
                                        symbol: true,
                                        value: fmt(data.ar1_sigma, 2),
                                        sub: 'innovation std dev',
                                    },
                                ].map((k) => (
                                    <div key={k.label} className="flex flex-col gap-2.5">
                                        <Eyebrow wide preserveCase={k.symbol}>{k.label}</Eyebrow>
                                        <span className="num text-[30px] sm:text-[38px] font-medium leading-none text-ink-0">
                                            {k.value}
                                        </span>
                                        <span className="text-[13px] text-ink-7">{k.sub}</span>
                                    </div>
                                ))}
                            </div>
                        </Band>

                        <Band className="py-12">
                            <h2 className="text-[22px] sm:text-[24px] font-semibold tracking-[-0.02em] text-ink-1 leading-none">
                                Trajectory and 20-game fan
                            </h2>
                            <Prose size="wide" className="mt-4 text-ink-6">
                                Every game played this season, then the simulated range for the next
                                twenty. The accent is what actually happened; the grey is what the
                                model thinks could happen next.
                            </Prose>

                            <div className="mt-8 flex flex-wrap items-center gap-7 text-[13px] text-ink-7">
                                <span className="flex items-center gap-2.5">
                                    <span className="w-4 h-0.5 bg-acid" />
                                    Actual
                                </span>
                                <span className="flex items-center gap-2.5">
                                    <span className="w-4 h-0.5 bg-[var(--ink-3)]" />
                                    Median projection
                                </span>
                                <span className="flex items-center gap-2.5">
                                    <span className="w-4 h-2.5 bg-white/[0.14]" />
                                    p25–p75
                                </span>
                                <span className="flex items-center gap-2.5">
                                    <span className="w-4 h-2.5 bg-white/[0.09]" />
                                    p10–p90
                                </span>
                            </div>

                            <div className="mt-7">
                                <ResponsiveContainer width="100%" height={320}>
                                    <ComposedChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
                                        <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.05)" />
                                        <XAxis
                                            dataKey="gameNum"
                                            tick={axis}
                                            tickLine={false}
                                            axisLine={{ stroke: 'var(--hair-rule)' }}
                                            interval={tickInterval}
                                        />
                                        <YAxis
                                            tick={axis}
                                            tickLine={false}
                                            axisLine={false}
                                            width={36}
                                            domain={['auto', 'auto']}
                                        />
                                        <Tooltip content={<FanTooltip stat={stat} />} cursor={{ stroke: 'rgba(255,255,255,0.14)' }} />

                                        <ReferenceLine
                                            y={data.season_avg}
                                            stroke="rgba(255,255,255,0.13)"
                                            strokeDasharray="4 6"
                                        />
                                        {splitX && (
                                            <ReferenceLine
                                                x={splitX}
                                                stroke="rgba(255,255,255,0.22)"
                                                strokeDasharray="4 4"
                                                label={{
                                                    value: 'PROJECTION',
                                                    position: 'insideTopRight',
                                                    fontSize: 10,
                                                    fontFamily: 'IBM Plex Mono',
                                                    fill: 'var(--ink-8)',
                                                }}
                                            />
                                        )}

                                        <Area
                                            type="monotone"
                                            dataKey="band_10_90"
                                            stroke="none"
                                            fill="rgba(255,255,255,0.09)"
                                            activeDot={false}
                                            isAnimationActive={false}
                                        />
                                        <Area
                                            type="monotone"
                                            dataKey="band_25_75"
                                            stroke="none"
                                            fill="rgba(255,255,255,0.14)"
                                            activeDot={false}
                                            isAnimationActive={false}
                                        />

                                        <Line
                                            type="monotone"
                                            dataKey="p50"
                                            stroke="var(--ink-3)"
                                            strokeWidth={2}
                                            dot={false}
                                            activeDot={{ r: 3.5 }}
                                            isAnimationActive={false}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="actual"
                                            stroke={C.acid}
                                            strokeWidth={1.5}
                                            dot={{ r: 2, fill: C.acid, strokeWidth: 0 }}
                                            activeDot={{ r: 4 }}
                                            isAnimationActive={false}
                                            connectNulls={false}
                                        />
                                    </ComposedChart>
                                </ResponsiveContainer>
                            </div>

                            <Prose size="narrow" className="mt-6 text-ink-7">
                                φ = {fmt(data.ar1_phi, 3)} — {phiReading(data.ar1_phi)}.
                            </Prose>
                        </Band>

                        <PropTable
                            propTable={data.prop_table}
                            seasonAvg={data.season_avg}
                            stat={stat}
                        />

                        <FootNotes
                            items={[
                                `Bands are the p10–p90 and p25–p75 intervals across ${PATHS.toLocaleString()} simulated paths`,
                                'AR(1) fits one autoregressive term to this season only — it carries no opponent, rest or injury context',
                                'A simulated probability is not a price. It does not account for the vig.',
                            ]}
                        />
                    </>
                )}
            </StateBlock>
        </>
    );
}
