import React from 'react';
import {
    RadarChart, Radar, PolarGrid, PolarAngleAxis,
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
    ResponsiveContainer, Tooltip,
} from 'recharts';
import SectionCard from '../ui/SectionCard';
import Skeleton from '../ui/Skeleton';
import InsightText from '../ui/InsightText';
import { C, fmt } from '../../utils/format';

const ARCHETYPE_COLOR = {
    'Consistent Workhorse':     C.green,
    'Model-Friendly Pick':      C.green,
    'Balanced All-Rounder':     C.indigo,
    'Momentum Rider':           C.indigo,
    'Matchup-Driven Player':    C.amber,
    'Load-Sensitive Performer': C.amber,
    'Boom/Bust Gamble':         C.red,
};

const SHAP_GROUP_LABELS = {
    form:       'Recent Form',
    opponent:   'Opponent',
    minutes:    'Minutes Load',
    shooting:   'Shooting Eff.',
    season_avg: 'Season Avg',
    context:    'Game Context',
};

const DIM_LABELS = {
    consistency:         'Consistency',
    edge_reliability:    'Edge Reliability',
    matchup_sensitivity: 'Matchup Sens.',
    form_dependence:     'Form Dep.',
    rest_sensitivity:    'Rest Sens.',
};

function StrengthChip({ label, good }) {
    const color = good ? C.green : C.red;
    return (
        <span className="px-3 py-1 rounded-full text-xs font-medium inline-block mr-2 mb-2"
            style={{ background: `${color}22`, color }}>
            {good ? '▲' : '▼'} {label}
        </span>
    );
}

export default function BehavioralFingerprint({ data, loading, error }) {
    if (loading) return <SectionCard title="Behavioral Fingerprint"><Skeleton /></SectionCard>;
    if (error)   return <SectionCard title="Behavioral Fingerprint"><p className="text-sm text-red-400">{error}</p></SectionCard>;
    if (!data)   return null;

    const {
        archetype,
        radar = [],
        dimensions = {},
        shap_group_importance = {},
        shap_available = false,
        strengths = [],
        vulnerabilities = [],
        betting_profile,
        insight,
    } = data;

    const archetypeColor = ARCHETYPE_COLOR[archetype] ?? C.slate;

    // Use backend-provided radar array; fall back to building from dimensions dict
    const radarData = radar.length > 0
        ? radar.map(d => ({ ...d, fullMark: 100 }))
        : Object.entries(DIM_LABELS).map(([key, label]) => ({
            dimension: label,
            value: dimensions[key] ?? 0,
            fullMark: 100,
          }));

    const shapEntries = Object.entries(shap_group_importance)
        .filter(([, v]) => v > 0)
        .sort((a, b) => b[1] - a[1])
        .map(([key, val]) => ({ group: SHAP_GROUP_LABELS[key] ?? key, value: val }));

    return (
        <SectionCard
            title="Behavioral Fingerprint"
            subtitle="Five-dimension player profile for bet selection"
        >
            {archetype && (
                <div className="mb-6">
                    <span className="px-4 py-1.5 rounded-full text-sm font-bold"
                        style={{ background: `${archetypeColor}22`, color: archetypeColor }}>
                        {archetype}
                    </span>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                {radarData.length > 0 && (
                    <ResponsiveContainer width="100%" height={280}>
                        <RadarChart data={radarData} margin={{ top: 8, right: 24, left: 24, bottom: 8 }}>
                            <PolarGrid stroke="#1e293b" />
                            <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 10, fill: C.slate }} />
                            <Tooltip formatter={v => [fmt(v, 0), 'Score']} />
                            <Radar
                                name="Player"
                                dataKey="value"
                                stroke={archetypeColor}
                                fill={archetypeColor}
                                fillOpacity={0.25}
                            />
                        </RadarChart>
                    </ResponsiveContainer>
                )}

                <div className="space-y-3">
                    {Object.entries(dimensions).map(([key, score]) => (
                        <div key={key}>
                            <div className="flex justify-between text-xs mb-1">
                                <span className="text-muted-foreground">{DIM_LABELS[key] ?? key}</span>
                                <span className="text-foreground font-semibold">{fmt(score, 0)}</span>
                            </div>
                            <div className="h-1.5 rounded-full bg-border overflow-hidden">
                                <div
                                    className="h-full rounded-full transition-all"
                                    style={{
                                        width: `${Math.min(score, 100)}%`,
                                        background: score >= 65 ? C.green : score >= 40 ? C.amber : C.red,
                                    }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {shapEntries.length > 0 && (
                <div className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                        <p className="text-xs font-semibold text-muted-foreground">XGBoost feature group importance (SHAP)</p>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium"
                            style={{ background: `${C.indigo}22`, color: C.indigo }}>
                            SHAP
                        </span>
                    </div>
                    <ResponsiveContainer width="100%" height={160}>
                        <BarChart data={shapEntries} layout="vertical" margin={{ top: 0, right: 40, left: 80, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                            <XAxis type="number" tickFormatter={v => `${v.toFixed(0)}%`} tick={{ fontSize: 10, fill: C.slate }} domain={[0, 100]} />
                            <YAxis type="category" dataKey="group" tick={{ fontSize: 10, fill: C.slate }} width={80} />
                            <Tooltip formatter={v => [`${Number(v).toFixed(1)}%`, 'Contribution']} />
                            <Bar dataKey="value" fill={C.indigo} radius={[0, 3, 3, 0]} fillOpacity={0.8} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}

            {!shap_available && (
                <p className="text-[10px] text-muted-foreground mb-4">
                    SHAP attribution unavailable — dimension scores are heuristic-based.
                </p>
            )}

            {(strengths.length > 0 || vulnerabilities.length > 0) && (
                <div className="mb-4">
                    {strengths.length > 0 && (
                        <div className="mb-3">
                            <p className="text-xs font-semibold text-muted-foreground mb-2">Strengths</p>
                            <div>{strengths.map((s, i) => <StrengthChip key={i} label={s} good />)}</div>
                        </div>
                    )}
                    {vulnerabilities.length > 0 && (
                        <div>
                            <p className="text-xs font-semibold text-muted-foreground mb-2">Vulnerabilities</p>
                            <div>{vulnerabilities.map((v, i) => <StrengthChip key={i} label={v} good={false} />)}</div>
                        </div>
                    )}
                </div>
            )}

            {betting_profile && (
                <div className="bg-background/60 border border-border rounded-xl px-4 py-3 mb-4 text-sm text-foreground">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">Betting profile</p>
                    <p dangerouslySetInnerHTML={{
                        __html: betting_profile.replace(/\*\*(.*?)\*\*/g, '<strong class="text-foreground">$1</strong>'),
                    }} />
                </div>
            )}

            <InsightText text={insight} />
        </SectionCard>
    );
}
