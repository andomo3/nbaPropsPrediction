import React from 'react';
import { TrendingDown, TrendingUp } from 'lucide-react';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    CartesianGrid,
    BarChart,
    Bar,
} from 'recharts';

const PredictionResults = ({ result }) => {
    if (!result) {
        return null;
    }

    const confidence = Math.round((result.probability ?? 0) * 100);
    const historicalGames = result.historicalGames || [];
    const h2hStats = result.h2hStats || { gamesPlayed: 0, average: 0, hitRate: 0 };
    const distribution = result.distribution || [];
    const factors = result.factors || [];
    const isOver = result.prediction === 'OVER';

    return (
        <section className="space-y-8">
            <div className="rounded-3xl border border-border bg-card p-8 md:p-10 lg:p-12">
                <div className="mb-8">
                    <h2 className="text-2xl md:text-3xl font-semibold text-foreground mb-2">Model Projection</h2>
                    <p className="text-base text-muted-foreground">Latest scenario output</p>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-8">
                    <div>
                        <p className="text-sm text-muted-foreground uppercase tracking-wider mb-2">Projection</p>
                        <p className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground font-mono">
                            {result.projection != null ? Number(result.projection).toFixed(1) : '--'}
                        </p>
                        <p className="text-base text-muted-foreground">
                            {result.player || 'Unknown Player'}  {(result.stat || '').toUpperCase()} line {result.line}
                        </p>
                    </div>
                    <div className={
                        `inline-flex items-center gap-2.5 px-5 py-2.5 rounded-xl text-base font-semibold ` +
                        (isOver
                            ? 'bg-primary/10 border border-primary/20 text-primary'
                            : 'bg-destructive/10 border border-destructive/20 text-destructive')
                    }>
                        {isOver ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
                        {result.prediction}
                    </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6 mt-8">
                    <div className="rounded-2xl bg-secondary/50 border border-border p-5 md:p-6">
                        <p className="text-sm text-muted-foreground uppercase tracking-wider mb-1">Confidence</p>
                        <p className="text-2xl md:text-3xl font-bold text-foreground font-mono">{confidence}%</p>
                    </div>
                    <div className="rounded-2xl bg-secondary/50 border border-border p-5 md:p-6">
                        <p className="text-sm text-muted-foreground uppercase tracking-wider mb-1">Over Prob.</p>
                        <p className="text-2xl md:text-3xl font-bold text-foreground font-mono">
                            {result.probability != null ? `${Math.round(result.probability * 100)}%` : '--'}
                        </p>
                    </div>
                    <div className="rounded-2xl bg-secondary/50 border border-border p-5 md:p-6">
                        <p className="text-sm text-muted-foreground uppercase tracking-wider mb-1">Under Prob.</p>
                        <p className="text-2xl md:text-3xl font-bold text-foreground font-mono">
                            {result.probability != null ? `${Math.round((1 - result.probability) * 100)}%` : '--'}
                        </p>
                    </div>
                    <div className="rounded-2xl bg-secondary/50 border border-border p-5 md:p-6">
                        <p className="text-sm text-muted-foreground uppercase tracking-wider mb-1">Edge</p>
                        <p className={`text-2xl md:text-3xl font-bold font-mono ${
                            result.edge != null
                                ? result.edge > 0 ? 'text-primary' : 'text-destructive'
                                : 'text-foreground'
                        }`}>
                            {result.edge != null
                                ? `${result.edge > 0 ? '+' : ''}${Number(result.edge).toFixed(1)}`
                                : result.prediction}
                        </p>
                    </div>
                </div>
            </div>

            <div className="grid gap-8 md:gap-10 md:grid-cols-2">
                <div className="rounded-3xl border border-border bg-card p-8 md:p-10 lg:p-12">
                    <div className="mb-8">
                        <h3 className="text-2xl md:text-3xl font-semibold text-foreground mb-2">Historical Performance</h3>
                        <p className="text-base text-muted-foreground">Last 10 games</p>
                    </div>
                    <div className="h-[280px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={historicalGames}>
                                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="game" stroke="var(--muted-foreground)" />
                                <YAxis stroke="var(--muted-foreground)" />
                                <Tooltip
                                    contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)' }}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="value"
                                    stroke="var(--chart-1)"
                                    fill="var(--chart-1)"
                                    fillOpacity={0.2}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="rounded-3xl border border-border bg-card p-8 md:p-10 lg:p-12">
                    <div className="mb-8">
                        <h3 className="text-2xl md:text-3xl font-semibold text-foreground mb-2">Distribution</h3>
                        <p className="text-base text-muted-foreground">Probability spread</p>
                    </div>
                    <div className="h-[280px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={distribution}>
                                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                                <XAxis dataKey="range" stroke="var(--muted-foreground)" />
                                <YAxis stroke="var(--muted-foreground)" />
                                <Tooltip
                                    contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)' }}
                                />
                                <Bar dataKey="probability" fill="var(--chart-2)" radius={[6, 6, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            <div className="rounded-3xl border border-border bg-card p-8 md:p-10 lg:p-12">
                <div className="mb-8">
                    <h3 className="text-2xl md:text-3xl font-semibold text-foreground mb-2">Head-to-Head Snapshot</h3>
                    <p className="text-base text-muted-foreground">Opponent performance summary</p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
                    <div className="rounded-2xl bg-secondary/50 border border-border p-5 md:p-6">
                        <p className="text-sm text-muted-foreground uppercase tracking-wider mb-1">Games</p>
                        <p className="text-2xl md:text-3xl font-bold text-foreground font-mono">{h2hStats.gamesPlayed}</p>
                    </div>
                    <div className="rounded-2xl bg-secondary/50 border border-border p-5 md:p-6">
                        <p className="text-sm text-muted-foreground uppercase tracking-wider mb-1">Average</p>
                        <p className="text-2xl md:text-3xl font-bold text-foreground font-mono">{h2hStats.average}</p>
                    </div>
                    <div className="rounded-2xl bg-secondary/50 border border-border p-5 md:p-6">
                        <p className="text-sm text-muted-foreground uppercase tracking-wider mb-1">Hit Rate</p>
                        <p className="text-2xl md:text-3xl font-bold text-foreground font-mono">{h2hStats.hitRate}%</p>
                    </div>
                    <div className="rounded-2xl bg-secondary/50 border border-border p-5 md:p-6">
                        <p className="text-sm text-muted-foreground uppercase tracking-wider mb-1">Confidence</p>
                        <p className="text-2xl md:text-3xl font-bold text-foreground font-mono">{confidence}%</p>
                    </div>
                </div>
            </div>

            <div className="rounded-3xl border border-border bg-card p-8 md:p-10 lg:p-12">
                <div className="mb-8">
                    <h3 className="text-2xl md:text-3xl font-semibold text-foreground mb-2">Key Factors</h3>
                    <p className="text-base text-muted-foreground">Why the model leans this way</p>
                </div>
                <div className="grid gap-8 md:gap-10 md:grid-cols-2">
                    {factors.map((item) => {
                        if (item.impact === 'positive') {
                            return (
                                <div key={item.factor} className="p-5 md:p-6 rounded-2xl border border-primary/20 bg-primary/5">
                                    <div className="flex items-center gap-2.5 mb-3">
                                        <TrendingUp className="h-4 w-4 text-primary" />
                                        <span className="text-base font-medium text-foreground">{item.factor}</span>
                                    </div>
                                    <p className="text-sm text-muted-foreground leading-relaxed text-left">{item.description}</p>
                                </div>
                            );
                        }
                        if (item.impact === 'negative') {
                            return (
                                <div key={item.factor} className="p-5 md:p-6 rounded-2xl border border-destructive/20 bg-destructive/5">
                                    <div className="flex items-center gap-2.5 mb-3">
                                        <TrendingDown className="h-4 w-4 text-destructive" />
                                        <span className="text-base font-medium text-foreground">{item.factor}</span>
                                    </div>
                                    <p className="text-sm text-muted-foreground leading-relaxed text-left">{item.description}</p>
                                </div>
                            );
                        }
                        return (
                            <div key={item.factor} className="p-5 md:p-6 rounded-2xl border border-border bg-secondary/30">
                                <div className="flex items-center gap-2.5 mb-3">
                                    <TrendingDown className="h-4 w-4 text-muted-foreground" />
                                    <span className="text-base font-medium text-foreground">{item.factor}</span>
                                </div>
                                <p className="text-sm text-muted-foreground leading-relaxed text-left">{item.description}</p>
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
};

export default PredictionResults;
