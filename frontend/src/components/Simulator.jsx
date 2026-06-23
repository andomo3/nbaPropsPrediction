import React, { useEffect, useState } from 'react';
import {
    ComposedChart,
    Area,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceLine,
    ResponsiveContainer,
    Legend,
} from 'recharts';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select';

import { PLAYERS, STATS, API_BASE } from '../utils/constants';

const STAT_UNITS = { pts: 'pts', reb: 'reb', ast: 'ast' };

// ── Custom Tooltip ─────────────────────────────────────────────────────────────
function FanTooltip({ active, payload, label, stat }) {
    if (!active || !payload?.length) return null;

    const entry = payload[0]?.payload ?? {};
    const isActual = entry.isActual;

    return (
        <div className="bg-popover border border-border rounded-xl px-4 py-3 text-sm shadow-lg min-w-[160px]">
            <p className="font-semibold text-foreground mb-1">Game {label}</p>
            {isActual ? (
                <p className="text-foreground">
                    Actual: <span className="font-bold">{entry.actual} {STAT_UNITS[stat]}</span>
                </p>
            ) : (
                <>
                    <p className="text-muted-foreground text-xs mb-1">Projected range</p>
                    <div className="flex flex-col gap-0.5">
                        <span className="text-foreground/80">90th: <b>{entry.p90}</b></span>
                        <span className="text-foreground/80">75th: <b>{entry.p75}</b></span>
                        <span className="text-primary font-bold">Median: {entry.p50}</span>
                        <span className="text-foreground/80">25th: <b>{entry.p25}</b></span>
                        <span className="text-foreground/80">10th: <b>{entry.p10}</b></span>
                    </div>
                </>
            )}
            {entry.opponent && (
                <p className="text-xs text-muted-foreground mt-1">vs {entry.opponent}</p>
            )}
        </div>
    );
}

// ── Prop Table ─────────────────────────────────────────────────────────────────
function PropTable({ propTable, seasonAvg, stat }) {
    if (!propTable?.length) return null;

    return (
        <div className="bg-card border border-border rounded-2xl p-6">
            <h3 className="text-base font-semibold text-foreground mb-4">
                Prop Probability Table
            </h3>
            <p className="text-xs text-muted-foreground mb-4">
                Simulated probability of going <strong>over</strong> each line in the next 20 games.
            </p>
            <div className="grid grid-cols-2 gap-2">
                {propTable.map(({ line, prob_over }) => {
                    const pct = Math.round(prob_over * 100);
                    const edge = pct >= 55 ? 'text-green-400' : pct <= 45 ? 'text-red-400' : 'text-muted-foreground';
                    const isAvg = Math.abs(line - seasonAvg) < 1.5;
                    return (
                        <div
                            key={line}
                            className={`flex items-center justify-between px-4 py-2.5 rounded-xl border ${
                                isAvg ? 'border-primary/40 bg-primary/5' : 'border-border bg-background'
                            }`}
                        >
                            <span className="text-sm font-medium text-foreground">
                                {line} {STAT_UNITS[stat]}
                                {isAvg && <span className="ml-1.5 text-xs text-primary">(avg)</span>}
                            </span>
                            <span className={`text-sm font-bold ${edge}`}>{pct}%</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ── Stat pills ────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub }) {
    return (
        <div className="bg-card border border-border rounded-2xl px-5 py-4">
            <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
            <p className="text-2xl font-bold text-foreground">{value}</p>
            {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
        </div>
    );
}

// ── Main component ────────────────────────────────────────────────────────────
const Simulator = () => {
    const [player, setPlayer] = useState(PLAYERS[0]);
    const [stat, setStat]     = useState('pts');

    const [data, setData]       = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState(null);

    useEffect(() => {
        setLoading(true);
        setError(null);
        setData(null);

        const params = new URLSearchParams({ player_name: player, stat });
        fetch(`${API_BASE}/api/simulator/?${params}`)
            .then((res) => {
                const ct = res.headers.get('content-type') || '';
                if (!ct.includes('application/json'))
                    throw new Error(`Server error (HTTP ${res.status})`);
                return res.json().then((json) => ({ ok: res.ok, json }));
            })
            .then(({ ok, json }) => {
                if (!ok) throw new Error(json.detail || 'Request failed');
                setData(json);
            })
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, [player, stat]);

    // ── Build unified chart data ───────────────────────────────────────────────
    const chartData = React.useMemo(() => {
        if (!data) return [];

        const actualPoints = data.actual.map((g) => ({
            gameNum:  g.game_num,
            actual:   g.value,
            opponent: g.opponent,
            isActual: true,
        }));

        const futurePoints = data.projections.map((g) => ({
            gameNum:  g.game_num,
            p10:      g.p10,
            p25:      g.p25,
            p50:      g.p50,
            p75:      g.p75,
            p90:      g.p90,
            // band helpers for Area components
            band_10_25: [g.p10, g.p25],
            band_25_75: [g.p25, g.p75],
            band_75_90: [g.p75, g.p90],
            isActual: false,
        }));

        return [...actualPoints, ...futurePoints];
    }, [data]);

    // Split tick labels: don't show every game
    const tickInterval = chartData.length > 40 ? 9 : chartData.length > 20 ? 4 : 2;

    const splitX = data ? data.games_played + 0.5 : null;

    return (
        <div className="w-full max-w-5xl mx-auto text-left">

            {/* ── Header ──────────────────────────────────────────────────── */}
            <div className="mb-8">
                <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight">
                    Season Simulator
                </h1>
                <p className="text-muted-foreground mt-1 text-sm">
                    AR(1) Monte Carlo — fan chart showing median projection ± uncertainty bands for the next 20 games.
                </p>
            </div>

            {/* ── Controls ─────────────────────────────────────────────── */}
            <div className="flex flex-wrap gap-4 mb-8 items-end">
                {/* Player selector */}
                <div className="space-y-1.5">
                    <span className="text-xs uppercase tracking-wider font-semibold text-primary block">player</span>
                    <Select value={player} onValueChange={setPlayer}>
                        <SelectTrigger className="h-10 w-56 bg-input border-border rounded-xl">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-popover border-border rounded-xl">
                            {PLAYERS.map((p) => (
                                <SelectItem key={p} value={p} className="text-sm py-2.5">
                                    {p}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Stat tabs */}
                <div className="space-y-1.5">
                    <span className="text-xs uppercase tracking-wider font-semibold text-primary block">stat</span>
                    <div className="flex gap-1 bg-input rounded-xl p-1">
                        {STATS.map(({ key, label }) => (
                            <button
                                key={key}
                                type="button"
                                onClick={() => setStat(key)}
                                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                                    stat === key
                                        ? 'bg-primary text-primary-foreground'
                                        : 'text-muted-foreground hover:text-foreground'
                                }`}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* ── Loading ──────────────────────────────────────────────── */}
            {loading && (
                <div className="flex items-center justify-center py-32 text-muted-foreground text-sm">
                    Running simulation...
                </div>
            )}

            {/* ── Error ────────────────────────────────────────────────── */}
            {!loading && error && (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-center">
                    <span className="text-3xl">—</span>
                    <p className="text-muted-foreground text-sm max-w-sm">{error}</p>
                </div>
            )}

            {/* ── Results ──────────────────────────────────────────────── */}
            {!loading && !error && data && (
                <div className="space-y-6">

                    {/* Stat cards */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <StatCard
                            label="Season Avg"
                            value={`${data.season_avg} ${STAT_UNITS[stat]}`}
                            sub="2025-26 actual"
                        />
                        <StatCard
                            label="Games Played"
                            value={data.games_played}
                            sub="in dataset"
                        />
                        <StatCard
                            label="AR(1) φ"
                            value={data.ar1_phi.toFixed(3)}
                            sub={data.ar1_phi > 0.1 ? 'positive momentum' : data.ar1_phi < -0.1 ? 'mean-reverting' : 'near random walk'}
                        />
                        <StatCard
                            label="AR(1) σ"
                            value={data.ar1_sigma.toFixed(2)}
                            sub="innovation std dev"
                        />
                    </div>

                    {/* Fan chart */}
                    <div className="bg-card border border-border rounded-2xl p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-base font-semibold text-foreground">
                                Game-by-Game Trajectory + 20-Game Fan
                            </h3>
                            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                <span className="flex items-center gap-1.5">
                                    <span className="inline-block w-3 h-3 rounded-full bg-primary" />
                                    Actual
                                </span>
                                <span className="flex items-center gap-1.5">
                                    <span className="inline-block w-3 h-3 rounded-full bg-indigo-400/60" />
                                    Projected (p10–p90)
                                </span>
                            </div>
                        </div>

                        <ResponsiveContainer width="100%" height={320}>
                            <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                                <XAxis
                                    dataKey="gameNum"
                                    tick={{ fontSize: 11, fill: 'var(--color-muted-foreground)' }}
                                    interval={tickInterval}
                                    label={{ value: 'Game #', position: 'insideBottomRight', offset: -4, fontSize: 11, fill: 'var(--color-muted-foreground)' }}
                                />
                                <YAxis
                                    tick={{ fontSize: 11, fill: 'var(--color-muted-foreground)' }}
                                    width={32}
                                    domain={['auto', 'auto']}
                                />
                                <Tooltip content={<FanTooltip stat={stat} />} />

                                {/* Split line between actual and projected */}
                                {splitX && (
                                    <ReferenceLine
                                        x={Math.round(splitX)}
                                        stroke="#b0a89e"
                                        strokeDasharray="4 4"
                                        label={{ value: 'Projection →', position: 'insideTopRight', fontSize: 10, fill: '#b0a89e' }}
                                    />
                                )}

                                {/* Season avg line */}
                                <ReferenceLine
                                    y={data.season_avg}
                                    stroke="rgba(99,102,241,0.4)"
                                    strokeDasharray="6 3"
                                    label={{ value: `avg ${data.season_avg}`, position: 'insideTopLeft', fontSize: 10, fill: 'rgba(99,102,241,0.7)' }}
                                />

                                {/* Projected fan: p10-p90 outer band */}
                                <Area
                                    type="monotone"
                                    dataKey="p90"
                                    stroke="none"
                                    fill="rgba(99,102,241,0.08)"
                                    activeDot={false}
                                    legendType="none"
                                    isAnimationActive={false}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="p10"
                                    stroke="none"
                                    fill="rgba(99,102,241,0.08)"
                                    activeDot={false}
                                    legendType="none"
                                    isAnimationActive={false}
                                    fillOpacity={0}
                                />

                                {/* Projected fan: p25-p75 inner band */}
                                <Area
                                    type="monotone"
                                    dataKey="p75"
                                    stroke="none"
                                    fill="rgba(99,102,241,0.18)"
                                    activeDot={false}
                                    legendType="none"
                                    isAnimationActive={false}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="p25"
                                    stroke="none"
                                    fill="rgba(99,102,241,0.18)"
                                    activeDot={false}
                                    legendType="none"
                                    isAnimationActive={false}
                                    fillOpacity={0}
                                />

                                {/* Median line */}
                                <Line
                                    type="monotone"
                                    dataKey="p50"
                                    stroke="rgba(99,102,241,0.85)"
                                    strokeWidth={2}
                                    dot={false}
                                    activeDot={{ r: 4 }}
                                    legendType="none"
                                    isAnimationActive={false}
                                />

                                {/* Actual game dots */}
                                <Line
                                    type="monotone"
                                    dataKey="actual"
                                    stroke="var(--color-primary)"
                                    strokeWidth={1.5}
                                    dot={{ r: 2.5, fill: 'var(--color-primary)', strokeWidth: 0 }}
                                    activeDot={{ r: 5 }}
                                    legendType="none"
                                    isAnimationActive={false}
                                    connectNulls={false}
                                />
                            </ComposedChart>
                        </ResponsiveContainer>

                        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
                            <span>Shaded bands show p10–p90 (outer) and p25–p75 (inner) from {1000} Monte Carlo paths.</span>
                            <span>φ = {data.ar1_phi.toFixed(3)} — {data.ar1_phi > 0.15 ? 'hot/cold streaks persist' : data.ar1_phi < -0.1 ? 'strong mean reversion' : 'near-random game-to-game variation'}</span>
                        </div>
                    </div>

                    {/* Prop probability table */}
                    <PropTable
                        propTable={data.prop_table}
                        seasonAvg={data.season_avg}
                        stat={stat}
                    />
                </div>
            )}
        </div>
    );
};

export default Simulator;
