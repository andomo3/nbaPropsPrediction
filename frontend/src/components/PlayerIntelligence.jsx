import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
    BarChart, Bar,
    XAxis, YAxis, CartesianGrid, Tooltip,
    ReferenceLine, ResponsiveContainer,
    RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
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

const C = {
    green:  '#22c55e',
    red:    '#ef4444',
    amber:  '#f59e0b',
    indigo: '#6366f1',
    slate:  '#94a3b8',
};

const BREAK_EVEN = 0.524;

function Skeleton() {
    return <div className="animate-pulse bg-border rounded-xl h-48" />;
}

function SectionCard({ title, children }) {
    return (
        <div className="bg-card border border-border rounded-2xl p-6 mb-4">
            {title && <h3 className="text-base font-semibold text-foreground mb-4">{title}</h3>}
            {children}
        </div>
    );
}

function InsightText({ text }) {
    if (!text) return null;
    return (
        <p
            className="text-sm text-muted-foreground mt-4 leading-relaxed"
            dangerouslySetInnerHTML={{
                __html: text.replace(/\*\*(.*?)\*\*/g, '<strong class="text-foreground">$1</strong>'),
            }}
        />
    );
}

function pct(v) {
    return v == null ? '—' : `${(v * 100).toFixed(1)}%`;
}

function fmt(v, d = 1) {
    return v == null ? '—' : Number(v).toFixed(d);
}

function hitColor(hr) {
    return hr >= BREAK_EVEN ? C.green : C.red;
}

function roiColor(roi) {
    return roi >= 0 ? C.green : C.red;
}

// ── Section 1: Edge Calibration ───────────────────────────────────────────────

function EdgeBandTooltip({ active, payload }) {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
        <div className="bg-popover border border-border rounded-xl px-3 py-2 text-xs shadow-lg">
            <p className="font-semibold text-foreground mb-1">Bucket: {d.bucket}</p>
            <p className="text-muted-foreground">Hit rate: <b style={{ color: hitColor(d.hit_rate) }}>{pct(d.hit_rate)}</b></p>
            <p className="text-muted-foreground">Avg edge: <b className="text-foreground">{fmt(d.avg_edge)}</b></p>
            <p className="text-muted-foreground">ROI: <b style={{ color: roiColor(d.roi) }}>{fmt(d.roi, 1)}%</b></p>
            <p className="text-muted-foreground">N: <b className="text-foreground">{d.n}</b></p>
        </div>
    );
}

function EdgeCalibration({ data, loading, error }) {
    if (loading) return <SectionCard title="Edge Calibration"><Skeleton /></SectionCard>;
    if (error) return <SectionCard title="Edge Calibration"><p className="text-sm text-red-400">{error}</p></SectionCard>;
    if (!data) return null;

    const { edge_bands = [], rest_analysis = [], form_analysis = [], cross_tab = [], best_threshold, insight } = data;

    const bandData = edge_bands.map(b => ({
        ...b,
        fill: b.hit_rate >= BREAK_EVEN ? C.green : C.red,
    }));

    return (
        <SectionCard title="Edge Calibration">
            {best_threshold && (
                <div className="border border-green-500 bg-green-500/10 rounded-xl px-4 py-3 mb-4 text-sm text-foreground">
                    Edge ≥ <strong>{fmt(best_threshold.threshold)}</strong> pts →{' '}
                    <strong style={{ color: C.green }}>{pct(best_threshold.hit_rate)}</strong> hit rate ·{' '}
                    <strong>{best_threshold.n}</strong> games ·{' '}
                    <strong style={{ color: roiColor(best_threshold.roi) }}>{fmt(best_threshold.roi, 1)}%</strong> ROI
                </div>
            )}

            {bandData.length > 0 && (
                <div className="mb-6">
                    <p className="text-xs text-muted-foreground mb-2">Edge bands — hit rate by projected edge bucket</p>
                    <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={bandData} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: C.slate }} />
                            <YAxis tickFormatter={v => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} tick={{ fontSize: 11, fill: C.slate }} />
                            <Tooltip content={<EdgeBandTooltip />} />
                            <ReferenceLine y={BREAK_EVEN} stroke={C.amber} strokeDasharray="4 2" label={{ value: '52.4%', fill: C.amber, fontSize: 10, position: 'right' }} />
                            <Bar dataKey="hit_rate" radius={[4, 4, 0, 0]}>
                                {bandData.map((entry, i) => (
                                    <rect key={i} fill={entry.fill} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                    <p className="text-[10px] text-muted-foreground mt-1">52.4% = betting break-even at -110 odds</p>
                </div>
            )}

            <div className="grid grid-cols-2 gap-4 mb-4">
                {rest_analysis.length > 0 && (
                    <div>
                        <p className="text-xs font-semibold text-muted-foreground mb-2">Rest splits</p>
                        <div className="space-y-1">
                            {rest_analysis.map((r, i) => (
                                <div key={i} className="flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-background/60">
                                    <span className="text-foreground">{r.label}</span>
                                    <span className="text-muted-foreground mr-2">n={r.n}</span>
                                    <span style={{ color: hitColor(r.hit_rate) }}>{pct(r.hit_rate)}</span>
                                    <span className="ml-2" style={{ color: roiColor(r.roi) }}>{fmt(r.roi, 1)}%</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {form_analysis.length > 0 && (
                    <div>
                        <p className="text-xs font-semibold text-muted-foreground mb-2">Form splits</p>
                        <div className="space-y-1">
                            {form_analysis.map((r, i) => (
                                <div key={i} className="flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-background/60">
                                    <span className="text-foreground">{r.label}</span>
                                    <span className="text-muted-foreground mr-2">n={r.n}</span>
                                    <span style={{ color: hitColor(r.hit_rate) }}>{pct(r.hit_rate)}</span>
                                    <span className="ml-2" style={{ color: roiColor(r.roi) }}>{fmt(r.roi, 1)}%</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {cross_tab.length > 0 && (
                <div className="mb-2">
                    <p className="text-xs font-semibold text-muted-foreground mb-2">Cross-tab</p>
                    <div className="space-y-1">
                        {cross_tab.map((r, i) => (
                            <div key={i} className="flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-background/60">
                                <span className="text-foreground">{r.label}</span>
                                <span className="text-muted-foreground mr-2">n={r.n}</span>
                                <span style={{ color: hitColor(r.hit_rate) }}>{pct(r.hit_rate)}</span>
                                <span className="ml-2" style={{ color: roiColor(r.roi) }}>{fmt(r.roi, 1)}%</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <InsightText text={insight} />
        </SectionCard>
    );
}

// ── Section 2: Floor / Ceiling Profile ───────────────────────────────────────

function FloorCeiling({ data, loading, error }) {
    if (loading) return <SectionCard title="Floor / Ceiling Profile"><Skeleton /></SectionCard>;
    if (error) return <SectionCard title="Floor / Ceiling Profile"><p className="text-sm text-red-400">{error}</p></SectionCard>;
    if (!data) return null;

    const {
        percentiles = {},
        floor, ceiling, mean, std, boom_bust, archetype,
        histogram = [],
        condition_splits = [],
        roster_comparison = [],
        insight,
    } = data;

    const p25 = percentiles.p25;
    const p75 = percentiles.p75;

    const histData = histogram.map(b => {
        const mid = ((b.bin_lo + b.bin_hi) / 2).toFixed(1);
        let fill = C.amber;
        if (b.bin_hi <= p25) fill = C.red;
        else if (b.bin_lo >= p75) fill = C.green;
        return { ...b, mid, fill };
    });

    const archetypeColor = archetype === 'Consistent' ? C.green : archetype === 'Steady' ? C.amber : C.red;

    const rosterData = roster_comparison.map(r => ({
        ...r,
        fill: r.archetype === 'Consistent' ? C.green : r.archetype === 'Steady' ? C.amber : C.red,
    }));

    return (
        <SectionCard title="Floor / Ceiling Profile">
            <div className="flex items-center gap-6 mb-6 flex-wrap">
                <div className="text-center">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Floor (p10)</p>
                    <p className="text-2xl font-bold text-foreground">{fmt(percentiles.p10)}</p>
                </div>
                <div className="text-center">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Median (p50)</p>
                    <p className="text-2xl font-bold text-foreground">{fmt(percentiles.p50)}</p>
                </div>
                <div className="text-center">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Ceiling (p90)</p>
                    <p className="text-2xl font-bold text-foreground">{fmt(percentiles.p90)}</p>
                </div>
                <div className="text-center">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Boom/Bust</p>
                    <p className="text-2xl font-bold text-foreground">{fmt(boom_bust, 2)}</p>
                </div>
                {archetype && (
                    <span className="px-3 py-1 rounded-full text-xs font-semibold" style={{ background: `${archetypeColor}22`, color: archetypeColor }}>
                        {archetype}
                    </span>
                )}
            </div>

            {histData.length > 0 && (
                <div className="mb-6">
                    <p className="text-xs text-muted-foreground mb-2">Distribution</p>
                    <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={histData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="mid" tick={{ fontSize: 10, fill: C.slate }} />
                            <YAxis tick={{ fontSize: 11, fill: C.slate }} />
                            <Tooltip formatter={(v) => [v, 'Count']} />
                            {p25 != null && <ReferenceLine x={p25?.toFixed(1)} stroke={C.red} strokeDasharray="4 2" label={{ value: 'p25', fill: C.red, fontSize: 10 }} />}
                            {p75 != null && <ReferenceLine x={p75?.toFixed(1)} stroke={C.green} strokeDasharray="4 2" label={{ value: 'p75', fill: C.green, fontSize: 10 }} />}
                            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                                {histData.map((entry, i) => (
                                    <rect key={i} fill={entry.fill} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}

            {condition_splits.length > 0 && (
                <div className="mb-6 overflow-x-auto">
                    <p className="text-xs font-semibold text-muted-foreground mb-2">Condition splits</p>
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="text-muted-foreground border-b border-border">
                                <th className="text-left py-1.5 pr-3">Condition</th>
                                <th className="text-right py-1.5 px-2">N</th>
                                <th className="text-right py-1.5 px-2">Floor</th>
                                <th className="text-right py-1.5 px-2">Median</th>
                                <th className="text-right py-1.5 px-2">Ceiling</th>
                                <th className="text-right py-1.5 px-2">Floor%</th>
                                <th className="text-right py-1.5 pl-2">Ceiling%</th>
                            </tr>
                        </thead>
                        <tbody>
                            {condition_splits.map((r, i) => (
                                <tr key={i} className="border-b border-border/40">
                                    <td className="py-1.5 pr-3 text-foreground">{r.label}</td>
                                    <td className="text-right px-2 text-muted-foreground">{r.n}</td>
                                    <td className="text-right px-2 text-foreground">{fmt(r.floor)}</td>
                                    <td className="text-right px-2 text-foreground">{fmt(r.median)}</td>
                                    <td className="text-right px-2 text-foreground">{fmt(r.ceiling)}</td>
                                    <td className="text-right px-2" style={{ color: r.floor_rate > 0.3 ? C.red : C.slate }}>{pct(r.floor_rate)}</td>
                                    <td className="text-right pl-2" style={{ color: r.ceiling_rate > 0.3 ? C.green : C.slate }}>{pct(r.ceiling_rate)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {rosterData.length > 0 && (
                <div className="mb-4">
                    <p className="text-xs font-semibold text-muted-foreground mb-2">Roster comparison — boom/bust ratio</p>
                    <ResponsiveContainer width="100%" height={180}>
                        <BarChart data={rosterData} margin={{ top: 8, right: 16, left: 0, bottom: 40 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="player_name" tick={{ fontSize: 9, fill: C.slate }} angle={-30} textAnchor="end" interval={0} />
                            <YAxis tick={{ fontSize: 11, fill: C.slate }} />
                            <Tooltip formatter={(v) => [Number(v).toFixed(2), 'Boom/Bust']} />
                            <Bar dataKey="boom_bust" radius={[3, 3, 0, 0]}>
                                {rosterData.map((entry, i) => (
                                    <rect key={i} fill={entry.fill} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}

            <InsightText text={insight} />
        </SectionCard>
    );
}

// ── Section 3: Opponent Exploitability ────────────────────────────────────────

function OpponentTooltip({ active, payload }) {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
        <div className="bg-popover border border-border rounded-xl px-3 py-2 text-xs shadow-lg">
            <p className="font-semibold text-foreground mb-1">{d.opponent}</p>
            <p className="text-muted-foreground">Avg actual: <b className="text-foreground">{fmt(d.avg_actual)}</b></p>
            <p className="text-muted-foreground">Delta: <b style={{ color: d.delta >= 0 ? C.green : C.red }}>{d.delta >= 0 ? '+' : ''}{fmt(d.delta)}</b></p>
            <p className="text-muted-foreground">Hit rate: <b style={{ color: hitColor(d.hit_rate) }}>{pct(d.hit_rate)}</b></p>
            <p className="text-muted-foreground">ROI: <b style={{ color: roiColor(d.roi) }}>{fmt(d.roi, 1)}%</b></p>
            <p className="text-muted-foreground">N: <b className="text-foreground">{d.n}</b></p>
        </div>
    );
}

function OpponentTable({ opponents, title }) {
    if (!opponents?.length) return null;
    return (
        <div>
            <p className="text-xs font-semibold text-muted-foreground mb-2">{title}</p>
            <div className="space-y-1">
                {opponents.slice(0, 3).map((r, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg bg-background/60">
                        <span className="font-medium text-foreground w-8">{r.opponent}</span>
                        <span className="text-muted-foreground">n={r.n}</span>
                        <span className="text-foreground ml-auto">{fmt(r.avg_actual)}</span>
                        <span style={{ color: r.delta >= 0 ? C.green : C.red }}>{r.delta >= 0 ? '+' : ''}{fmt(r.delta)}</span>
                        <span style={{ color: hitColor(r.hit_rate) }}>{pct(r.hit_rate)}</span>
                        <span style={{ color: roiColor(r.roi) }}>{fmt(r.roi, 1)}%</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

function OpponentExploitability({ data, loading, error }) {
    if (loading) return <SectionCard title="Opponent Exploitability"><Skeleton /></SectionCard>;
    if (error) return <SectionCard title="Opponent Exploitability"><p className="text-sm text-red-400">{error}</p></SectionCard>;
    if (!data) return null;

    const {
        season_avg,
        per_opponent = [],
        favorable = [],
        unfavorable = [],
        matchup_sensitivity,
        bias_by_tier = {},
        insight,
    } = data;

    const deltaData = per_opponent.map(o => ({
        ...o,
        fill: o.delta >= 0 ? C.green : C.red,
    }));

    const sensitivityColor = matchup_sensitivity < 12 ? C.green : matchup_sensitivity <= 25 ? C.amber : C.red;

    return (
        <SectionCard title="Opponent Exploitability">
            {matchup_sensitivity != null && (
                <div className="mb-4">
                    <span
                        className="inline-block px-4 py-1.5 rounded-full text-sm font-semibold"
                        style={{ background: `${sensitivityColor}22`, color: sensitivityColor }}
                    >
                        Matchup sensitivity: {matchup_sensitivity}%
                    </span>
                </div>
            )}

            {deltaData.length > 0 && (
                <div className="mb-6">
                    <p className="text-xs text-muted-foreground mb-2">Delta vs season avg by opponent</p>
                    <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={deltaData} margin={{ top: 8, right: 16, left: 0, bottom: 40 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="opponent" tick={{ fontSize: 9, fill: C.slate }} angle={-45} textAnchor="end" interval={0} />
                            <YAxis tick={{ fontSize: 11, fill: C.slate }} />
                            <Tooltip content={<OpponentTooltip />} />
                            <ReferenceLine y={0} stroke={C.slate} />
                            <Bar dataKey="delta" radius={[3, 3, 0, 0]}>
                                {deltaData.map((entry, i) => (
                                    <rect key={i} fill={entry.fill} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}

            <div className="grid grid-cols-2 gap-4 mb-4">
                <OpponentTable opponents={favorable} title="Favorable matchups" />
                <OpponentTable opponents={unfavorable} title="Unfavorable matchups" />
            </div>

            {Object.keys(bias_by_tier).length > 0 && (
                <div className="flex gap-3 flex-wrap mb-2">
                    {['favorable', 'neutral', 'unfavorable'].map(tier => {
                        const val = bias_by_tier[tier];
                        if (val == null) return null;
                        return (
                            <span key={tier} className="text-xs px-3 py-1.5 rounded-full bg-background/60 border border-border">
                                <span className="capitalize text-muted-foreground">{tier}: </span>
                                <span style={{ color: val >= 0 ? C.green : C.red }} className="font-medium">
                                    {val >= 0 ? '+' : ''}{fmt(val)} avg model error
                                </span>
                            </span>
                        );
                    })}
                </div>
            )}

            <InsightText text={insight} />
        </SectionCard>
    );
}

// ── Section 4: Behavioral Fingerprint ────────────────────────────────────────

const DIMENSION_LABELS = {
    consistency: 'Consistency',
    edge_reliability: 'Edge Reliability',
    matchup_sensitivity: 'Matchup Sensitivity',
    form_dependence: 'Form Dependence',
    rest_sensitivity: 'Rest Sensitivity',
};

const GROUP_LABELS = {
    form: 'Recent Form',
    opponent: 'Opponent',
    minutes: 'Minutes',
    shooting: 'Shooting',
    season_avg: 'Season Avg',
    context: 'Context',
};

function BehavioralFingerprint({ data, loading, error }) {
    if (loading) return <SectionCard title="Behavioral Fingerprint"><Skeleton /></SectionCard>;
    if (error) return <SectionCard title="Behavioral Fingerprint"><p className="text-sm text-red-400">{error}</p></SectionCard>;
    if (!data) return null;

    const {
        archetype,
        dimensions = {},
        dominant_shap_group,
        shap_group_importance = {},
        strengths = [],
        vulnerabilities = [],
        betting_profile,
        floor: fp_floor,
        ceiling: fp_ceiling,
        best_edge_threshold,
        top_favorable_opponent,
        top_unfavorable_opponent,
    } = data;

    const radarData = Object.entries(DIMENSION_LABELS).map(([key, label]) => ({
        dimension: label,
        value: dimensions[key] ?? 0,
    }));

    const shapEntries = Object.entries(shap_group_importance).filter(([, v]) => v > 0);

    return (
        <SectionCard title="Behavioral Fingerprint">
            {archetype && (
                <div className="mb-6">
                    <span className="inline-block px-5 py-2 rounded-full text-sm font-semibold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                        {archetype}
                    </span>
                </div>
            )}

            {radarData.length > 0 && (
                <div className="mb-6">
                    <p className="text-xs text-muted-foreground mb-2">Dimensional profile (0–100)</p>
                    <ResponsiveContainer width="100%" height={280}>
                        <RadarChart data={radarData} margin={{ top: 16, right: 40, left: 40, bottom: 16 }}>
                            <PolarGrid stroke="#1e293b" />
                            <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: C.slate }} />
                            <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9, fill: C.slate }} tickCount={5} />
                            <Radar dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3} />
                        </RadarChart>
                    </ResponsiveContainer>
                </div>
            )}

            <div className="grid grid-cols-2 gap-4 mb-6">
                {strengths.length > 0 && (
                    <div>
                        <p className="text-xs font-semibold text-muted-foreground mb-2">Strengths</p>
                        <ul className="space-y-1.5">
                            {strengths.map((s, i) => (
                                <li key={i} className="flex items-start gap-2 text-xs text-foreground">
                                    <span style={{ color: C.green }} className="mt-0.5 flex-shrink-0">✓</span>
                                    {s}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
                {vulnerabilities.length > 0 && (
                    <div>
                        <p className="text-xs font-semibold text-muted-foreground mb-2">Vulnerabilities</p>
                        <ul className="space-y-1.5">
                            {vulnerabilities.map((v, i) => (
                                <li key={i} className="flex items-start gap-2 text-xs text-foreground">
                                    <span style={{ color: C.red }} className="mt-0.5 flex-shrink-0">✗</span>
                                    {v}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>

            {betting_profile && (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 mb-6">
                    <p className="text-xs font-semibold text-amber-400 mb-1">Betting profile</p>
                    <p
                        className="text-sm text-foreground leading-relaxed"
                        dangerouslySetInnerHTML={{
                            __html: betting_profile.replace(/\*\*(.*?)\*\*/g, '<strong class="text-foreground">$1</strong>'),
                        }}
                    />
                </div>
            )}

            {shapEntries.length > 0 && (
                <div className="mb-6">
                    <p className="text-xs font-semibold text-muted-foreground mb-2">SHAP group importance</p>
                    <div className="space-y-1.5">
                        {shapEntries.sort((a, b) => b[1] - a[1]).map(([key, val]) => (
                            <div key={key} className="flex items-center gap-3 text-xs">
                                <span className="w-28 text-muted-foreground">{GROUP_LABELS[key] || key}</span>
                                <div className="flex-1 bg-border rounded-full h-2 overflow-hidden">
                                    <div
                                        className="h-full rounded-full bg-indigo-500"
                                        style={{ width: `${Math.min(val, 100)}%` }}
                                    />
                                </div>
                                <span className="w-10 text-right text-foreground">{fmt(val, 1)}%</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div className="flex gap-4 flex-wrap text-xs">
                {fp_floor != null && (
                    <div className="px-3 py-2 rounded-lg bg-background/60 border border-border">
                        <p className="text-muted-foreground">Floor</p>
                        <p className="font-semibold text-foreground">{fmt(fp_floor)}</p>
                    </div>
                )}
                {fp_ceiling != null && (
                    <div className="px-3 py-2 rounded-lg bg-background/60 border border-border">
                        <p className="text-muted-foreground">Ceiling</p>
                        <p className="font-semibold text-foreground">{fmt(fp_ceiling)}</p>
                    </div>
                )}
                {best_edge_threshold != null && (
                    <div className="px-3 py-2 rounded-lg bg-background/60 border border-border">
                        <p className="text-muted-foreground">Best edge threshold</p>
                        <p className="font-semibold text-foreground">{fmt(best_edge_threshold)}</p>
                    </div>
                )}
                {top_favorable_opponent && (
                    <div className="px-3 py-2 rounded-lg bg-green-500/10 border border-green-500/20">
                        <p className="text-muted-foreground">Best opponent</p>
                        <p className="font-semibold text-green-400">{top_favorable_opponent}</p>
                    </div>
                )}
                {top_unfavorable_opponent && (
                    <div className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20">
                        <p className="text-muted-foreground">Worst opponent</p>
                        <p className="font-semibold text-red-400">{top_unfavorable_opponent}</p>
                    </div>
                )}
            </div>
        </SectionCard>
    );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PlayerIntelligence() {
    const [searchParams, setSearchParams] = useSearchParams();

    const [player, setPlayer] = useState(searchParams.get('player_name') || PLAYERS[4]);
    const [stat, setStat] = useState(searchParams.get('stat') || 'pts');

    const [edge, setEdge] = useState({ data: null, loading: true, error: null });
    const [floorCeil, setFloorCeil] = useState({ data: null, loading: true, error: null });
    const [opponents, setOpponents] = useState({ data: null, loading: true, error: null });
    const [fingerprint, setFingerprint] = useState({ data: null, loading: true, error: null });

    useEffect(() => {
        setSearchParams({ player_name: player, stat });
    }, [player, stat]);

    useEffect(() => {
        const qs = `?player_name=${encodeURIComponent(player)}&stat=${stat}&season=2026`;

        setEdge({ data: null, loading: true, error: null });
        setFloorCeil({ data: null, loading: true, error: null });
        setOpponents({ data: null, loading: true, error: null });
        setFingerprint({ data: null, loading: true, error: null });

        fetch(`${API_BASE}/api/intelligence/edge/${qs}`)
            .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
            .then(data => setEdge({ data, loading: false, error: null }))
            .catch(err => setEdge({ data: null, loading: false, error: String(err) }));

        fetch(`${API_BASE}/api/intelligence/floor-ceiling/${qs}`)
            .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
            .then(data => setFloorCeil({ data, loading: false, error: null }))
            .catch(err => setFloorCeil({ data: null, loading: false, error: String(err) }));

        fetch(`${API_BASE}/api/intelligence/opponents/${qs}`)
            .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
            .then(data => setOpponents({ data, loading: false, error: null }))
            .catch(err => setOpponents({ data: null, loading: false, error: String(err) }));

        fetch(`${API_BASE}/api/intelligence/fingerprint/${qs}`)
            .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
            .then(data => setFingerprint({ data, loading: false, error: null }))
            .catch(err => setFingerprint({ data: null, loading: false, error: String(err) }));
    }, [player, stat]);

    return (
        <div className="min-h-screen bg-background text-foreground p-6 max-w-5xl mx-auto">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-foreground">Player Intelligence</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Conditional edge analysis · floor/ceiling profiling · opponent exploitability · behavioral fingerprint
                </p>
            </div>

            <div className="flex items-center gap-4 mb-6 flex-wrap">
                <Select value={player} onValueChange={setPlayer}>
                    <SelectTrigger className="w-56">
                        <SelectValue placeholder="Select player" />
                    </SelectTrigger>
                    <SelectContent>
                        {PLAYERS.map(p => (
                            <SelectItem key={p} value={p}>{p}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                <div className="flex gap-1">
                    {STATS.map(s => (
                        <button
                            key={s.key}
                            onClick={() => setStat(s.key)}
                            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                                stat === s.key
                                    ? 'bg-indigo-500 text-white'
                                    : 'bg-card border border-border text-muted-foreground hover:text-foreground'
                            }`}
                        >
                            {s.label}
                        </button>
                    ))}
                </div>
            </div>

            <EdgeCalibration {...edge} />
            <FloorCeiling {...floorCeil} />
            <OpponentExploitability {...opponents} />
            <BehavioralFingerprint {...fingerprint} />
        </div>
    );
}
