import React, { useEffect, useState } from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceLine,
    ReferenceArea,
    ResponsiveContainer,
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const TIER_STYLES = {
    High:     'bg-green-500/15 text-green-400 border-green-500/30',
    Moderate: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    Low:      'bg-red-500/15   text-red-400   border-red-500/30',
};

const TIER_ORDER = { High: 3, Moderate: 2, Low: 1 };

const WINDOW_OPTIONS = [10, 20, 30];

function TierBadge({ tier, score, large = false }) {
    const base = TIER_STYLES[tier] ?? 'bg-border text-muted-foreground border-border';
    return (
        <div className={`flex flex-col items-center gap-0.5 border rounded-xl font-semibold ${base} ${large ? 'px-4 py-2 text-base' : 'px-2.5 py-1 text-xs'}`}>
            <span>{tier}</span>
            {score !== undefined && (
                <span className={`font-normal opacity-75 ${large ? 'text-sm' : 'text-[10px]'}`}>{score}</span>
            )}
        </div>
    );
}

function Skeleton() {
    return (
        <div className="space-y-3">
            <div className="h-5 w-48 rounded-lg bg-border/40 animate-pulse" />
            <div className="h-[220px] rounded-xl bg-border/40 animate-pulse" />
            <div className="h-10 w-full rounded-lg bg-border/40 animate-pulse" />
        </div>
    );
}

const tooltipContentStyle = {
    backgroundColor: 'hsl(var(--card))',
    border: '1px solid hsl(var(--border))',
    borderRadius: '0.75rem',
    color: 'hsl(var(--foreground))',
    fontSize: '0.75rem',
    padding: '0.5rem 0.75rem',
};

function CustomTooltip({ active, payload }) {
    if (!active || !payload || !payload.length) return null;
    const d = payload[0].payload;
    return (
        <div style={tooltipContentStyle} className="space-y-1">
            <p className="font-semibold text-foreground">
                Window {d.window_num} &nbsp;·&nbsp; Games {d.game_start}–{d.game_end}
            </p>
            <p className="text-muted-foreground text-[11px]">
                {d.date_start} → {d.date_end}
            </p>
            <div className="flex gap-4 mt-1">
                <span>Score: <span className="text-foreground font-medium">{d.score.toFixed(1)}</span></span>
                <span>Tier: <span className="text-foreground font-medium">{d.tier}</span></span>
            </div>
            <div className="flex gap-4">
                <span>MAE: <span className="text-foreground font-medium">{d.mae.toFixed(2)}</span></span>
                <span>Hit Rate: <span className="text-foreground font-medium">{(d.hit_rate * 100).toFixed(0)}%</span></span>
            </div>
        </div>
    );
}

function TierChangeChips({ tierChanges }) {
    if (!tierChanges || tierChanges.length === 0) {
        return (
            <p className="text-xs text-muted-foreground text-center py-2">
                No tier changes this season — consistent predictability.
            </p>
        );
    }

    return (
        <div className="flex flex-wrap gap-3">
            {tierChanges.map((change, i) => {
                const isImprovement = (TIER_ORDER[change.to_tier] ?? 0) > (TIER_ORDER[change.from_tier] ?? 0);
                const delta = change.score_after - change.score_before;
                const deltaStr = (delta >= 0 ? '+' : '') + delta.toFixed(1);
                const arrowColor = isImprovement ? 'text-green-400' : 'text-red-400';
                const chipBorder = isImprovement ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5';
                return (
                    <div
                        key={i}
                        className={`flex flex-col gap-1 px-3 py-2 rounded-xl border text-xs ${chipBorder}`}
                    >
                        <span className="text-muted-foreground font-medium">
                            Game {change.at_game} &nbsp;·&nbsp; {change.date}
                        </span>
                        <span className={`font-semibold ${arrowColor}`}>
                            {change.from_tier} → {change.to_tier}
                        </span>
                        <span className={`font-normal ${arrowColor} opacity-80`}>
                            {deltaStr} pts score
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

export default function TierHistory({ playerName, stat, season }) {
    const [window, setWindow] = useState(20);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [notFound, setNotFound] = useState(false);

    useEffect(() => {
        if (!playerName || !stat || !season) return;
        setLoading(true);
        setError(null);
        setNotFound(false);
        setData(null);

        const params = new URLSearchParams({
            player_name: playerName,
            stat,
            season: String(season),
            window: String(window),
        });

        fetch(`${API_BASE}/api/analysis/tier-history/?${params}`)
            .then((res) => {
                if (res.status === 404) {
                    setNotFound(true);
                    setLoading(false);
                    return null;
                }
                if (!res.ok) throw new Error(`Request failed: ${res.status}`);
                return res.json();
            })
            .then((json) => {
                if (json) {
                    setData(json);
                    setLoading(false);
                }
            })
            .catch((err) => {
                setError(err.message);
                setLoading(false);
            });
    }, [playerName, stat, season, window]);

    return (
        <div className="bg-card border border-border rounded-2xl p-6 space-y-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <h3 className="text-sm font-semibold text-foreground">Predictability Over Time</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                        {window}-game rolling window &nbsp;·&nbsp; 50% overlap &nbsp;·&nbsp; XGBoost
                    </p>
                </div>
                {data && (
                    <TierBadge
                        tier={data.current_tier}
                        score={data.current_score?.toFixed(1)}
                        large
                    />
                )}
            </div>

            <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Window:</span>
                <div className="flex gap-1">
                    {WINDOW_OPTIONS.map((w) => (
                        <button
                            key={w}
                            onClick={() => setWindow(w)}
                            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                                window === w
                                    ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/40'
                                    : 'bg-transparent text-muted-foreground border-border hover:border-indigo-500/30 hover:text-indigo-400'
                            }`}
                        >
                            {w}
                        </button>
                    ))}
                </div>
            </div>

            {loading && <Skeleton />}

            {!loading && notFound && (
                <p className="text-xs text-muted-foreground text-center py-8">
                    No seeded data for this player / stat / season.
                </p>
            )}

            {!loading && error && (
                <p className="text-xs text-red-400/80 text-center py-8">
                    {error}
                </p>
            )}

            {!loading && data && (
                <>
                    <ResponsiveContainer width="100%" height={220}>
                        <LineChart
                            data={data.windows}
                            margin={{ top: 8, right: 12, left: -10, bottom: 4 }}
                        >
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />

                            <ReferenceArea y1={0}  y2={40}  fill="#ef4444" fillOpacity={0.07} />
                            <ReferenceArea y1={40} y2={65}  fill="#f59e0b" fillOpacity={0.07} />
                            <ReferenceArea y1={65} y2={100} fill="#22c55e" fillOpacity={0.07} />

                            <ReferenceLine
                                y={65}
                                stroke="#22c55e"
                                strokeDasharray="4 3"
                                strokeOpacity={0.6}
                                label={{ value: 'High', position: 'right', fill: '#22c55e', fontSize: 10 }}
                            />
                            <ReferenceLine
                                y={40}
                                stroke="#f59e0b"
                                strokeDasharray="4 3"
                                strokeOpacity={0.6}
                                label={{ value: 'Moderate', position: 'right', fill: '#f59e0b', fontSize: 10 }}
                            />

                            <XAxis
                                dataKey="window_num"
                                label={{ value: 'Window', position: 'insideBottom', offset: -2, fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                                axisLine={false}
                                tickLine={false}
                                height={32}
                            />
                            <YAxis
                                domain={[0, 100]}
                                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                                axisLine={false}
                                tickLine={false}
                                width={30}
                            />
                            <Tooltip content={<CustomTooltip />} />
                            <Line
                                type="monotone"
                                dataKey="score"
                                stroke="#6366f1"
                                strokeWidth={2}
                                dot={{ r: 3, fill: '#6366f1', strokeWidth: 0 }}
                                activeDot={{ r: 5, fill: '#818cf8' }}
                            />
                        </LineChart>
                    </ResponsiveContainer>

                    <div>
                        <p className="text-xs text-muted-foreground mb-2 font-medium">Tier Changes</p>
                        <TierChangeChips tierChanges={data.tier_changes} />
                    </div>
                </>
            )}
        </div>
    );
}
