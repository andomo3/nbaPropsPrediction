import React, { useEffect, useState } from 'react';
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

const TIER_ORDER = { High: 2, Moderate: 1, Low: 0 };

const TIER_CIRCLE = {
    High:     'bg-green-500/20 text-green-400',
    Moderate: 'bg-amber-500/20 text-amber-400',
    Low:      'bg-red-500/20 text-red-400',
};

function ScoreCircle({ score, tier }) {
    const base = 'w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0';
    if (!tier) {
        return (
            <div className={`${base} border border-border text-muted-foreground`}>
                —
            </div>
        );
    }
    return (
        <div className={`${base} ${TIER_CIRCLE[tier] ?? 'bg-border text-muted-foreground'}`}>
            {score != null ? score.toFixed(0) : '—'}
        </div>
    );
}

function TierChangedBadge({ s1tier, s2tier }) {
    if (!s1tier || !s2tier) return null;
    const delta = TIER_ORDER[s2tier] - TIER_ORDER[s1tier];
    if (delta === 0) return null;
    return (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30 ml-1.5 flex-shrink-0">
            {delta > 0 ? 'Tier ↑' : 'Tier ↓'}
        </span>
    );
}

function DeltaCell({ delta }) {
    if (delta == null) return <span className="text-muted-foreground">—</span>;
    if (delta > 0) return <span className="text-green-400 font-semibold">↑ +{delta.toFixed(1)}</span>;
    if (delta < 0) return <span className="text-red-400 font-semibold">↓ {delta.toFixed(1)}</span>;
    return <span className="text-muted-foreground font-semibold">0.0</span>;
}

function SideBySideRow({ player, seasons }) {
    const [s1key, s2key] = seasons;
    const d1 = player.seasons[s1key];
    const d2 = player.seasons[s2key];

    const s1Available = d1?.available;
    const s2Available = d2?.available;

    return (
        <div className="flex flex-wrap sm:flex-nowrap items-center gap-x-3 sm:gap-x-4 gap-y-2 px-4 sm:px-5 py-4 bg-card border border-border rounded-xl hover:border-border/80 transition-colors">
            {/* Player name — full row on mobile, first column on ≥sm */}
            <div className="w-full sm:w-auto sm:flex-1 min-w-0">
                <p className="font-semibold text-foreground truncate">{player.player_name}</p>
                {s2Available && (
                    <p className="text-xs text-muted-foreground">{d2.total_games} games (2025-26)</p>
                )}
            </div>

            {/* Season 1 */}
            <div className="flex flex-col items-center gap-1 w-24 flex-shrink-0">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">2024-25</p>
                <ScoreCircle
                    score={s1Available ? d1.predictability_score : null}
                    tier={s1Available ? d1.predictability_tier : null}
                />
                {s1Available
                    ? <span className="text-[10px] text-muted-foreground">{d1.predictability_tier}</span>
                    : <span className="text-[10px] text-muted-foreground">—</span>
                }
            </div>

            {/* Season 2 */}
            <div className="flex flex-col items-center gap-1 w-24 flex-shrink-0">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider">2025-26</p>
                <ScoreCircle
                    score={s2Available ? d2.predictability_score : null}
                    tier={s2Available ? d2.predictability_tier : null}
                />
                {s2Available
                    ? <span className="text-[10px] text-muted-foreground">{d2.predictability_tier}</span>
                    : <span className="text-[10px] text-muted-foreground">—</span>
                }
            </div>

            {/* Delta + tier badge */}
            <div className="w-20 sm:w-28 flex-shrink-0 flex items-center justify-center">
                <DeltaCell delta={player.score_delta} />
                {player.tier_changed && s1Available && s2Available && (
                    <TierChangedBadge
                        s1tier={d1.predictability_tier}
                        s2tier={d2.predictability_tier}
                    />
                )}
            </div>

            {/* MAE 2025-26 */}
            <div className="w-16 flex-shrink-0 text-right hidden sm:block">
                <p className="text-[10px] text-muted-foreground mb-1">MAE 25-26</p>
                <p className="text-sm font-semibold text-foreground">
                    {s2Available ? d2.mae.toFixed(2) : '—'}
                </p>
            </div>
        </div>
    );
}

function DeltaBar({ player, seasons, maxAbsDelta }) {
    const [s1key, s2key] = seasons;
    const d1 = player.seasons[s1key];
    const d2 = player.seasons[s2key];
    const s1Available = d1?.available;
    const s2Available = d2?.available;
    const delta = player.score_delta;

    const s1Score = s1Available ? d1.predictability_score : null;
    const s2Score = s2Available ? d2.predictability_score : null;
    const s1Tier  = s1Available ? d1.predictability_tier : null;
    const s2Tier  = s2Available ? d2.predictability_tier : null;

    const barPct = maxAbsDelta > 0 && delta != null ? (Math.abs(delta) / maxAbsDelta) * 100 : 0;
    const isPositive = delta != null && delta > 0;

    return (
        <div className="flex flex-wrap sm:flex-nowrap items-center gap-x-3 sm:gap-x-4 gap-y-2 px-4 sm:px-5 py-4 bg-card border border-border rounded-xl transition-colors">
            {/* Player name — full row on mobile, first column on ≥sm */}
            <div className="w-full sm:w-36 flex-shrink-0 min-w-0">
                <p className="font-semibold text-foreground truncate text-sm">{player.player_name}</p>
            </div>

            {/* Score 2024-25 */}
            <div className="flex items-center gap-1.5 flex-shrink-0">
                <ScoreCircle score={s1Score} tier={s1Tier} />
            </div>

            {/* Timeline bar */}
            <div className="flex-1 min-w-0 flex items-center gap-2">
                {delta != null ? (
                    <div className="w-full h-2 bg-border rounded-full overflow-hidden relative">
                        <div
                            className={`h-full rounded-full absolute ${isPositive ? 'bg-green-500' : 'bg-red-500'}`}
                            style={{ width: `${barPct}%`, left: isPositive ? '50%' : `calc(50% - ${barPct / 2}%)` }}
                        />
                        <div className="absolute inset-y-0 left-1/2 w-px bg-border/60" />
                    </div>
                ) : (
                    <div className="w-full h-2 bg-border rounded-full" />
                )}
            </div>

            {/* Score 2025-26 */}
            <div className="flex items-center gap-1.5 flex-shrink-0">
                <ScoreCircle score={s2Score} tier={s2Tier} />
            </div>

            {/* Delta number */}
            <div className="w-14 sm:w-20 flex-shrink-0 text-right">
                <DeltaCell delta={delta} />
            </div>

            {/* Tier badge */}
            <div className="w-16 flex-shrink-0 hidden sm:block">
                {player.tier_changed && s1Available && s2Available && (
                    <TierChangedBadge s1tier={s1Tier} s2tier={s2Tier} />
                )}
            </div>
        </div>
    );
}

const LeaderboardComparison = () => {
    const [stat, setStat]   = useState('pts');
    const [model, setModel] = useState('xgb');
    const [view, setView]   = useState('sidebyside');

    const [data, setData]       = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState(null);

    useEffect(() => {
        setLoading(true);
        setError(null);

        const params = new URLSearchParams({ stat, model });

        fetch(`${API_BASE}/api/backtest/leaderboard-comparison/?${params}`)
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

    const players = data?.players ?? [];
    const seasons = data?.seasons ?? [];

    // API labels seasons as '2024-25' but keys each player's per-season data
    // by the season END year ('2025'). Derive the key from the label.
    const seasonEndKey = (label) => {
        const [start, end] = String(label).split('-');
        return end && end.length === 2 ? `${start.slice(0, 2)}${end}` : String(label);
    };
    const [s1key, s2key] = seasons.length >= 2
        ? [seasonEndKey(seasons[0]), seasonEndKey(seasons[1])]
        : ['2025', '2026'];

    const sortedPlayers = view === 'delta'
        ? [...players].sort((a, b) => Math.abs(b.score_delta ?? 0) - Math.abs(a.score_delta ?? 0))
        : players;

    const maxAbsDelta = sortedPlayers.reduce((max, p) => {
        const abs = p.score_delta != null ? Math.abs(p.score_delta) : 0;
        return abs > max ? abs : max;
    }, 1);

    const statLabel  = STATS.find((s) => s.key === stat)?.label ?? stat;
    const modelLabel = MODELS.find((m) => m.value === model)?.label ?? model;

    return (
        <div className="w-full max-w-4xl mx-auto text-left">

            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight">
                    Cross-Season Comparison
                </h1>
                <p className="text-muted-foreground mt-1 text-sm">
                    How has player predictability shifted between the 2024-25 and 2025-26 seasons?
                </p>
            </div>

            {/* Controls */}
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

                {/* View toggle */}
                <div className="space-y-1.5">
                    <span className="text-xs uppercase tracking-wider font-semibold text-primary block">view</span>
                    <div className="flex gap-1 bg-input rounded-xl p-1">
                        {[
                            { key: 'sidebyside', label: 'Side by Side' },
                            { key: 'delta',      label: 'Delta View' },
                        ].map(({ key, label }) => (
                            <button
                                key={key}
                                type="button"
                                onClick={() => setView(key)}
                                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                                    view === key
                                        ? 'bg-primary text-primary-foreground'
                                        : 'text-muted-foreground hover:text-foreground'
                                }`}
                            >
                                {label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Active filter pill */}
                {data && (
                    <div className="mb-0.5 px-3 py-1.5 rounded-full border text-xs font-medium bg-amber-500/20 text-amber-400 border-amber-500/30">
                        {modelLabel} · {statLabel}
                    </div>
                )}
            </div>

            {/* Loading */}
            {loading && (
                <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">
                    Loading comparison data...
                </div>
            )}

            {/* Error */}
            {!loading && error && (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
                    <span className="text-3xl">—</span>
                    <p className="text-muted-foreground text-sm max-w-sm">{error}</p>
                </div>
            )}

            {/* Empty */}
            {!loading && !error && players.length === 0 && (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
                    <span className="text-3xl">—</span>
                    <p className="text-muted-foreground text-sm">
                        No comparison data available for this combination.
                    </p>
                </div>
            )}

            {/* Side-by-side column headers */}
            {!loading && !error && players.length > 0 && view === 'sidebyside' && (
                <div className="hidden sm:flex items-center gap-4 px-5 mb-2 text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
                    <div className="flex-1">Player</div>
                    <div className="w-24 text-center">2024-25</div>
                    <div className="w-24 text-center">2025-26</div>
                    <div className="w-28 text-center">Delta</div>
                    <div className="w-16 text-right hidden sm:block">MAE 25-26</div>
                </div>
            )}

            {/* Delta view column headers */}
            {!loading && !error && players.length > 0 && view === 'delta' && (
                <div className="hidden sm:flex items-center gap-4 px-5 mb-2 text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
                    <div className="w-36">Player</div>
                    <div className="w-10">24-25</div>
                    <div className="flex-1 text-center">Change</div>
                    <div className="w-10">25-26</div>
                    <div className="w-20 text-right">Delta</div>
                    <div className="w-16">Tier</div>
                </div>
            )}

            {/* Rows */}
            {!loading && !error && sortedPlayers.length > 0 && (
                <div className="space-y-2">
                    {sortedPlayers.map((player) =>
                        view === 'sidebyside' ? (
                            <SideBySideRow
                                key={player.player_name}
                                player={player}
                                seasons={[s1key, s2key]}
                            />
                        ) : (
                            <DeltaBar
                                key={player.player_name}
                                player={player}
                                seasons={[s1key, s2key]}
                                maxAbsDelta={maxAbsDelta}
                            />
                        )
                    )}
                </div>
            )}

            {/* Legend */}
            {!loading && !error && players.length > 0 && (
                <div className="mt-6 pt-4 border-t border-border space-y-1.5 text-xs text-muted-foreground">
                    <div className="flex flex-wrap gap-x-6 gap-y-1">
                        <span>
                            <strong className="text-green-400">High</strong> — score ≥ 65
                        </span>
                        <span>
                            <strong className="text-amber-400">Moderate</strong> — score 40–64
                        </span>
                        <span>
                            <strong className="text-red-400">Low</strong> — score &lt; 40
                        </span>
                    </div>
                    <p>
                        <strong className="text-foreground">Predictability score</strong> — composite of R² (variance explained),
                        inverse coefficient of variation (consistency), and hit rate (over/under accuracy). Higher = more predictable.
                    </p>
                    <p>
                        <strong className="text-foreground">Delta</strong> — change in predictability score from 2024-25 to 2025-26.
                        Amber <strong className="text-amber-400">Tier ↑ / ↓</strong> badge indicates a tier boundary was crossed.
                    </p>
                    {view === 'delta' && (
                        <p>
                            <strong className="text-foreground">Delta View</strong> — players sorted by absolute score change, biggest movers first.
                            Bar width encodes magnitude; green = improved, red = declined.
                        </p>
                    )}
                </div>
            )}
        </div>
    );
};

export default LeaderboardComparison;
