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

// Color palette for the 4 models
const MODEL_COLORS = {
    xgb:   '#f59e0b',  // amber
    rf:    '#6366f1',  // indigo
    lr:    '#22c55e',  // green
    naive: '#94a3b8',  // slate
};

const tooltipStyle = {
    contentStyle: {
        background: 'hsl(var(--card))',
        border: '1px solid hsl(var(--border))',
        borderRadius: '8px',
        fontSize: 12,
    },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function best(models, key, direction = 'low') {
    const available = models.filter((m) => m.available && m.summary);
    if (!available.length) return null;
    return available.reduce((a, b) =>
        direction === 'low'
            ? a.summary[key] < b.summary[key] ? a : b
            : a.summary[key] > b.summary[key] ? a : b
    ).model;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, highlight }) {
    const colorClass =
        highlight === 'green' ? 'text-green-400'
        : highlight === 'red' ? 'text-red-400'
        : highlight === 'amber' ? 'text-amber-400'
        : 'text-foreground';
    return (
        <div className="flex flex-col gap-1 bg-card border border-border rounded-xl p-4">
            <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                {label}
            </span>
            <span className={`text-2xl font-bold ${colorClass}`}>{value}</span>
            {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
        </div>
    );
}

function ModelComparisonTable({ comparison }) {
    if (!comparison) return null;
    const { models } = comparison;
    const bestMae     = best(models, 'mae',      'low');
    const bestHitRate = best(models, 'hit_rate', 'high');
    const bestRoi     = best(models, 'roi',      'high');

    return (
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
            <div className="px-5 py-3 border-b border-border">
                <p className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">
                    Model Comparison
                </p>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="border-b border-border bg-card">
                        <tr>
                            {['Model', 'MAE', 'Hit Rate', 'ROI', 'P&L'].map((h) => (
                                <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-muted-foreground">
                                    {h}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {models.map((m) => (
                            <tr key={m.model} className="border-b border-border/50 hover:bg-accent/20 transition-colors">
                                {/* Model name with colour dot */}
                                <td className="px-5 py-3 font-medium">
                                    <div className="flex items-center gap-2">
                                        <span
                                            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                                            style={{ background: MODEL_COLORS[m.model] }}
                                        />
                                        {m.label}
                                    </div>
                                </td>
                                {m.available && m.summary ? (
                                    <>
                                        <td className={`px-5 py-3 font-semibold ${m.model === bestMae ? 'text-green-400' : ''}`}>
                                            {m.summary.mae.toFixed(2)}
                                        </td>
                                        <td className={`px-5 py-3 font-semibold ${m.model === bestHitRate ? 'text-green-400' : ''}`}>
                                            {(m.summary.hit_rate * 100).toFixed(1)}%
                                        </td>
                                        <td className={`px-5 py-3 font-semibold ${
                                            m.model === bestRoi ? 'text-green-400'
                                            : m.summary.roi < 0 ? 'text-red-400' : ''
                                        }`}>
                                            {m.summary.roi >= 0 ? '+' : ''}{m.summary.roi.toFixed(1)}%
                                        </td>
                                        <td className={`px-5 py-3 font-semibold ${m.summary.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {m.summary.total_pnl >= 0 ? '+' : ''}{m.summary.total_pnl.toFixed(2)}u
                                        </td>
                                    </>
                                ) : (
                                    <td colSpan={4} className="px-5 py-3 text-muted-foreground text-xs italic">
                                        Not yet seeded
                                    </td>
                                )}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function OverlayTooltip({ active, payload, label }) {
    if (!active || !payload?.length) return null;
    return (
        <div style={{
            background: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: 8, padding: '8px 12px', fontSize: 12,
        }}>
            <p className="font-semibold mb-1">{label}</p>
            {payload.map((p) => (
                <p key={p.dataKey} style={{ color: p.color }}>
                    {p.name}: <strong>{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</strong>
                </p>
            ))}
        </div>
    );
}

// ── Main component ────────────────────────────────────────────────────────────

const SeasonReport = () => {
    const [player, setPlayer] = useState(PLAYERS[0]);
    const [stat, setStat]     = useState('pts');
    const [season, setSeason] = useState('2026');

    const [data, setData]           = useState(null);
    const [comparison, setComparison] = useState(null);
    const [loading, setLoading]     = useState(false);
    const [error, setError]         = useState(null);

    useEffect(() => {
        setLoading(true);
        setError(null);
        setData(null);
        setComparison(null);

        const params = new URLSearchParams({ player_name: player, stat, season });

        const fetchSummary = fetch(`${API_BASE}/api/backtest/season-summary/?${params}`)
            .then((res) => {
                const ct = res.headers.get('content-type') || '';
                if (!ct.includes('application/json')) throw new Error(`Server error (HTTP ${res.status})`);
                return res.json().then((json) => ({ ok: res.ok, json }));
            })
            .then(({ ok, json }) => {
                if (!ok) throw new Error(json.detail || 'Request failed');
                setData(json);
            });

        const fetchComparison = fetch(`${API_BASE}/api/backtest/model-comparison/?${params}`)
            .then((res) => {
                const ct = res.headers.get('content-type') || '';
                if (!ct.includes('application/json')) return null;
                return res.json().then((json) => ({ ok: res.ok, json }));
            })
            .then((result) => {
                if (result?.ok) setComparison(result.json);
            })
            .catch(() => {}); // comparison is non-critical — silently skip if unavailable

        Promise.all([fetchSummary, fetchComparison])
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, [player, stat, season]);

    // ── Derived values ────────────────────────────────────────────────────────
    const summary  = data?.summary;
    const perGame  = data?.per_game ?? [];
    const seasonLabel = data?.season ?? SEASONS.find((s) => s.value === season)?.label ?? season;
    const pnlColor = summary?.total_pnl >= 0 ? '#22c55e' : '#ef4444';
    const statLabel = STATS.find((s) => s.key === stat)?.label ?? stat;

    // Single-model chart data (for the PnL chart)
    const pnlChartData = perGame.map((g) => ({
        date: g.date.slice(5),
        pnl:  parseFloat(g.cumulative_pnl.toFixed(2)),
    }));

    // Overlay chart data — merge actuals + all model projections by index
    const overlayChartData = (() => {
        if (!comparison) return null;
        return comparison.dates.map((date, i) => {
            const point = { date: date.slice(5), actual: comparison.actuals[i] };
            comparison.models.forEach((m) => {
                if (m.available && m.projections[i] != null) {
                    point[m.model] = m.projections[i];
                }
            });
            return point;
        });
    })();

    // Summary card highlights
    const hitRateHighlight = !summary ? null : summary.hit_rate >= 0.5524 ? 'green' : 'red';
    const roiHighlight     = !summary ? null : summary.roi >= 0 ? 'green' : 'red';
    const pnlHighlight     = !summary ? null : summary.total_pnl >= 0 ? 'green' : 'red';
    const biasHighlight    = !summary ? null
        : Math.abs(summary.bias) < 0.5 ? 'green'
        : Math.abs(summary.bias) < 1.5 ? 'amber' : 'red';

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
                    <div className="space-y-2">
                        <span className="text-xs uppercase tracking-wider font-semibold text-primary block">player</span>
                        <Select value={player} onValueChange={setPlayer}>
                            <SelectTrigger className="h-11 bg-input border-border rounded-xl">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-popover border-border rounded-xl">
                                {PLAYERS.map((p) => (
                                    <SelectItem key={p} value={p} className="text-sm py-2.5">{p}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <span className="text-xs uppercase tracking-wider font-semibold text-primary block">stat</span>
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

                    <div className="space-y-2">
                        <span className="text-xs uppercase tracking-wider font-semibold text-primary block">season</span>
                        <Select value={season} onValueChange={setSeason}>
                            <SelectTrigger className="h-11 bg-input border-border rounded-xl">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-popover border-border rounded-xl">
                                {SEASONS.map((s) => (
                                    <SelectItem key={s.value} value={s.value} className="text-sm py-2.5">{s.label}</SelectItem>
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
                        Data is seeded for the 2025-26 season. Other seasons may not yet be available.
                    </p>
                </div>
            )}

            {/* ── Results ──────────────────────────────────────────────────── */}
            {!loading && !error && data && (
                <div className="space-y-6">

                    <div className="flex items-baseline gap-2">
                        <h2 className="text-lg font-semibold text-foreground">{player}</h2>
                        <span className="text-sm text-muted-foreground">
                            — {statLabel} · {seasonLabel}
                        </span>
                    </div>

                    {/* ── XGBoost summary cards ─────────────────────────── */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        <StatCard label="Games" value={summary.total_games} />
                        <StatCard label="MAE" value={summary.mae.toFixed(2)} sub="Mean absolute error" />
                        <StatCard
                            label="Bias"
                            value={`${summary.bias >= 0 ? '+' : ''}${summary.bias.toFixed(2)}`}
                            sub={summary.bias >= 0 ? 'Model under-projected' : 'Model over-projected'}
                            highlight={biasHighlight}
                        />
                        <StatCard label="Hit Rate" value={`${(summary.hit_rate * 100).toFixed(1)}%`} sub="Over/under correct" highlight={hitRateHighlight} />
                        <StatCard label="P&L (units)" value={`${summary.total_pnl >= 0 ? '+' : ''}${summary.total_pnl.toFixed(2)}`} highlight={pnlHighlight} />
                        <StatCard label="ROI" value={`${summary.roi >= 0 ? '+' : ''}${summary.roi.toFixed(1)}%`} sub="At -110 odds" highlight={roiHighlight} />
                    </div>

                    {/* ── Model comparison table ────────────────────────── */}
                    <ModelComparisonTable comparison={comparison} />

                    {/* ── Overlay chart: all 4 projection lines ─────────── */}
                    {overlayChartData && overlayChartData.length > 0 && (
                        <div className="bg-card border border-border rounded-2xl p-5">
                            <p className="text-xs uppercase tracking-wider font-semibold text-muted-foreground mb-4">
                                Actual vs All Model Projections
                            </p>
                            <ResponsiveContainer width="100%" height={260}>
                                <ComposedChart data={overlayChartData} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#888' }} interval="preserveStartEnd" />
                                    <YAxis tick={{ fontSize: 10, fill: '#888' }} />
                                    <Tooltip content={<OverlayTooltip />} />
                                    <Legend wrapperStyle={{ fontSize: 12, color: '#888' }} />
                                    <Bar dataKey="actual" name="Actual" fill="rgba(99,102,241,0.35)" radius={[2,2,0,0]} maxBarSize={10} />
                                    {comparison.models.filter((m) => m.available).map((m) => (
                                        <Line
                                            key={m.model}
                                            type="monotone"
                                            dataKey={m.model}
                                            name={m.label}
                                            stroke={MODEL_COLORS[m.model]}
                                            dot={false}
                                            strokeWidth={2}
                                        />
                                    ))}
                                </ComposedChart>
                            </ResponsiveContainer>
                        </div>
                    )}

                    {/* ── Cumulative P&L (XGBoost) ──────────────────────── */}
                    {pnlChartData.length > 0 && (
                        <div className="bg-card border border-border rounded-2xl p-5">
                            <p className="text-xs uppercase tracking-wider font-semibold text-muted-foreground mb-4">
                                Cumulative P&L — XGBoost (flat-unit at -110)
                            </p>
                            <ResponsiveContainer width="100%" height={180}>
                                <LineChart data={pnlChartData} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#888' }} interval="preserveStartEnd" />
                                    <YAxis tick={{ fontSize: 10, fill: '#888' }} />
                                    <Tooltip
                                        {...tooltipStyle}
                                        formatter={(v) => [`${v >= 0 ? '+' : ''}${v}u`, 'Cumulative P&L']}
                                        labelFormatter={(l) => `Date: ${l}`}
                                    />
                                    <ReferenceLine y={0} stroke="#555" strokeDasharray="4 2" />
                                    <Line type="monotone" dataKey="pnl" stroke={pnlColor} dot={false} strokeWidth={2} />
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
                                            {['Date','Opp','Actual','Proj','Error','Line','','P&L'].map((h) => (
                                                <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-muted-foreground">{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {perGame.map((g, i) => (
                                            <tr key={i} className="border-b border-border/50 hover:bg-accent/30 transition-colors">
                                                <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">{g.date}</td>
                                                <td className="px-4 py-2.5 font-medium">{g.opponent}</td>
                                                <td className="px-4 py-2.5 font-semibold">{g.actual}</td>
                                                <td className="px-4 py-2.5 text-muted-foreground">{Number(g.projection).toFixed(1)}</td>
                                                <td className={`px-4 py-2.5 font-medium ${g.error > 0 ? 'text-green-400' : g.error < 0 ? 'text-red-400' : 'text-muted-foreground'}`}>
                                                    {g.error >= 0 ? '+' : ''}{Number(g.error).toFixed(1)}
                                                </td>
                                                <td className="px-4 py-2.5 text-muted-foreground">{Number(g.line).toFixed(1)}</td>
                                                <td className="px-4 py-2.5">
                                                    {g.correct
                                                        ? <span className="text-green-400 font-bold">✓</span>
                                                        : <span className="text-red-400 font-bold">✗</span>}
                                                </td>
                                                <td className={`px-4 py-2.5 font-semibold ${g.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {g.pnl >= 0 ? '+' : ''}{Number(g.pnl).toFixed(2)}u
                                                </td>
                                            </tr>
                                        ))}
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
