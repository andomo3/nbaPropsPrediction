import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const STATS = [
    { key: 'pts', label: 'Points' },
    { key: 'reb', label: 'Rebounds' },
    { key: 'ast', label: 'Assists' },
];

const MODELS = [
    { value: 'xgb',   label: 'XGBoost' },
    { value: 'rf',    label: 'Random Forest' },
    { value: 'lr',    label: 'Linear Reg.' },
    { value: 'naive', label: 'Naive' },
];

const MODEL_COLORS = {
    xgb:   'bg-amber-500/20 text-amber-400 border-amber-500/30',
    rf:    'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    lr:    'bg-green-500/20 text-green-400 border-green-500/30',
    naive: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

const TIER_FILTERS = [
    { key: 'all',      label: 'All Players' },
    { key: 'High',     label: 'High' },
    { key: 'Moderate', label: 'Moderate' },
    { key: 'Low',      label: 'Low' },
];

const TIER_STYLES = {
    High:     'bg-green-500/15 text-green-400 border-green-500/30',
    Moderate: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    Low:      'bg-red-500/15   text-red-400   border-red-500/30',
};

function TierBadge({ tier, score }) {
    return (
        <div className={`flex-shrink-0 flex flex-col items-center gap-0.5 px-2.5 py-1 rounded-lg border text-xs font-semibold ${TIER_STYLES[tier] ?? 'bg-border text-muted-foreground border-border'}`}>
            <span>{tier}</span>
            <span className="text-[10px] font-normal opacity-75">{score}</span>
        </div>
    );
}

const RANK_STYLES = [
    { bg: 'bg-amber-500/10 border-amber-500/30',  text: 'text-amber-400',  num: 'text-amber-400'  },  // 1st
    { bg: 'bg-slate-400/10 border-slate-400/30',  text: 'text-slate-300',  num: 'text-slate-300'  },  // 2nd
    { bg: 'bg-orange-700/10 border-orange-700/30', text: 'text-orange-600', num: 'text-orange-500' },  // 3rd
];

function RankBadge({ rank }) {
    if (rank === 1) return <span className="text-lg">🥇</span>;
    if (rank === 2) return <span className="text-lg">🥈</span>;
    if (rank === 3) return <span className="text-lg">🥉</span>;
    return (
        <span className="w-7 h-7 flex items-center justify-center rounded-full bg-border text-muted-foreground text-xs font-bold">
            {rank}
        </span>
    );
}

function MaeBar({ mae, maxMae }) {
    const pct = maxMae > 0 ? Math.round((mae / maxMae) * 100) : 0;
    const color = pct <= 40 ? 'bg-green-500' : pct <= 65 ? 'bg-amber-400' : 'bg-red-500';
    return (
        <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm font-semibold w-10 flex-shrink-0">{mae.toFixed(2)}</span>
            <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
            </div>
        </div>
    );
}

function PlayerRow({ row, maxMae, stat }) {
    const navigate = useNavigate();
    const rankStyle = RANK_STYLES[row.rank - 1];
    const isTopThree = row.rank <= 3;

    return (
        <div className={`flex items-center gap-4 px-5 py-4 border rounded-xl transition-colors
            ${isTopThree
                ? `${rankStyle.bg} border-opacity-50`
                : 'bg-card border-border hover:border-border/80'
            }`}
        >
            {/* Rank */}
            <div className="flex-shrink-0 w-8 flex justify-center">
                <RankBadge rank={row.rank} />
            </div>

            {/* Player name + tier badge */}
            <div className="flex-1 min-w-0 flex items-center gap-3">
                <div className="min-w-0">
                    <p className={`font-semibold truncate ${isTopThree ? rankStyle.text : 'text-foreground'}`}>
                        {row.player_name}
                    </p>
                    <p className="text-xs text-muted-foreground">{row.total_games} games</p>
                </div>
                {row.predictability_tier && (
                    <TierBadge tier={row.predictability_tier} score={row.predictability_score} />
                )}
            </div>

            {/* MAE bar */}
            <div className="w-36 flex-shrink-0">
                <p className="text-xs text-muted-foreground mb-1">MAE</p>
                <MaeBar mae={row.mae} maxMae={maxMae} />
            </div>

            {/* Hit rate */}
            <div className="w-16 flex-shrink-0 text-right hidden sm:block">
                <p className="text-xs text-muted-foreground mb-1">Hit Rate</p>
                <p className={`text-sm font-semibold ${row.hit_rate >= 0.5524 ? 'text-green-400' : 'text-muted-foreground'}`}>
                    {(row.hit_rate * 100).toFixed(1)}%
                </p>
            </div>

            {/* ROI */}
            <div className="w-16 flex-shrink-0 text-right hidden md:block">
                <p className="text-xs text-muted-foreground mb-1">ROI</p>
                <p className={`text-sm font-semibold ${row.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {row.roi >= 0 ? '+' : ''}{row.roi.toFixed(1)}%
                </p>
            </div>

            {/* Bias */}
            <div className="w-16 flex-shrink-0 text-right hidden lg:block">
                <p className="text-xs text-muted-foreground mb-1">Bias</p>
                <p className="text-sm font-semibold text-muted-foreground">
                    {row.bias >= 0 ? '+' : ''}{row.bias.toFixed(2)}
                </p>
            </div>

            {/* Profile link */}
            <button
                type="button"
                onClick={() => navigate(`/profile?player_name=${encodeURIComponent(row.player_name)}&stat=${stat}`)}
                className="flex-shrink-0 text-xs text-primary hover:text-primary/80 font-medium hidden sm:block transition-colors"
            >
                Profile →
            </button>
        </div>
    );
}

const Leaderboard = () => {
    const [stat, setStat]         = useState('pts');
    const [model, setModel]       = useState('xgb');
    const [tierFilter, setTierFilter] = useState('all');

    const [data, setData]         = useState(null);
    const [loading, setLoading]   = useState(true);
    const [error, setError]       = useState(null);

    useEffect(() => {
        setLoading(true);
        setError(null);

        const params = new URLSearchParams({ stat, model, season: '2026' });

        fetch(`${API_BASE}/api/backtest/leaderboard/?${params}`)
            .then((res) => {
                const ct = res.headers.get('content-type') || '';
                if (!ct.includes('application/json')) throw new Error(`Server error (HTTP ${res.status})`);
                return res.json().then((json) => ({ ok: res.ok, json }));
            })
            .then(({ ok, json }) => {
                if (!ok) throw new Error(json.detail || 'Request failed');
                setData(json);
            })
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, [stat, model]);

    const allRankings = data?.rankings ?? [];
    const rankings    = tierFilter === 'all'
        ? allRankings
        : allRankings.filter((r) => r.predictability_tier === tierFilter);
    const maxMae      = allRankings.length ? Math.max(...allRankings.map((r) => r.mae)) : 1;
    const statLabel   = STATS.find((s) => s.key === stat)?.label ?? stat;
    const modelLabel  = MODELS.find((m) => m.value === model)?.label ?? model;

    // tier counts for filter chip labels
    const tierCounts = allRankings.reduce((acc, r) => {
        acc[r.predictability_tier] = (acc[r.predictability_tier] ?? 0) + 1;
        return acc;
    }, {});

    return (
        <div className="w-full max-w-4xl mx-auto text-left">

            {/* ── Header ──────────────────────────────────────────────────── */}
            <div className="mb-8">
                <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight">
                    Predictability Leaderboard
                </h1>
                <p className="text-muted-foreground mt-1 text-sm">
                    Which players does the model predict most accurately? Ranked by lowest mean absolute error.
                </p>
            </div>

            {/* ── Controls ────────────────────────────────────────────────── */}
            <div className="flex flex-wrap gap-4 mb-8 items-end">
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

                {/* Model selector */}
                <div className="space-y-1.5">
                    <span className="text-xs uppercase tracking-wider font-semibold text-primary block">model</span>
                    <Select value={model} onValueChange={setModel}>
                        <SelectTrigger className="h-10 w-44 bg-input border-border rounded-xl">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-popover border-border rounded-xl">
                            {MODELS.map((m) => (
                                <SelectItem key={m.value} value={m.value} className="text-sm py-2.5">
                                    {m.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Predictability filter */}
                {data && (
                    <div className="space-y-1.5">
                        <span className="text-xs uppercase tracking-wider font-semibold text-primary block">predictability</span>
                        <div className="flex gap-1 bg-input rounded-xl p-1">
                            {TIER_FILTERS.map(({ key, label }) => {
                                const count = key === 'all' ? allRankings.length : (tierCounts[key] ?? 0);
                                return (
                                    <button
                                        key={key}
                                        type="button"
                                        onClick={() => setTierFilter(key)}
                                        className={`px-3 py-2 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
                                            tierFilter === key
                                                ? 'bg-primary text-primary-foreground'
                                                : 'text-muted-foreground hover:text-foreground'
                                        }`}
                                    >
                                        {label}
                                        <span className={`text-[10px] rounded-full px-1.5 py-0.5 ${
                                            tierFilter === key ? 'bg-white/20' : 'bg-border'
                                        }`}>{count}</span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Active filter pill */}
                {data && (
                    <div className={`mb-0.5 px-3 py-1.5 rounded-full border text-xs font-medium ${MODEL_COLORS[model]}`}>
                        {modelLabel} · {statLabel} · {data.season}
                    </div>
                )}
            </div>

            {/* ── Loading ──────────────────────────────────────────────────── */}
            {loading && (
                <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">
                    Loading leaderboard...
                </div>
            )}

            {/* ── Error ────────────────────────────────────────────────────── */}
            {!loading && error && (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
                    <span className="text-3xl">—</span>
                    <p className="text-muted-foreground text-sm max-w-sm">{error}</p>
                </div>
            )}

            {/* ── Empty (no seeded data) ───────────────────────────────────── */}
            {!loading && !error && allRankings.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
                    <span className="text-3xl">—</span>
                    <p className="text-muted-foreground text-sm">
                        No data seeded yet for this combination.
                    </p>
                    <p className="text-xs text-muted-foreground/60">
                        Run: python manage.py seed_season_backtest --season 2026
                    </p>
                </div>
            )}

            {/* ── Empty (tier filter excluded everyone) ────────────────────── */}
            {!loading && !error && allRankings.length > 0 && rankings.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
                    <span className="text-3xl">—</span>
                    <p className="text-muted-foreground text-sm">
                        No <strong>{tierFilter}</strong> predictability players in this dataset.
                    </p>
                    <button
                        type="button"
                        onClick={() => setTierFilter('all')}
                        className="text-xs text-primary underline"
                    >
                        Show all players
                    </button>
                </div>
            )}

            {/* ── Rankings list ─────────────────────────────────────────────── */}
            {!loading && !error && rankings.length > 0 && (
                <div className="space-y-2">
                    {rankings.map((row) => (
                        <PlayerRow key={row.player_name} row={row} maxMae={maxMae} stat={stat} />
                    ))}
                </div>
            )}

            {/* ── Legend ───────────────────────────────────────────────────── */}
            {!loading && !error && rankings.length > 0 && (
                <div className="mt-6 pt-4 border-t border-border flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
                    <span><strong className="text-foreground">MAE</strong> — mean absolute error (lower = more accurate)</span>
                    <span><strong className="text-foreground">Hit Rate</strong> — % of over/under calls correct (break-even: 52.4%)</span>
                    <span><strong className="text-foreground">Bias</strong> — average signed error (+ = model under-projects)</span>
                    <span><strong className="text-green-400">High</strong> / <strong className="text-amber-400">Moderate</strong> / <strong className="text-red-400">Low</strong> — composite predictability score (R² + CV + hit rate)</span>
                </div>
            )}
        </div>
    );
};

export default Leaderboard;
