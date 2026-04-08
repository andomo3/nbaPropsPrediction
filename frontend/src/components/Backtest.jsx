import React, { useRef, useState } from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceLine,
    ResponsiveContainer,
} from 'recharts';
import { ArrowRight } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const STAT_OPTIONS = [
    { value: 'pts', label: 'Points' },
    { value: 'reb', label: 'Rebounds' },
    { value: 'ast', label: 'Assists' },
];

function StatCard({ label, value, highlight }) {
    return (
        <div className="flex flex-col gap-1 bg-card border border-border rounded-xl p-4">
            <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                {label}
            </span>
            <span
                className={`text-2xl font-bold ${
                    highlight === 'green'
                        ? 'text-green-400'
                        : highlight === 'red'
                        ? 'text-red-400'
                        : 'text-foreground'
                }`}
            >
                {value}
            </span>
        </div>
    );
}

const Backtest = () => {
    const [playerQuery, setPlayerQuery] = useState('');
    const [playerName, setPlayerName] = useState('');
    const [playerOpen, setPlayerOpen] = useState(false);
    const [playerResults, setPlayerResults] = useState([]);
    const [playerLoading, setPlayerLoading] = useState(false);
    const [stat, setStat] = useState('pts');
    const [dateFrom, setDateFrom] = useState('2023-10-01');
    const [dateTo, setDateTo] = useState('2024-04-30');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const searchTimeout = useRef(null);

    const searchPlayers = (query) => {
        setPlayerQuery(query);
        setPlayerName(query);
        setPlayerOpen(true);
        if (searchTimeout.current) clearTimeout(searchTimeout.current);
        if (!query.trim()) { setPlayerResults([]); return; }
        setPlayerLoading(true);
        searchTimeout.current = setTimeout(async () => {
            try {
                const res = await fetch(`${API_BASE}/api/players/?q=${encodeURIComponent(query)}`);
                if (!res.ok) throw new Error('search failed');
                const data = await res.json();
                setPlayerResults(
                    Array.isArray(data) ? data.map((p) => p.full_name).filter(Boolean) : []
                );
            } catch {
                setPlayerResults([]);
            } finally {
                setPlayerLoading(false);
            }
        }, 200);
    };

    const handleRun = async () => {
        if (!playerName.trim() || !stat || !dateFrom || !dateTo) return;
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const res = await fetch(`${API_BASE}/api/backtest/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    player_name: playerName.trim(),
                    stat,
                    date_from: dateFrom,
                    date_to: dateTo,
                }),
            });
            const json = await res.json();
            if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
            setResult(json);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const agg = result?.aggregate;
    const perGame = result?.per_game || [];
    const finalPnl = agg?.total_pnl ?? 0;
    const chartColor = finalPnl >= 0 ? '#22c55e' : '#ef4444';

    const chartData = perGame.map((g) => ({
        date: g.date,
        pnl: parseFloat(g.cumulative_pnl.toFixed(2)),
    }));

    return (
        <div className="w-full max-w-4xl mx-auto text-left">
            <div className="mb-8">
                <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight">
                    Backtesting
                </h1>
                <p className="text-muted-foreground mt-1 text-sm">
                    See how the model would have performed bet-by-bet on historical games
                </p>
            </div>

            <div className="bg-card border border-border rounded-2xl p-6 mb-8 space-y-6">
                <div className="grid gap-5 md:grid-cols-2">
                    <div className="space-y-2 relative">
                        <Label className="text-xs uppercase tracking-wider font-semibold text-primary">
                            player_name
                        </Label>
                        <Input
                            value={playerQuery}
                            onChange={(e) => searchPlayers(e.target.value)}
                            onFocus={() => setPlayerOpen(true)}
                            onBlur={() => setTimeout(() => setPlayerOpen(false), 120)}
                            placeholder="Search player"
                            autoComplete="off"
                            className="h-12 bg-input border-border rounded-xl"
                        />
                        {playerOpen && (
                            <div className="absolute z-50 mt-1 w-full rounded-xl border border-border bg-popover text-popover-foreground max-h-52 overflow-y-auto shadow-lg">
                                {playerLoading && (
                                    <div className="px-3 py-2 text-sm text-muted-foreground">Searching...</div>
                                )}
                                {!playerLoading && playerResults.length > 0 &&
                                    playerResults.slice(0, 8).map((name) => (
                                        <button
                                            type="button"
                                            key={name}
                                            className="w-full text-left px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground"
                                            onMouseDown={(e) => e.preventDefault()}
                                            onClick={() => {
                                                setPlayerName(name);
                                                setPlayerQuery(name);
                                                setPlayerOpen(false);
                                            }}
                                        >
                                            {name}
                                        </button>
                                    ))
                                }
                                {!playerLoading && playerResults.length === 0 && (
                                    <div className="px-3 py-2 text-sm text-muted-foreground">No matches</div>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label className="text-xs uppercase tracking-wider font-semibold text-primary">
                            stat
                        </Label>
                        <Select value={stat} onValueChange={setStat}>
                            <SelectTrigger className="h-12 bg-input border-border rounded-xl">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-popover border-border rounded-xl">
                                {STAT_OPTIONS.map((s) => (
                                    <SelectItem key={s.value} value={s.value} className="text-sm py-2.5">
                                        {s.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <Label className="text-xs uppercase tracking-wider font-semibold text-primary">
                            date_from
                        </Label>
                        <Input
                            type="date"
                            value={dateFrom}
                            onChange={(e) => setDateFrom(e.target.value)}
                            className="h-12 bg-input border-border rounded-xl"
                        />
                    </div>

                    <div className="space-y-2">
                        <Label className="text-xs uppercase tracking-wider font-semibold text-primary">
                            date_to
                        </Label>
                        <Input
                            type="date"
                            value={dateTo}
                            onChange={(e) => setDateTo(e.target.value)}
                            className="h-12 bg-input border-border rounded-xl"
                        />
                    </div>
                </div>

                {error && (
                    <p className="text-sm text-red-400">{error}</p>
                )}

                <Button
                    size="lg"
                    className="w-full h-12 font-semibold rounded-xl"
                    onClick={handleRun}
                    disabled={loading || !playerName.trim()}
                >
                    {loading ? 'Running Backtest...' : 'Run Backtest'}
                    <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
            </div>

            {result && (
                <div className="space-y-6">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <StatCard label="Total Bets" value={agg.total_bets} />
                        <StatCard label="Win Rate" value={`${(agg.accuracy * 100).toFixed(1)}%`} />
                        <StatCard
                            label="P&L (units)"
                            value={`${finalPnl >= 0 ? '+' : ''}${finalPnl.toFixed(2)}`}
                            highlight={finalPnl >= 0 ? 'green' : 'red'}
                        />
                        <StatCard
                            label="ROI"
                            value={`${agg.roi >= 0 ? '+' : ''}${agg.roi.toFixed(1)}%`}
                            highlight={agg.roi >= 0 ? 'green' : 'red'}
                        />
                    </div>

                    {chartData.length > 0 && (
                        <div className="bg-card border border-border rounded-2xl p-5">
                            <p className="text-xs uppercase tracking-wider font-semibold text-muted-foreground mb-4">
                                Cumulative P&L
                            </p>
                            <ResponsiveContainer width="100%" height={220}>
                                <LineChart data={chartData} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                                    <XAxis
                                        dataKey="date"
                                        tick={{ fontSize: 10, fill: '#888' }}
                                        tickFormatter={(v) => v.slice(5)}
                                        interval="preserveStartEnd"
                                    />
                                    <YAxis tick={{ fontSize: 10, fill: '#888' }} />
                                    <Tooltip
                                        contentStyle={{
                                            background: 'hsl(var(--card))',
                                            border: '1px solid hsl(var(--border))',
                                            borderRadius: '8px',
                                            fontSize: 12,
                                        }}
                                        formatter={(v) => [`${v >= 0 ? '+' : ''}${v}u`, 'P&L']}
                                        labelFormatter={(l) => `Date: ${l}`}
                                    />
                                    <ReferenceLine y={0} stroke="#555" strokeDasharray="4 2" />
                                    <Line
                                        type="monotone"
                                        dataKey="pnl"
                                        stroke={chartColor}
                                        dot={false}
                                        strokeWidth={2}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    )}

                    {perGame.length > 0 && (
                        <div className="bg-card border border-border rounded-2xl overflow-hidden">
                            <div className="px-5 py-3 border-b border-border">
                                <p className="text-xs uppercase tracking-wider font-semibold text-muted-foreground">
                                    Game-by-Game Results
                                </p>
                            </div>
                            <div className="overflow-y-auto max-h-96">
                                <table className="w-full text-sm">
                                    <thead className="sticky top-0 bg-card border-b border-border">
                                        <tr>
                                            {['Date', 'Opp', 'Actual', 'Line', 'Proj', '', 'P&L'].map((h) => (
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
                                        {perGame.map((g, i) => (
                                            <tr
                                                key={i}
                                                className="border-b border-border/50 hover:bg-accent/30 transition-colors"
                                            >
                                                <td className="px-4 py-2.5 text-muted-foreground">{g.date}</td>
                                                <td className="px-4 py-2.5">{g.opponent}</td>
                                                <td className="px-4 py-2.5 font-medium">{g.actual}</td>
                                                <td className="px-4 py-2.5 text-muted-foreground">{Number(g.line).toFixed(1)}</td>
                                                <td className="px-4 py-2.5 text-muted-foreground">
                                                    {g.projection != null ? Number(g.projection).toFixed(1) : '—'}
                                                </td>
                                                <td className="px-4 py-2.5">
                                                    {g.correct ? (
                                                        <span className="text-green-400 font-bold">✓</span>
                                                    ) : (
                                                        <span className="text-red-400 font-bold">✗</span>
                                                    )}
                                                </td>
                                                <td
                                                    className={`px-4 py-2.5 font-semibold ${
                                                        g.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                                                    }`}
                                                >
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

export default Backtest;
