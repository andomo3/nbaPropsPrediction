import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
    BarChart, Bar,
    PieChart, Pie, Cell,
    ScatterChart, Scatter,
    XAxis, YAxis, ZAxis,
    CartesianGrid, Tooltip,
    ReferenceLine, ResponsiveContainer,
    RadarChart, Radar, PolarGrid, PolarAngleAxis,
} from 'recharts';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const PLAYERS = [
    'Nikola Jokic', 'Shai Gilgeous-Alexander', 'Anthony Edwards',
    'Jayson Tatum', 'LeBron James', 'Stephen Curry',
    'Giannis Antetokounmpo', 'Luka Doncic', 'Tyrese Haliburton', 'Joel Embiid',
];

const STATS = [
    { key: 'pts', label: 'Points' },
    { key: 'reb', label: 'Rebounds' },
    { key: 'ast', label: 'Assists' },
];

// ── Palette ────────────────────────────────────────────────────────────────────
const C = {
    amber:  '#f59e0b',
    indigo: '#6366f1',
    green:  '#22c55e',
    slate:  '#94a3b8',
    red:    '#ef4444',
    sky:    '#38bdf8',
};

const TIER_COLORS = { High: C.green, Moderate: C.amber, Low: C.red };

const VARIANCE_SEGMENTS = [
    { key: 'model_r2',       label: 'Model (XGBoost)', color: C.amber  },
    { key: 'opponent_delta', label: 'Opponent Effect',  color: C.indigo },
    { key: 'residual',       label: 'Residual Noise',   color: '#334155' },
];

const GROUP_LABELS = {
    form:       'Recent Form',
    opponent:   'Opponent',
    minutes:    'Minutes',
    shooting:   'Shooting',
    season_avg: 'Season Avg',
    context:    'Context',
};

const GROUP_COLORS = {
    form: C.amber, opponent: C.indigo, minutes: C.green,
    shooting: C.sky, season_avg: '#c084fc', context: C.slate,
};

// ── Reusable section card ─────────────────────────────────────────────────────
function Card({ title, subtitle, children, className = '' }) {
    return (
        <div className={`bg-card border border-border rounded-2xl p-6 ${className}`}>
            {title && (
                <div className="mb-4">
                    <h3 className="text-sm font-semibold text-foreground">{title}</h3>
                    {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
                </div>
            )}
            {children}
        </div>
    );
}

// ── Skeleton loader ───────────────────────────────────────────────────────────
function Skeleton({ h = 'h-48' }) {
    return <div className={`${h} rounded-xl bg-border/40 animate-pulse`} />;
}

// ── Predictability score badge ────────────────────────────────────────────────
function ScoreBadge({ score, tier }) {
    const color = TIER_COLORS[tier] || C.slate;
    const pct = Math.round(score);
    const circumference = 2 * Math.PI * 36;
    const dash = (pct / 100) * circumference;

    return (
        <div className="flex flex-col items-center gap-1">
            <div className="relative w-24 h-24">
                <svg viewBox="0 0 88 88" className="w-full h-full -rotate-90">
                    <circle cx="44" cy="44" r="36" fill="none" stroke="#1e293b" strokeWidth="8" />
                    <circle
                        cx="44" cy="44" r="36" fill="none"
                        stroke={color} strokeWidth="8"
                        strokeDasharray={`${dash} ${circumference}`}
                        strokeLinecap="round"
                    />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-xl font-bold" style={{ color }}>{pct}</span>
                    <span className="text-[10px] text-muted-foreground">/100</span>
                </div>
            </div>
            <span className="text-xs font-semibold" style={{ color }}>{tier} Predictability</span>
        </div>
    );
}

// ── SHAP horizontal bar chart ─────────────────────────────────────────────────
function ShapChart({ data }) {
    const top8 = data.feature_importance.slice(0, 8).reverse();
    const chartData = top8.map(f => ({
        label:   f.label,
        value:   f.pct_contribution,
        shap:    f.mean_abs_shap,
        dir:     f.direction,
        fill:    f.direction === 'positive' ? C.amber : C.sky,
    }));

    const CustomBar = (props) => {
        const { x, y, width, height, fill } = props;
        return <rect x={x} y={y} width={width} height={height} fill={fill} rx={3} />;
    };

    const CustomTooltip = ({ active, payload }) => {
        if (!active || !payload?.length) return null;
        const d = payload[0].payload;
        return (
            <div className="bg-popover border border-border rounded-xl px-3 py-2 text-xs shadow-lg">
                <p className="font-semibold text-foreground mb-1">{d.label}</p>
                <p className="text-muted-foreground">Contribution: <b className="text-foreground">{d.value.toFixed(1)}%</b></p>
                <p className="text-muted-foreground">Mean |SHAP|: <b className="text-foreground">{d.shap.toFixed(3)}</b></p>
                <p style={{ color: d.dir === 'positive' ? C.amber : C.sky }}>
                    {d.dir === 'positive' ? '↑ increases' : '↓ decreases'} projection
                </p>
            </div>
        );
    };

    return (
        <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 36, top: 4, bottom: 4 }}>
                <XAxis type="number" domain={[0, 'auto']} tick={{ fontSize: 10, fill: 'var(--color-muted-foreground)' }} tickFormatter={v => `${v.toFixed(0)}%`} />
                <YAxis type="category" dataKey="label" width={130} tick={{ fontSize: 11, fill: 'var(--color-foreground)' }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" shape={<CustomBar />} isAnimationActive={false}>
                    {chartData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Bar>
            </BarChart>
        </ResponsiveContainer>
    );
}

// ── Variance decomposition donut ──────────────────────────────────────────────
function VarianceDonut({ components }) {
    const pieData = VARIANCE_SEGMENTS.map(s => ({
        name:  s.label,
        value: Math.round((components[s.key] || 0) * 1000) / 10,
        color: s.color,
    })).filter(d => d.value > 0);

    const CustomTooltip = ({ active, payload }) => {
        if (!active || !payload?.length) return null;
        const d = payload[0];
        return (
            <div className="bg-popover border border-border rounded-xl px-3 py-2 text-xs shadow-lg">
                <p className="font-semibold" style={{ color: d.payload.color }}>{d.name}</p>
                <p className="text-foreground">{d.value.toFixed(1)}% of variance</p>
            </div>
        );
    };

    return (
        <div>
            <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                    <Pie
                        data={pieData} dataKey="value"
                        cx="50%" cy="50%"
                        innerRadius={55} outerRadius={80}
                        paddingAngle={3}
                        isAnimationActive={false}
                    >
                        {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-1.5 mt-2">
                {pieData.map(d => (
                    <div key={d.name} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
                            <span className="text-muted-foreground">{d.name}</span>
                        </div>
                        <span className="font-semibold text-foreground">{d.value.toFixed(1)}%</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ── Group importance radar ─────────────────────────────────────────────────────
function GroupRadar({ groups }) {
    const radarData = Object.entries(groups).map(([key, val]) => ({
        subject: GROUP_LABELS[key] || key,
        value:   val,
        fullMark: 50,
    }));

    return (
        <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
                <PolarGrid stroke="rgba(255,255,255,0.08)" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: 'var(--color-muted-foreground)' }} />
                <Radar dataKey="value" stroke={C.amber} fill={C.amber} fillOpacity={0.25} isAnimationActive={false} />
                <Tooltip formatter={(v) => [`${v.toFixed(1)}%`, 'Contribution']} contentStyle={{ background: 'var(--color-popover)', border: '1px solid var(--color-border)', borderRadius: 12, fontSize: 12 }} />
            </RadarChart>
        </ResponsiveContainer>
    );
}

// ── Model comparison table ────────────────────────────────────────────────────
function ModelTable({ models }) {
    const available = models.filter(m => m.available);
    if (!available.length) return <p className="text-xs text-muted-foreground">No multi-model data available.</p>;

    const bestR2  = Math.max(...available.map(m => m.r2));
    const bestMAE = Math.min(...available.map(m => m.mae));

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-xs">
                <thead>
                    <tr className="border-b border-border">
                        {['Model', 'R²', 'MAE', 'Hit Rate', 'ROI'].map(h => (
                            <th key={h} className="pb-2 text-left font-semibold text-muted-foreground pr-3">{h}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {available.map(m => (
                        <tr key={m.model} className="border-b border-border/40">
                            <td className="py-2 pr-3 font-medium text-foreground">{m.label}</td>
                            <td className={`py-2 pr-3 font-semibold ${m.r2 === bestR2 ? 'text-green-400' : 'text-muted-foreground'}`}>
                                {m.r2.toFixed(3)}
                            </td>
                            <td className={`py-2 pr-3 font-semibold ${m.mae === bestMAE ? 'text-green-400' : 'text-muted-foreground'}`}>
                                {m.mae.toFixed(2)}
                            </td>
                            <td className={`py-2 pr-3 ${m.hit_rate >= 0.5524 ? 'text-green-400' : 'text-muted-foreground'}`}>
                                {(m.hit_rate * 100).toFixed(1)}%
                            </td>
                            <td className={`py-2 ${m.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {m.roi >= 0 ? '+' : ''}{m.roi.toFixed(1)}%
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// ── Calibration scatter ───────────────────────────────────────────────────────
function CalibrationScatter({ perGame, stat }) {
    const scatterData = perGame.map(g => ({
        x: g.projection,
        y: g.actual,
        z: 1,
        opponent: g.opponent,
        date: g.date,
    }));

    const allVals = perGame.flatMap(g => [g.projection, g.actual]);
    const lo = Math.floor(Math.min(...allVals) - 1);
    const hi = Math.ceil(Math.max(...allVals) + 1);

    const CustomTooltip = ({ active, payload }) => {
        if (!active || !payload?.length) return null;
        const d = payload[0].payload;
        return (
            <div className="bg-popover border border-border rounded-xl px-3 py-2 text-xs shadow-lg">
                <p className="font-medium text-muted-foreground">{d.date} vs {d.opponent}</p>
                <p className="text-foreground">Projected: <b>{d.x.toFixed(1)}</b></p>
                <p className="text-foreground">Actual: <b>{d.y.toFixed(1)}</b></p>
                <p className={d.y >= d.x ? 'text-green-400' : 'text-red-400'}>
                    Error: {(d.y - d.x).toFixed(1)}
                </p>
            </div>
        );
    };

    return (
        <ResponsiveContainer width="100%" height={240}>
            <ScatterChart margin={{ top: 8, right: 16, bottom: 16, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis
                    type="number" dataKey="x" name="Projected"
                    domain={[lo, hi]}
                    tick={{ fontSize: 10, fill: 'var(--color-muted-foreground)' }}
                    label={{ value: `Projected ${stat}`, position: 'insideBottom', offset: -8, fontSize: 10, fill: 'var(--color-muted-foreground)' }}
                />
                <YAxis
                    type="number" dataKey="y" name="Actual"
                    domain={[lo, hi]}
                    tick={{ fontSize: 10, fill: 'var(--color-muted-foreground)' }}
                    width={28}
                    label={{ value: `Actual ${stat}`, angle: -90, position: 'insideLeft', fontSize: 10, fill: 'var(--color-muted-foreground)' }}
                />
                <ZAxis type="number" dataKey="z" range={[28, 28]} />
                <Tooltip content={<CustomTooltip />} />
                {/* Identity line y=x (perfect calibration) */}
                <ReferenceLine
                    segment={[{ x: lo, y: lo }, { x: hi, y: hi }]}
                    stroke="rgba(99,102,241,0.5)" strokeDasharray="5 3"
                    label={{ value: 'Perfect', position: 'insideTopLeft', fontSize: 9, fill: 'rgba(99,102,241,0.7)' }}
                />
                <Scatter data={scatterData} fill={C.amber} fillOpacity={0.7} isAnimationActive={false} />
            </ScatterChart>
        </ResponsiveContainer>
    );
}

// ── Distributional stats row ──────────────────────────────────────────────────
function DistStats({ dist, vc }) {
    const items = [
        { label: 'R²',        value: vc.model_r2.toFixed(3),              tip: 'Variance explained by XGBoost' },
        { label: 'CV',        value: dist.cv.toFixed(3),                   tip: 'Coefficient of variation (σ/μ)' },
        { label: 'MAD',       value: dist.mad.toFixed(2),                  tip: 'Median absolute deviation (robust spread)' },
        { label: 'Skewness',  value: dist.skewness.toFixed(3),             tip: 'Error distribution skewness' },
        { label: 'Kurtosis',  value: dist.excess_kurtosis.toFixed(3),      tip: 'Excess kurtosis (heavy tails > 0)' },
        { label: 'Normal?',   value: dist.errors_normal == null ? '—' : dist.errors_normal ? 'Yes' : 'No',
          tip: `${dist.normality_test} p=${dist.normality_p}`,
          color: dist.errors_normal ? 'text-green-400' : dist.errors_normal === false ? 'text-amber-400' : 'text-muted-foreground' },
    ];

    return (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
            {items.map(({ label, value, tip, color }) => (
                <div key={label} className="bg-background border border-border rounded-xl px-3 py-2.5" title={tip}>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{label}</p>
                    <p className={`text-sm font-bold ${color || 'text-foreground'}`}>{value}</p>
                </div>
            ))}
        </div>
    );
}

// ── Main component ─────────────────────────────────────────────────────────────
const PlayerProfile = () => {
    const [searchParams] = useSearchParams();

    const initPlayer = (() => {
        const qp = searchParams.get('player_name');
        return qp && PLAYERS.includes(qp) ? qp : PLAYERS[4];
    })();
    const initStat = (() => {
        const qs = searchParams.get('stat');
        return ['pts', 'reb', 'ast'].includes(qs) ? qs : 'pts';
    })();

    const [player, setPlayer] = useState(initPlayer);
    const [stat, setStat]     = useState(initStat);

    const [shap, setShap]             = useState(null);
    const [shapLoading, setShapLoading] = useState(true);
    const [shapError, setShapError]   = useState(null);

    const [variance, setVariance]             = useState(null);
    const [varianceLoading, setVarianceLoading] = useState(true);
    const [varianceError, setVarianceError]   = useState(null);

    useEffect(() => {
        setShap(null); setShapLoading(true); setShapError(null);
        setVariance(null); setVarianceLoading(true); setVarianceError(null);

        const params = new URLSearchParams({ player_name: player, stat });

        const fetchJson = (url) =>
            fetch(url)
                .then(res => {
                    const ct = res.headers.get('content-type') || '';
                    if (!ct.includes('application/json')) throw new Error(`HTTP ${res.status}`);
                    return res.json().then(json => ({ ok: res.ok, json }));
                })
                .then(({ ok, json }) => {
                    if (!ok) throw new Error(json.detail || 'Request failed');
                    return json;
                });

        // Variance — fast (reads from DB cache)
        fetchJson(`${API_BASE}/api/analysis/variance/?${params}`)
            .then(setVariance)
            .catch(e => setVarianceError(e.message))
            .finally(() => setVarianceLoading(false));

        // SHAP — slower (computes TreeExplainer)
        fetchJson(`${API_BASE}/api/analysis/shap/?${params}`)
            .then(setShap)
            .catch(e => setShapError(e.message))
            .finally(() => setShapLoading(false));

    }, [player, stat]);

    const statLabel = STATS.find(s => s.key === stat)?.label ?? stat;

    return (
        <div className="w-full max-w-5xl mx-auto text-left">

            {/* ── Header ──────────────────────────────────────────────────── */}
            <div className="mb-8">
                <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight">
                    Predictability Profile
                </h1>
                <p className="text-muted-foreground mt-1 text-sm">
                    Research-grade variance decomposition + SHAP feature attribution per player.
                </p>
            </div>

            {/* ── Controls ────────────────────────────────────────────────── */}
            <div className="flex flex-wrap gap-4 mb-8 items-end">
                <div className="space-y-1.5">
                    <span className="text-xs uppercase tracking-wider font-semibold text-primary block">player</span>
                    <Select value={player} onValueChange={setPlayer}>
                        <SelectTrigger className="h-10 w-56 bg-input border-border rounded-xl">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-popover border-border rounded-xl">
                            {PLAYERS.map(p => (
                                <SelectItem key={p} value={p} className="text-sm py-2.5">{p}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <div className="space-y-1.5">
                    <span className="text-xs uppercase tracking-wider font-semibold text-primary block">stat</span>
                    <div className="flex gap-1 bg-input rounded-xl p-1">
                        {STATS.map(({ key, label }) => (
                            <button key={key} type="button" onClick={() => setStat(key)}
                                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${stat === key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}>
                                {label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* ── Score + Insight ──────────────────────────────────────────── */}
            {varianceLoading && <Skeleton h="h-28" />}
            {!varianceLoading && varianceError && (
                <div className="py-8 text-center text-muted-foreground text-sm">{varianceError}</div>
            )}
            {!varianceLoading && variance && (
                <div className="bg-card border border-border rounded-2xl p-6 mb-6 flex flex-col sm:flex-row gap-6 items-start">
                    <div className="flex-shrink-0">
                        <ScoreBadge score={variance.predictability_score} tier={variance.predictability_tier} />
                        <p className="text-xs text-muted-foreground text-center mt-2">{variance.n_games} games</p>
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-xs uppercase tracking-wider font-semibold text-primary mb-2">Analysis Insight</p>
                        <p className="text-sm text-muted-foreground leading-relaxed"
                            dangerouslySetInnerHTML={{ __html: variance.insight.replace(/\*\*(.*?)\*\*/g, '<strong class="text-foreground">$1</strong>') }}
                        />
                    </div>
                </div>
            )}

            {/* ── Distributional stats ─────────────────────────────────────── */}
            {!varianceLoading && variance && (
                <div className="mb-6">
                    <DistStats dist={variance.distributional} vc={variance.variance_components} />
                </div>
            )}

            {/* ── SHAP + Variance donut ────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 mb-4">
                {/* SHAP chart */}
                <Card title="SHAP Feature Attribution" subtitle={`Mean |SHAP| contribution to ${statLabel} projection`} className="lg:col-span-3">
                    {shapLoading && <Skeleton h="h-64" />}
                    {!shapLoading && shapError && (
                        <p className="text-xs text-muted-foreground py-8 text-center">{shapError}</p>
                    )}
                    {!shapLoading && shap && (
                        <>
                            <ShapChart data={shap} />
                            <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
                                <span className="flex items-center gap-1.5">
                                    <span className="w-2.5 h-2.5 rounded-sm" style={{ background: C.amber }} />
                                    Pushes projection up
                                </span>
                                <span className="flex items-center gap-1.5">
                                    <span className="w-2.5 h-2.5 rounded-sm" style={{ background: C.sky }} />
                                    Pushes projection down
                                </span>
                            </div>
                        </>
                    )}
                </Card>

                {/* Variance decomposition */}
                <Card title="Variance Decomposition" subtitle="Fraction of total stat variance" className="lg:col-span-2">
                    {varianceLoading && <Skeleton h="h-64" />}
                    {!varianceLoading && variance && (
                        <VarianceDonut components={variance.variance_components} />
                    )}
                </Card>
            </div>

            {/* ── Group importance + Model table ────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
                {/* Group radar */}
                <Card title="Feature Group Breakdown" subtitle="SHAP contribution by feature category">
                    {shapLoading && <Skeleton h="h-52" />}
                    {!shapLoading && shap && (
                        <>
                            <GroupRadar groups={shap.group_importance} />
                            <div className="mt-3 grid grid-cols-2 gap-1.5">
                                {Object.entries(shap.group_importance).sort((a,b) => b[1]-a[1]).map(([key, val]) => (
                                    <div key={key} className="flex items-center justify-between text-xs">
                                        <div className="flex items-center gap-1.5">
                                            <span className="w-2 h-2 rounded-full" style={{ background: GROUP_COLORS[key] || C.slate }} />
                                            <span className="text-muted-foreground">{GROUP_LABELS[key] || key}</span>
                                        </div>
                                        <span className="font-semibold text-foreground">{val.toFixed(1)}%</span>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </Card>

                {/* Model comparison */}
                <Card title="Model R² Comparison" subtitle={`All 4 models on ${player}'s ${statLabel}`}>
                    {varianceLoading && <Skeleton h="h-52" />}
                    {!varianceLoading && variance && (
                        <>
                            <ModelTable models={variance.model_comparison} />
                            <p className="text-xs text-muted-foreground mt-3">
                                R² = fraction of variance explained. Green = best per column.
                                Break-even hit rate: 52.4%.
                            </p>
                        </>
                    )}
                </Card>
            </div>

            {/* ── Calibration scatter ───────────────────────────────────────── */}
            {!shapLoading && shap && shap.per_game?.length > 0 && (
                <Card
                    title="Projection Calibration"
                    subtitle="Projected vs actual — dots on the dashed line = perfect calibration"
                >
                    <CalibrationScatter perGame={shap.per_game} stat={statLabel.toLowerCase()} />
                    <p className="text-xs text-muted-foreground mt-2">
                        Scatter above the line = model under-projected. Below = over-projected.
                        Tight clustering around the diagonal indicates a well-calibrated model.
                    </p>
                </Card>
            )}
        </div>
    );
};

export default PlayerProfile;
