import React from 'react';
import {
    RadarChart, Radar, PolarGrid, PolarAngleAxis,
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
    ResponsiveContainer, Tooltip,
} from 'recharts';
import DetailBand from '../terminal/DetailBand';
import { Eyebrow, Insight } from '../terminal/ui';
import { C, fmt } from '../../utils/format';

const ARCHETYPE_COLOR = {
    'Consistent Workhorse':     C.acid,
    'Model-Friendly Pick':      C.acid,
    'Balanced All-Rounder':     C.ink2,
    'Momentum Rider':           C.ink2,
    'Matchup-Driven Player':    C.cautionText,
    'Load-Sensitive Performer': C.cautionText,
    'Boom/Bust Gamble':         C.alert,
};

const SHAP_GROUP_LABELS = {
    form:       'Recent form',
    opponent:   'Opponent',
    minutes:    'Minutes load',
    shooting:   'Shooting eff.',
    season_avg: 'Season avg',
    context:    'Game context',
};

const DIM_LABELS = {
    consistency:         'Consistency',
    edge_reliability:    'Edge reliability',
    matchup_sensitivity: 'Matchup sens.',
    form_dependence:     'Form dep.',
    rest_sensitivity:    'Rest sens.',
};

const axis = { fontSize: 11, fill: 'var(--ink-8)', fontFamily: 'IBM Plex Mono' };

function Tip({ active, payload, suffix = '' }) {
    if (!active || !payload?.length) return null;
    return (
        <div className="bg-popover border border-hair-control rounded-lg px-3 py-1.5">
            <p className="num text-sm text-ink-1">
                {fmt(payload[0].value, suffix ? 1 : 0)}{suffix}
            </p>
        </div>
    );
}

function Chip({ label, good }) {
    return (
        <span
            className="text-xs px-2.5 py-1 rounded"
            style={
                good
                    ? { background: 'rgba(200,255,77,0.14)', color: C.acid }
                    : { background: 'rgba(232,119,107,0.14)', color: C.alert }
            }
        >
            {good ? '▲' : '▼'} {label}
        </span>
    );
}

export default function BehavioralFingerprint({ id, data, loading, error }) {
    const archetype = data?.archetype;
    const archetypeColor = ARCHETYPE_COLOR[archetype] ?? C.ink3;

    const radar = data?.radar ?? [];
    const dimensions = data?.dimensions ?? {};
    const strengths = data?.strengths ?? [];
    const vulnerabilities = data?.vulnerabilities ?? [];

    const radarData = radar.length > 0
        ? radar.map((d) => ({ ...d, fullMark: 100 }))
        : Object.entries(DIM_LABELS).map(([key, label]) => ({
            dimension: label,
            value: dimensions[key] ?? 0,
            fullMark: 100,
          }));

    const shapEntries = Object.entries(data?.shap_group_importance ?? {})
        .filter(([, v]) => v > 0)
        .sort((a, b) => b[1] - a[1])
        .map(([key, val]) => ({ group: SHAP_GROUP_LABELS[key] ?? key, value: val }));

    return (
        <DetailBand
            id={id}
            label="Behavioral fingerprint"
            subtitle="Five-dimension player profile for bet selection"
            loading={loading}
            error={error}
        >
            {!data ? null : (
                <div className="flex flex-col gap-8">
                    {archetype && (
                        <div className="flex flex-col gap-1.5">
                            <Eyebrow>Archetype</Eyebrow>
                            <span
                                className="text-[24px] font-semibold tracking-tightest leading-none"
                                style={{ color: archetypeColor }}
                            >
                                {archetype}
                            </span>
                        </div>
                    )}

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
                        {radarData.length > 0 && (
                            <ResponsiveContainer width="100%" height={260}>
                                <RadarChart data={radarData} margin={{ top: 8, right: 28, left: 28, bottom: 8 }}>
                                    <PolarGrid stroke="rgba(255,255,255,0.09)" />
                                    <PolarAngleAxis
                                        dataKey="dimension"
                                        tick={{ fontSize: 11, fill: 'var(--ink-7)' }}
                                    />
                                    <Tooltip content={<Tip />} />
                                    <Radar
                                        name="Player"
                                        dataKey="value"
                                        stroke={archetypeColor}
                                        fill={archetypeColor}
                                        fillOpacity={0.18}
                                    />
                                </RadarChart>
                            </ResponsiveContainer>
                        )}

                        <div className="flex flex-col">
                            {Object.entries(dimensions).map(([key, score], i, arr) => (
                                <div
                                    key={key}
                                    className={`flex flex-col gap-2 py-3 ${
                                        i === arr.length - 1 ? '' : 'border-b border-hair-row'
                                    }`}
                                >
                                    <div className="flex justify-between items-baseline">
                                        <span className="text-sm text-ink-3">{DIM_LABELS[key] ?? key}</span>
                                        <span className="num text-sm font-medium text-ink-1">
                                            {fmt(score, 0)}
                                        </span>
                                    </div>
                                    <div className="h-1 bg-track">
                                        <div
                                            className="h-full"
                                            style={{
                                                width: `${Math.min(score, 100)}%`,
                                                background: score >= 65 ? C.acid : score >= 40 ? C.caution : C.alert,
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {shapEntries.length > 0 && (
                        <div className="flex flex-col gap-3">
                            <Eyebrow wide>XGBoost feature group importance (SHAP)</Eyebrow>
                            <ResponsiveContainer width="100%" height={170}>
                                <BarChart
                                    data={shapEntries}
                                    layout="vertical"
                                    margin={{ top: 0, right: 32, left: 8, bottom: 0 }}
                                >
                                    <CartesianGrid horizontal={false} stroke="rgba(255,255,255,0.05)" />
                                    <XAxis
                                        type="number"
                                        tickFormatter={(v) => `${v.toFixed(0)}%`}
                                        tick={axis}
                                        tickLine={false}
                                        axisLine={{ stroke: 'var(--hair-rule)' }}
                                        domain={[0, 100]}
                                    />
                                    <YAxis
                                        type="category"
                                        dataKey="group"
                                        tick={{ fontSize: 12, fill: 'var(--ink-5)' }}
                                        tickLine={false}
                                        axisLine={false}
                                        width={104}
                                    />
                                    <Tooltip content={<Tip suffix="%" />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                                    <Bar dataKey="value" fill="rgba(200,255,77,0.55)" radius={[0, 2, 2, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    )}

                    {!data.shap_available && (
                        <p className="text-xs text-ink-8">
                            SHAP attribution unavailable — dimension scores are heuristic-based.
                        </p>
                    )}

                    {(strengths.length > 0 || vulnerabilities.length > 0) && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                            {strengths.length > 0 && (
                                <div className="flex flex-col gap-2.5">
                                    <Eyebrow>Strengths</Eyebrow>
                                    <div className="flex flex-wrap gap-1.5">
                                        {strengths.map((s) => <Chip key={s} label={s} good />)}
                                    </div>
                                </div>
                            )}
                            {vulnerabilities.length > 0 && (
                                <div className="flex flex-col gap-2.5">
                                    <Eyebrow>Vulnerabilities</Eyebrow>
                                    <div className="flex flex-wrap gap-1.5">
                                        {vulnerabilities.map((v) => <Chip key={v} label={v} good={false} />)}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {data.betting_profile && (
                        <div className="flex flex-col gap-2 pt-5 border-t border-hair">
                            <Eyebrow>Betting profile</Eyebrow>
                            <Insight text={data.betting_profile} className="text-[15px] text-ink-2" />
                        </div>
                    )}

                    <Insight text={data.insight} />
                </div>
            )}
        </DetailBand>
    );
}
