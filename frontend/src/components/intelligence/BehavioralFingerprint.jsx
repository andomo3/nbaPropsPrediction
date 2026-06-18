import React from 'react';
import {
    RadarChart, Radar, PolarGrid, PolarAngleAxis,
    ResponsiveContainer, Tooltip,
} from 'recharts';
import SectionCard from '../ui/SectionCard';
import Skeleton from '../ui/Skeleton';
import InsightText from '../ui/InsightText';
import { C, fmt } from '../../utils/format';

const ARCHETYPE_COLOR = {
    'Sharp Edge Hunter':      C.green,
    'Form Rider':             C.indigo,
    'Rest Sensitive':         C.amber,
    'Matchup Dependent':      C.amber,
    'Consistent All-Weather': C.green,
    'High Variance':          C.red,
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
        strengths = [],
        vulnerabilities = [],
        betting_profile,
        insight,
    } = data;

    const archetypeColor = ARCHETYPE_COLOR[archetype] ?? C.slate;

    const radarData = radar.map(d => ({ ...d, fullMark: 100 }));

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
                    <div>
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
                    </div>
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
                <div className="bg-background/60 border border-border rounded-xl px-4 py-3 mb-2 text-sm text-foreground">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">Betting profile</p>
                    {betting_profile}
                </div>
            )}

            <InsightText text={insight} />
        </SectionCard>
    );
}
