import React, { useEffect, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const STATS = [
    { key: 'pts', label: 'Points' },
    { key: 'reb', label: 'Rebounds' },
    { key: 'ast', label: 'Assists' },
];

function confidenceColor(prob) {
    if (prob >= 0.65) return 'bg-green-500';
    if (prob >= 0.55) return 'bg-amber-400';
    return 'bg-zinc-500';
}

function confidenceTextColor(prob) {
    if (prob >= 0.65) return 'text-green-400';
    if (prob >= 0.55) return 'text-amber-400';
    return 'text-zinc-400';
}

function PickCard({ pick }) {
    const pct = Math.round(pick.prob_over * 100);
    const isOver = pick.edge === 'Over';
    const isTopPick = pick.prob_over >= 0.68;

    return (
        <div className="relative bg-card border border-border rounded-2xl p-5 flex flex-col gap-4 hover:border-primary/40 transition-colors">
            {isTopPick && (
                <span className="absolute top-4 right-4 text-xs font-semibold bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                    Top Pick
                </span>
            )}

            <div className="flex flex-col gap-1">
                <span className="text-base font-semibold text-foreground leading-tight pr-16">
                    {pick.player_name}
                </span>
                <span className="text-xs text-muted-foreground">
                    {pick.is_home ? 'vs' : '@'} {pick.opponent_abbr}
                </span>
            </div>

            <div className="flex items-center gap-3">
                <span
                    className={`text-xs font-bold px-2.5 py-1 rounded-md ${
                        isOver
                            ? 'bg-green-500/15 text-green-400'
                            : 'bg-red-500/15 text-red-400'
                    }`}
                >
                    {pick.edge.toUpperCase()}
                </span>
                <span className="text-sm text-muted-foreground">
                    Line {pick.line.toFixed(1)}
                </span>
            </div>

            <div className="flex flex-col gap-1.5">
                <div className="flex justify-between items-center">
                    <span className="text-xs text-muted-foreground">Confidence</span>
                    <span className={`text-xs font-semibold ${confidenceTextColor(pick.prob_over)}`}>
                        {pct}%
                    </span>
                </div>
                <div className="h-1.5 w-full bg-border rounded-full overflow-hidden">
                    <div
                        className={`h-full rounded-full ${confidenceColor(pick.prob_over)}`}
                        style={{ width: `${pct}%` }}
                    />
                </div>
            </div>
        </div>
    );
}

const DailyPicks = () => {
    const [activeStat, setActiveStat] = useState('pts');
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        setLoading(true);
        setError(null);
        fetch(`${API_BASE}/api/picks/?stat=${activeStat}`)
            .then((res) => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json();
            })
            .then((json) => {
                setData(json);
                setLoading(false);
            })
            .catch((err) => {
                setError(err.message);
                setLoading(false);
            });
    }, [activeStat]);

    const today = new Date().toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
    });

    return (
        <div className="w-full max-w-4xl mx-auto text-left">
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-8">
                <div>
                    <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight">
                        Today's Picks
                    </h1>
                    <p className="text-muted-foreground mt-1 text-sm">
                        Auto-generated picks for top players — updated daily at 9 AM ET
                    </p>
                </div>
                <span className="text-xs font-medium bg-border/60 text-muted-foreground px-3 py-1.5 rounded-full whitespace-nowrap">
                    {today}
                </span>
            </div>

            <div className="flex gap-1 bg-input rounded-xl p-1 mb-8 w-fit">
                {STATS.map(({ key, label }) => (
                    <button
                        key={key}
                        onClick={() => setActiveStat(key)}
                        className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                            activeStat === key
                                ? 'bg-primary text-primary-foreground'
                                : 'text-muted-foreground hover:text-foreground'
                        }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {loading && (
                <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">
                    Loading picks...
                </div>
            )}

            {error && !loading && (
                <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">
                    Failed to load picks: {error}
                </div>
            )}

            {!loading && !error && data && data.picks.length === 0 && (
                <div className="flex flex-col items-center justify-center py-24 gap-3 text-center">
                    <span className="text-4xl">—</span>
                    <p className="text-muted-foreground text-sm">
                        No picks yet — check back at 9 AM ET
                    </p>
                </div>
            )}

            {!loading && !error && data && data.picks.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {data.picks.map((pick) => (
                        <PickCard key={`${pick.player_name}-${pick.stat}`} pick={pick} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default DailyPicks;
