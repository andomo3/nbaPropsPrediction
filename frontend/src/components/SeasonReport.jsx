import React, { useEffect, useState } from 'react';
import {
    ComposedChart,
    Bar,
    Line,
    LineChart,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ReferenceLine,
    ResponsiveContainer,
} from 'recharts';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

// Must stay in sync with backend constants.py
const PLAYERS = [
    'Nikola Jokic',
    'Shai Gilgeous-Alexander',
    'Anthony Edwards',
    'Jayson Tatum',
    'LeBron James',
    'Stephen Curry',
    'Giannis Antetokounmpo',
    'Luka Doncic',
    'Tyrese Haliburton',
    'Joel Embiid',
];

const STATS = [
    { key: 'pts', label: 'Points' },
    { key: 'reb', label: 'Rebounds' },
    { key: 'ast', label: 'Assists' },
];

const SEASONS = [
    { value: '2026', label: '2025-26' },
    { value: '2025', label: '2024-25' },
    { value: '2024', label: '2023-24' },
    { value: '2023', label: '2022-23' },
];

// ── Shared tooltip style ──────────────────────────────────────────────────────
const tooltipStyle = {
    contentStyle: {
        background: 'hsl(var(--card))',
        border: '1px solid hsl(var(--border))',
        borderRadius: '8px',
        fontSize: 12,
    },
};

// ── StatCard ──────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, highlight }) {
    const colorClass =
        highlight === 'green'
            ? 'text-green-400'
            : highlight === 'red'
            ? 'text-red-400'
            : highlight === 'amber'
            ? 'text-amber-400'
            : 'text-foreground';

    return (
        <div className="flex flex-col gap-1 bg-card border border-border rounded-xl p-4">
            <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                {label}
            </span>
            <span className={`text-2xl font-bold ${colorClass}`}>{value}</span>
            {sub && (
                <span className="text-xs text-muted-foreground">{sub}</span>
            )}
        </div>
    );
}

// ── Custom tooltip for Actual vs Projection chart ─────────────────────────────
function ActualVsProjectionTooltip({ active, payload, label }) {
    if (!active || !payload?.length) return null;
    const actual = payload.find((p) => p.dataKey === 'actual');
    const proj = payload.find((p) => p.dataKey === 'projection');
    const err = actual && proj ? (actual.value - proj.value).toFixed(1) : null;
    return (
        <div
            style={{
                background: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: 8,
                padding: '8px 12px',
                fontSize: 12,
            }}
        >
            <p className="font-semibold mb-1">{label}</p>
            {actual && (
                <p style={{ color: actual.color }}>
                    Actual: <strong>{actual.value}</strong>
                </p>
            )}
            {proj && (
                <p style={{ color: proj.color }}>
                    Model: <strong>{Number(proj.value).toFixed(1)}</strong>
                </p>
            )}
            {err !== null && (
                <p className="mt-1 text-muted-foreground">
                    Error: {err >= 0 ? '+' : ''}{err}
                </p>
            )}
        </div>
    );
}

// ── Main component ────────────────────────────────────────────────────────────
const SeasonReport = () => {
    const [player, setPlayer] = useState(PLAYERS[0]);
    const [stat, setStat] = useState('pts');
    const [season, setSeason] = useState('2026');

    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Auto-fetch whenever player / stat / season changes
    useEffect(() => {
        setLoading(true);
        setError(null);
        setData(null);

        const params = new URLSearchParams({
            player_name: player,
            stat,
            season,
        });

        fetch(`${API_BASE}/api/backtest/season-summary/?${params}`)
            .then((res) => {
                const contentType = res.headers.get('content-type') || '';
                if (!contentType.includes('application/json')) {
                    throw new Error(`Server error (HTTP ${res.status})`);
                }
                return res.json().then((json) => ({ ok: res.ok, json }));
            })
            .then(({ ok, json }) => {
                if (!ok) throw new Error(json.detail || 'Request failed');
                setData(json);
            })
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, [player, stat, season]);

    // ── Derived display values ────────────────────────────────────────────────
    const summary = data?.summary;
    const perGame = data?.per_game ?? [];
    const seasonLabel = data?.season ?? SEASONS.find((s) => s.value === season)?.label ?? season;

    const pnlColor = summary?.total_pnl >= 0 ? '#22c55e' : '#ef4444';

    const chartData = perGame.map((g, i) => ({
        date: g.date.slice(5),   // "MM-DD"
        index: i + 1,
        actual: g.actual,
        projection: parseFloat(Number(g.projection).toFixed(1)),
        pnl: parseFloat(g.cumulative_pnl.toFixed(2)),
    }));

    // ── Stat-card highlight helpers ───────────────────────────────────────────
    const hitRateHighlight = !summary
        ? null
        : summary.hit_rate >= 0.5524   // break-even at -110
        ? 'green'
        : 'red';

    const roiHighlight = !summary ? null : summary.roi >= 0 ? 'green' : 'red';
    const pnlHighlight = !summary
        ? null
        : summary.total_pnl >= 0
        ? 'green'
        : 'red';

    // Bias: close to 0 is good; + means model under-projected, - over-projected
    const biasHighlight = !summary
        ? null
        : Math.abs(summary.bias) < 0.5
        ? 'green'
        : Math.abs(summary.bias) < 1.5
        ? 'amber'
        : 'red';

    const statLabel = STATS.find((s) => s.key === stat)?.label ?? stat;

    return (
        <div className="w-full max-w-4xl mx-auto text-left">

            {/* ── Header ──────────────────────────────────────────────────── */}
            <div className="mb-8">
                <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight">
                    Season Report Card
                </h1>
                <p className="text-muted-foreground mt-1 text-sm">
                    How well did the model predict each player over a full season?
                </p>
            </div>

            {/* ── Controls ────────────────────────────────────────────────── */}
            <div className="bg-card border border-border rounded-2xl p-5 mb-8">
                <div className="grid gap-4 sm:grid-cols-3">

                    {/* Player */}
                    <div className="space-y-2">
                        <span className="text-xs uppercase tracking-wider font-semibold text-primary block">
                            player
                        </span>
                        <Select value={player} onValueChange={setPlayer}>
                            <SelectTrigger className="h-11 bg-input border-border rounded-xl">
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

                    {/* Stat */}
                    <div className="space-y-2">
                        <span className="text-xs uppercase tracking-wider font-semibold text-primary block">
                            stat
                        </span>
                        <div className="flex gap-1 bg-input rounded-xl p-1 h-11">
                            {STATS.map(({ key, label }) => (
                                <button
                                    key={key}
                                    type="button"
                                    onClick={() => setStat(key)}
                                    className={`flex-1 text-sm font-medium rounded-lg transition-colors ${
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

                    {/* Season */}
                    <div className="space-y-2">
                        <span className="text-xs uppercase tracking-wider font-semibold text-primary block">
                            season
                        </span>
                        <Select value={season} onValueChange={setSeason}>
                            <SelectTrigger className="h-11 bg-input border-border rounded-xl">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-popover border-border rounded-xl">
                                {SEASONS.map((s) => (
                                    <SelectItem key={s.value} value={s.value} className="text-sm py-2.5">
                                        {s.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            </div>

            {/* ── Loading ──────────────────────────────────────────────────── */}
            {loading && (
                <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">
                    Loading report...
                </div>
            )}

            {/* ── Error ────────────────────────────────────────────────────── */}
            {!loading && error && (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
                    <span className="text-3xl">—</span>
                    <p className="text-muted-foreground text-sm max-w-sm">{error}</p>
                    <p className="text-xs text-muted-foreground/60">
                        Data is seeded for the 2023-24 season. Other seasons may not yet be available.
                    </p>
                </div>
            )}

            {/* ── Results ──────────────────────────────────────────────────── */}
            {!loading && !error && data && (
                <div className="space-y-6">

                    {/* Title row */}
                    <div className="flex items-baseline gap-2">
                        <h2 className="text-lg font-semibold text-foreground">
                            {player}
                        </h2>
                        <span className="text-sm text-muted-foreground">
                            — {statLabel} · {seasonLabel}
                        </span>
                    </div>

                    {/* ── Summary cards ─────────────────────────────────────── */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        <StatCard
                            label="Games"
                            value={summary.total_games}
                        />
                        <StatCard
                            label="MAE"
                            value={summary.mae.toFixed(2)}
                            sub="Mean absolute error"
                        />
                        <StatCard
                            label="Bias"
                            value={`${summary.bias >= 0 ? '+' : ''}${summary.bias.toFixed(2)}`}
                            sub={summary.bias >= 0 ? 'Model under-projected' : 'Model over-projected'}
                            highlight={biasHighlight}
                        />
                        <StatCard
                            label="Hit Rate"
                            value={`${(summary.hit_rate * 100).toFixed(1)}%`}
                            sub="Over/under correct"
                            highlight={hitRateHighlight}
                        />
                        <StatCard
                            label="P&L (units)"
                            value={`${summary.total_pnl >= 0 ? '+' : ''}${summary.total_pnl.toFixed(2)}`}
                            highlight={pnlHighlight}
                        />
                        <StatCard
                            label="ROI"
                            value={`${summary.roi >= 0 ? '+' : ''}${summary.roi.toFixed(1)}%`}
                            sub="At -110 odds"
                            highlight={roiHighlight}
                        />
                    </div>

                    {/* ── Actual vs Projection chart ─────────────────────── */}
                    {chartData.length > 0 && (
                        <div className="bg-card border border-border rounded-2xl p-5">
                            <p className="text-xs uppercase tracking-wider font-semibold text-muted-foreground mb-4">
                                Actual vs Model Projection — per game
                            </p>
                            <ResponsiveContainer width="100%" height={240}>
                                <ComposedChart
                                    data={chartData}
                                    margin={{ top: 4, right: 12, bottom: 4, left: 0 }}
                                >
                                    <CartesianGrid
                                        strokeDasharray="3 3"
                                        stroke="rgba(255,255,255,0.06)"
                                    />
                                    <XAxis
                                        dataKey="date"
                                        tick={{ fontSize: 10, fill: '#888' }}
                                        interval="preserveStartEnd"
                                    />
                                    <YAxis tick={{ fontSize: 10, fill: '#888' }} />
                                    <Tooltip content={<ActualVsProjectionTooltip />} />
                                    <Legend
                                        wrapperStyle={{ fontSize: 12, color: '#888' }}
                                        formatter={(val) =>
                                            val === 'actual' ? 'Actual' : 'Model Proj.'
                                        }
                                    />
                                    <Bar
                                        dataKey="actual"
                                        fill="rgba(99,102,241,0.45)"
                                        radius={[2, 2, 0, 0]}
                                        maxBarSize={10}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="projection"
                                        stroke="#f59e0b"
                                        dot={false}
                                        strokeWidth={2}
                                    />
                                </ComposedChart>
                            </ResponsiveContainer>
                        </div>
                    )}

                    {/* ── Cumulative P&L chart ───────────────────────────── */}
                    {chartData.length > 0 && (
                        <div className="bg-card border border-border rounded-2xl p-5">
                            <p className="text-xs uppercase tracking-wider font-semibold text-muted-foreground mb-4">
                                Cumulative P&L (flat-unit betting at -110)
                            </p>
                            <ResponsiveContainer width="100%" height={180}>
                                <LineChart
                                    data={chartData}
                                    margin={{ top: 4, right: 12, bottom: 4, left: 0 }}
                                >
                                    <CartesianGrid
                                        strokeDasharray="3 3"
                                        stroke="rgba(255,255,255,0.06)"
                                    />
                                    <XAxis
                                        dataKey="date"
                                        tick={{ fontSize: 10, fill: '#888' }}
                                        interval="preserveStartEnd"
                                    />
                                    <YAxis tick={{ fontSize: 10, fill: '#888' }} />
                                    <Tooltip
                                        {...tooltipStyle}
                                        formatter={(v) => [
                                            `${v >= 0 ? '+' : ''}${v}u`,
                                            'Cumulative P&L',
                                        ]}
                                        labelFormatter={(l) => `Date: ${l}`}
                                    />
                                    <ReferenceLine
                                        y={0}
                                        stroke="#555"
                                        strokeDasharray="4 2"
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="pnl"
                                        stroke={pnlColor}
                                        dot={false}
                                        strokeWidth={2}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    )}

                    {/* ── Game-by-game table ─────────────────────────────── */}
                    {perGame.length > 0 && (
                        <div className="bg-card border border-border rounded-2xl overflow-hidden">
                            <div className="px-5 py-3 border-b border-border">
                                <p className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">
                                    Game-by-Game Breakdown
                                </p>
                            </div>
                            <div className="overflow-y-auto max-h-96">
                                <table className="w-full text-sm">
                                    <thead className="sticky top-0 bg-card border-b border-border">
                                        <tr>
                                            {[
                                                'Date',
                                                'Opp',
                                                'Actual',
                                                'Proj',
                                                'Error',
                                                'Line',
                                                '',
                                                'P&L',
                                            ].map((h) => (
                                                <th
                                                    key={h}
                                                    className="text-left px-4 py-2.5 text-xs font-semibold text-muted-foreground"
                                                >
                                                    {h}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {perGame.map((g, i) => {
                                            const err = g.error;
                                            return (
                                                <tr
                                                    key={i}
                                                    className="border-b border-border/50 hover:bg-accent/30 transition-colors"
                                                >
                                                    <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">
                                                        {g.date}
                                                    </td>
                                                    <td className="px-4 py-2.5 font-medium">
                                                        {g.opponent}
                                                    </td>
                                                    <td className="px-4 py-2.5 font-semibold">
                                                        {g.actual}
                                                    </td>
                                                    <td className="px-4 py-2.5 text-muted-foreground">
                                                        {Number(g.projection).toFixed(1)}
                                                    </td>
                                                    <td
                                                        className={`px-4 py-2.5 font-medium ${
                                                            err > 0
                                                                ? 'text-green-400'
                                                                : err < 0
                                                                ? 'text-red-400'
                                                                : 'text-muted-foreground'
                                                        }`}
                                                    >
                                                        {err >= 0 ? '+' : ''}
                                                        {Number(err).toFixed(1)}
                                                    </td>
                                                    <td className="px-4 py-2.5 text-muted-foreground">
                                                        {Number(g.line).toFixed(1)}
                                                    </td>
                                                    <td className="px-4 py-2.5">
                                                        {g.correct ? (
                                                            <span className="text-green-400 font-bold">
                                                                ✓
                                                            </span>
                                                        ) : (
                                                            <span className="text-red-400 font-bold">
                                                                ✗
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td
                                                        className={`px-4 py-2.5 font-semibold ${
                                                            g.pnl >= 0
                                                                ? 'text-green-400'
                                                                : 'text-red-400'
                                                        }`}
                                                    >
                                                        {g.pnl >= 0 ? '+' : ''}
                                                        {Number(g.pnl).toFixed(2)}u
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default SeasonReport;
