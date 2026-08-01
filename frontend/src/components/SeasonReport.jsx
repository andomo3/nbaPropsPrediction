import React, { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
    CartesianGrid, Line, LineChart, ReferenceLine,
    ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import {
    Band, Eyebrow, FootNotes, GhostSelect, GUTTER, Insight,
    PageHead, StateBlock, Tabs,
} from './terminal/ui';
import useFetch from './terminal/useFetch';
import { PLAYERS, STATS, API_BASE } from '../utils/constants';
import { BREAK_EVEN, C, fmt, hitColor, pct, roiColor, signed } from '../utils/format';

const SEASONS = [
    { value: '2026', label: '2025–26' },
    { value: '2025', label: '2024–25' },
    { value: '2024', label: '2023–24' },
    { value: '2023', label: '2022–23' },
];

const STAT_TABS = STATS.map((s) => ({ value: s.key, label: s.label }));
const PLAYER_OPTIONS = PLAYERS.map((p) => ({ value: p, label: p }));

/** The edge floor the board applies — the report card grades the same rule. */
const EDGE_FLOOR = 1.0;

const VERDICT_COLOR = {
    'Strong signal':      C.acid,
    'Moderate signal':    C.cautionText,
    'Weak signal':        C.cautionText,
    'No reliable signal': C.alert,
    'Insufficient data':  C.ink8,
};

const VERDICT_DOT = {
    'Strong signal':      C.acid,
    'Moderate signal':    C.caution,
    'Weak signal':        C.caution,
    'No reliable signal': C.alert,
    'Insufficient data':  C.ink8,
};

/** Largest peak-to-trough fall in a cumulative P&L series, in units. */
function maxDrawdown(series) {
    let peak = 0;
    let worst = 0;
    let from = null;
    let to = null;
    let peakAt = null;
    for (const pt of series) {
        if (pt.value > peak) {
            peak = pt.value;
            peakAt = pt.date;
        }
        const dd = peak - pt.value;
        if (dd > worst) {
            worst = dd;
            from = peakAt;
            to = pt.date;
        }
    }
    return { value: worst, from, to };
}

function ChartTooltip({ active, payload, label }) {
    if (!active || !payload?.length) return null;
    return (
        <div className="bg-popover border border-hair-control rounded-lg px-3 py-2">
            <p className="num text-[11px] tracking-eyebrow uppercase text-ink-8 mb-1.5">{label}</p>
            {payload.map((p) => (
                <p key={p.dataKey} className="text-xs text-ink-5">
                    {p.name}:{' '}
                    <span className="num font-medium" style={{ color: p.color }}>
                        {p.value >= 0 ? '+' : '−'}{Math.abs(p.value).toFixed(2)}u
                    </span>
                </p>
            ))}
        </div>
    );
}

/** One column of the evidence row. */
function Evidence({ label, rows, takeaway, cols }) {
    return (
        <div className="px-5 xl:px-8 py-6 flex flex-col gap-3.5">
            <Eyebrow wide>{label}</Eyebrow>
            <div className="flex flex-col">
                {rows.length === 0 && <p className="text-sm text-ink-7 py-2">Not available.</p>}
                {rows.map((r, i) => (
                    <div
                        key={r.label}
                        style={{ gridTemplateColumns: cols }}
                        className={`grid gap-3 items-baseline py-2.5 ${
                            i === rows.length - 1 ? '' : 'border-b border-hair-row'
                        }`}
                    >
                        <span className="text-sm text-ink-3 truncate">{r.label}</span>
                        {r.meta != null && (
                            <span className="num text-xs text-ink-8 text-right">{r.meta}</span>
                        )}
                        <span
                            className="num text-[15px] font-medium text-right"
                            style={{ color: r.color }}
                        >
                            {r.value}
                        </span>
                        {r.extra != null && (
                            <span
                                className="num text-[15px] font-medium text-right"
                                style={{ color: r.extraColor }}
                            >
                                {r.extra}
                            </span>
                        )}
                    </div>
                ))}
            </div>
            {takeaway && <p className="text-[13px] leading-[1.55] text-ink-6">{takeaway}</p>}
        </div>
    );
}

export default function SeasonReport() {
    const [params, setParams] = useSearchParams();
    const player = params.get('player_name') || PLAYERS[0];
    const stat = params.get('stat') || 'pts';
    const season = params.get('season') || '2026';

    const set = (key, value) => {
        const next = new URLSearchParams(params);
        next.set('player_name', player);
        next.set('stat', stat);
        next.set('season', season);
        next.set(key, value);
        setParams(next, { replace: true });
    };

    const qs = `?player_name=${encodeURIComponent(player)}&stat=${stat}&season=${season}`;
    const summaryReq   = useFetch(`${API_BASE}/api/backtest/season-summary/${qs}`);
    const comparison   = useFetch(`${API_BASE}/api/backtest/model-comparison/${qs}`);
    const validation   = useFetch(`${API_BASE}/api/intelligence/validation/${qs}`);
    const calibration  = useFetch(`${API_BASE}/api/intelligence/edge/${qs}`);

    const data = summaryReq.data;
    const summary = data?.summary;
    const perGame = data?.per_game ?? [];
    const statLabel = STATS.find((s) => s.key === stat)?.label ?? stat;

    /* Two cumulative curves off the same graded games: every bet, and only the
       bets that clear the edge floor the board actually applies. */
    const { chart, filteredTotal, allTotal, filteredN, drawdown } = useMemo(() => {
        let cumAll = 0;
        let cumFiltered = 0;
        let n = 0;
        const series = perGame.map((g) => {
            cumAll += g.pnl;
            const clears = Math.abs(g.projection - g.line) >= EDGE_FLOOR;
            if (clears) {
                cumFiltered += g.pnl;
                n += 1;
            }
            return {
                date: g.date.slice(5),
                all: Number(cumAll.toFixed(2)),
                filtered: Number(cumFiltered.toFixed(2)),
            };
        });
        return {
            chart: series,
            allTotal: cumAll,
            filteredTotal: cumFiltered,
            filteredN: n,
            drawdown: maxDrawdown(series.map((p) => ({ date: p.date, value: p.filtered }))),
        };
    }, [perGame]);

    const verdict = validation.data?.verdict;
    const bands = calibration.data?.edge_bands ?? [];
    const conditions = useMemo(() => {
        const rest = calibration.data?.rest_analysis ?? [];
        const form = calibration.data?.form_analysis ?? [];
        return [...rest, ...form]
            .filter((r) => r.hit_rate != null)
            .sort((a, b) => a.hit_rate - b.hit_rate)
            .slice(0, 4);
    }, [calibration.data]);

    const models = (comparison.data?.models ?? []).filter((m) => m.available && m.summary);
    const bestModelRoi = models.length ? Math.max(...models.map((m) => m.summary.roi)) : null;

    const bandsMonotonic = bands.length > 2
        && bands.every((b, i) => i === 0 || b.hit_rate >= bands[i - 1].hit_rate);
    const failing = conditions.filter((c) => c.hit_rate < BREAK_EVEN).length;

    return (
        <>
            <PageHead
                eyebrow={
                    summary
                        ? `${data.season} · ${statLabel.toUpperCase()} · ${summary.total_games} GRADED GAMES`
                        : `${SEASONS.find((s) => s.value === season)?.label ?? season} · ${statLabel.toUpperCase()}`
                }
                title="Season report card"
                controls={
                    <>
                        <GhostSelect
                            value={player}
                            onChange={(v) => set('player_name', v)}
                            options={PLAYER_OPTIONS}
                            label="Player"
                        />
                        <Tabs
                            options={STAT_TABS}
                            value={stat}
                            onChange={(v) => set('stat', v)}
                            ariaLabel="Stat"
                        />
                        <GhostSelect
                            value={season}
                            onChange={(v) => set('season', v)}
                            options={SEASONS}
                            label="Season"
                        />
                    </>
                }
            />

            <StateBlock
                loading={summaryReq.loading}
                error={summaryReq.error}
                empty={!summary ? 'No graded games for this player, stat and season.' : null}
                emptyHint="python manage.py seed_season_backtest --season 2026"
            >
                {summary && (
                    <>
                        {/* Verdict + headline figures */}
                        <Band className="py-6">
                            <div className="flex flex-col gap-6 xl:flex-row xl:items-center xl:gap-0">
                                <div className="xl:flex-[1.5] xl:pr-9 flex flex-col gap-2 min-w-0">
                                    <Eyebrow wide>Season verdict</Eyebrow>
                                    {verdict ? (
                                        <div className="flex items-center gap-3">
                                            <span
                                                className="w-2.5 h-2.5 rounded-full shrink-0"
                                                style={{ background: VERDICT_DOT[verdict] ?? C.ink8 }}
                                            />
                                            <span
                                                className="text-[24px] sm:text-[26px] font-semibold tracking-tightest leading-none"
                                                style={{ color: VERDICT_COLOR[verdict] ?? C.ink8 }}
                                            >
                                                {verdict}
                                            </span>
                                        </div>
                                    ) : (
                                        <span className="text-[24px] font-semibold text-ink-8 leading-none">
                                            {validation.loading ? 'Grading…' : 'Not graded'}
                                        </span>
                                    )}
                                    <Insight text={validation.data?.insight} className="max-w-md" />
                                </div>

                                <div className="hidden xl:block w-px h-16 bg-[var(--hair-rule)]" aria-hidden="true" />

                                <div className="xl:flex-[4] xl:pl-8 grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-6">
                                    <div className="flex flex-col gap-1.5">
                                        <Eyebrow>Hit rate</Eyebrow>
                                        <div className="num text-[26px] sm:text-[30px] font-medium leading-none" style={{ color: hitColor(summary.hit_rate) }}>
                                            {pct(summary.hit_rate)}
                                        </div>
                                        <div className="text-xs text-ink-7">
                                            {Math.round(summary.hit_rate * summary.total_games)} of {summary.total_games} · break-even 52.4%
                                        </div>
                                    </div>
                                    <div className="flex flex-col gap-1.5">
                                        <Eyebrow>ROI</Eyebrow>
                                        <div className="num text-[26px] sm:text-[30px] font-medium leading-none" style={{ color: roiColor(summary.roi) }}>
                                            {signed(summary.roi)}%
                                        </div>
                                        <div className="text-xs text-ink-7">
                                            {signed(summary.total_pnl, 2)}u flat at −110
                                        </div>
                                    </div>
                                    <div className="flex flex-col gap-1.5">
                                        <Eyebrow>MAE</Eyebrow>
                                        <div className="num text-[26px] sm:text-[30px] font-medium text-ink-0 leading-none">
                                            {fmt(summary.mae, 2)}
                                        </div>
                                        <div className="text-xs text-ink-7">
                                            bias {signed(summary.bias, 2)}
                                        </div>
                                    </div>
                                    <div className="flex flex-col gap-1.5">
                                        <Eyebrow>Max drawdown</Eyebrow>
                                        <div className="num text-[26px] sm:text-[30px] font-medium leading-none" style={{ color: drawdown.value > 0 ? C.cautionText : C.ink0 }}>
                                            −{fmt(drawdown.value, 2)}u
                                        </div>
                                        <div className="text-xs text-ink-7">
                                            {drawdown.from ? `${drawdown.from} – ${drawdown.to}` : 'no drawdown'}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </Band>

                        {/* Cumulative P&L */}
                        {chart.length > 0 && (
                            <Band className="pt-7 pb-7">
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between mb-5">
                                    <div className="flex flex-col gap-1">
                                        <h2 className="text-[18px] font-semibold tracking-[-0.01em] text-ink-1">
                                            Cumulative profit &amp; loss
                                        </h2>
                                        <p className="text-sm text-ink-5">
                                            Flat one-unit stakes at −110, {statLabel.toLowerCase()}, with and without the
                                            edge ≥ {fmt(EDGE_FLOOR)} filter the board applies.
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-4 text-xs text-ink-7">
                                        <span className="flex items-center gap-2">
                                            <span className="w-3.5 h-0.5 bg-acid" />
                                            Filtered ({filteredN})
                                        </span>
                                        <span className="flex items-center gap-2">
                                            <span className="w-3.5 h-0.5 bg-white/25" />
                                            Every bet ({perGame.length})
                                        </span>
                                    </div>
                                </div>

                                <div className="relative">
                                    <ResponsiveContainer width="100%" height={260}>
                                        <LineChart data={chart} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
                                            <CartesianGrid
                                                vertical={false}
                                                stroke="rgba(255,255,255,0.05)"
                                            />
                                            <XAxis
                                                dataKey="date"
                                                tick={{ fontSize: 11, fill: 'var(--ink-8)', fontFamily: 'IBM Plex Mono' }}
                                                tickLine={false}
                                                axisLine={{ stroke: 'var(--hair-rule)' }}
                                                interval="preserveStartEnd"
                                                minTickGap={40}
                                            />
                                            <YAxis hide domain={['auto', 'auto']} />
                                            <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.14)' }} />
                                            <ReferenceLine y={0} stroke="rgba(255,255,255,0.14)" strokeDasharray="4 5" />
                                            <Line
                                                type="monotone"
                                                dataKey="all"
                                                name="Every bet"
                                                stroke="rgba(255,255,255,0.25)"
                                                strokeWidth={2}
                                                dot={false}
                                            />
                                            <Line
                                                type="monotone"
                                                dataKey="filtered"
                                                name="Filtered"
                                                stroke={C.acid}
                                                strokeWidth={2.5}
                                                dot={false}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>

                                    <div className="absolute left-0 top-0 flex flex-col gap-0.5 pointer-events-none">
                                        <span className="num text-[24px] font-medium" style={{ color: roiColor(filteredTotal) }}>
                                            {signed(filteredTotal, 1)}u
                                        </span>
                                        <span className="text-[13px] text-ink-7">
                                            every bet: {signed(allTotal, 1)}u
                                        </span>
                                    </div>
                                </div>
                            </Band>
                        )}

                        {/* Evidence row */}
                        <Band padded={false} className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_1px_minmax(0,1fr)_1px_minmax(0,1fr)] divide-y xl:divide-y-0">
                            <Evidence
                                label="Calibration by edge bucket"
                                cols="1fr auto 66px"
                                rows={bands.map((b) => ({
                                    label: b.bucket,
                                    meta: `n=${b.n}`,
                                    value: pct(b.hit_rate),
                                    color: hitColor(b.hit_rate),
                                }))}
                                takeaway={
                                    bands.length === 0
                                        ? null
                                        : bandsMonotonic
                                            ? 'Monotonic across buckets — the projected edge is real, it just needs a floor.'
                                            : 'Not monotonic across buckets — a bigger projected edge does not reliably convert here.'
                                }
                            />
                            <div className="hidden xl:block bg-hair" aria-hidden="true" />
                            <Evidence
                                label="By model"
                                cols="1fr 70px 70px"
                                rows={models.map((m) => ({
                                    label: m.label,
                                    value: pct(m.summary.hit_rate),
                                    color: hitColor(m.summary.hit_rate),
                                    extra: `${signed(m.summary.roi)}%`,
                                    extraColor: m.summary.roi === bestModelRoi ? C.acid : roiColor(m.summary.roi),
                                }))}
                                takeaway={
                                    models.length === 0
                                        ? null
                                        : `Hit rate and ROI for the same graded games. ${
                                            models.find((m) => m.summary.roi === bestModelRoi)?.label
                                          } leads on return.`
                                }
                            />
                            <div className="hidden xl:block bg-hair" aria-hidden="true" />
                            <Evidence
                                label="Where it struggles"
                                cols="1fr auto 66px"
                                rows={conditions.map((c) => ({
                                    label: c.label,
                                    meta: `n=${c.n}`,
                                    value: pct(c.hit_rate),
                                    color: hitColor(c.hit_rate),
                                }))}
                                takeaway={
                                    conditions.length === 0
                                        ? null
                                        : failing === 0
                                            ? 'No split falls below break-even — the weakest conditions still clear 52.4%.'
                                            : `${failing} of these ${conditions.length} conditions sit below the 52.4% break-even line.`
                                }
                            />
                        </Band>

                        {/* Game by game — depth on demand, collapsed by default */}
                        {perGame.length > 0 && (
                            <Band padded={false}>
                                <details className="group">
                                    <summary className={`${GUTTER} py-4 flex items-center gap-3 cursor-pointer select-none list-none`}>
                                        <Eyebrow wide>Game by game</Eyebrow>
                                        <span className="text-[13px] text-ink-7 group-open:hidden">
                                            {perGame.length} graded games →
                                        </span>
                                        <span className="text-[13px] text-ink-7 hidden group-open:inline">
                                            hide
                                        </span>
                                    </summary>
                                    <div className="table-scroll max-h-[420px] overflow-y-auto border-t border-hair">
                                        <div className="min-w-[720px]">
                                            <div className={`grid grid-cols-[92px_64px_repeat(5,minmax(0,1fr))_72px] gap-4 ${GUTTER} py-2.5 border-b border-hair num text-[11px] font-medium tracking-eyebrow uppercase text-ink-8 sticky top-0 bg-background`}>
                                                <span>Date</span>
                                                <span>Opp</span>
                                                <span className="text-right">Actual</span>
                                                <span className="text-right">Proj</span>
                                                <span className="text-right">Line</span>
                                                <span className="text-right">Error</span>
                                                <span className="text-right">Edge</span>
                                                <span className="text-right">P&amp;L</span>
                                            </div>
                                            {perGame.map((g, i) => {
                                                const edge = g.projection - g.line;
                                                return (
                                                    <div
                                                        key={`${g.date}-${i}`}
                                                        className={`grid grid-cols-[92px_64px_repeat(5,minmax(0,1fr))_72px] gap-4 ${GUTTER} py-2.5 border-b border-hair-soft items-baseline`}
                                                    >
                                                        <span className="num text-[13px] text-ink-8">{g.date}</span>
                                                        <span className="text-[13px] text-ink-3">{g.opponent}</span>
                                                        <span className="num text-[13px] text-ink-1 text-right">{fmt(g.actual)}</span>
                                                        <span className="num text-[13px] text-ink-3 text-right">{fmt(g.projection)}</span>
                                                        <span className="num text-[13px] text-ink-5 text-right">{fmt(g.line)}</span>
                                                        <span className="num text-[13px] text-right" style={{ color: Math.abs(g.error) <= 3 ? C.ink3 : C.cautionText }}>
                                                            {signed(g.error)}
                                                        </span>
                                                        <span className="num text-[13px] text-right" style={{ color: Math.abs(edge) >= EDGE_FLOOR ? C.ink2 : C.ink8 }}>
                                                            {signed(edge)}
                                                        </span>
                                                        <span className="num text-[13px] text-right font-medium" style={{ color: g.pnl >= 0 ? C.acid : C.alert }}>
                                                            {signed(g.pnl, 2)}u
                                                        </span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </details>
                            </Band>
                        )}

                        <FootNotes
                            items={[
                                'Flat one-unit stakes at −110 · no vig shopping modelled',
                                'Binomial test vs the 52.4% break-even rate',
                                `Filtered curve takes only bets with a projected edge of ${fmt(EDGE_FLOOR)}+ pts`,
                            ]}
                        />
                    </>
                )}
            </StateBlock>
        </>
    );
}
