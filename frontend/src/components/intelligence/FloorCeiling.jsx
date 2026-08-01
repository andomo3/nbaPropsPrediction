import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
    Tooltip, ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts';
import DetailBand from '../terminal/DetailBand';
import { Eyebrow, Insight } from '../terminal/ui';
import { C, pct, fmt } from '../../utils/format';

const ARCHETYPE_COLOR = {
    'Consistent Workhorse': C.acid,
    'Reliable Contributor': C.acid,
    'Steady Performer':     C.cautionText,
    'Volatile Scorer':      C.cautionText,
    'Boom/Bust Gamble':     C.alert,
};

const axis = { fontSize: 11, fill: 'var(--ink-8)', fontFamily: 'IBM Plex Mono' };

function ChartTip({ active, payload, label, unit }) {
    if (!active || !payload?.length) return null;
    return (
        <div className="bg-popover border border-hair-control rounded-lg px-3 py-2">
            <p className="num text-[11px] tracking-eyebrow uppercase text-ink-8 mb-1">{label}</p>
            <p className="num text-sm text-ink-1">
                {payload[0].value} {unit}
            </p>
        </div>
    );
}

export default function FloorCeiling({ id, data, loading, error }) {
    const archetype = data?.archetype;
    const archetypeColor = ARCHETYPE_COLOR[archetype] ?? C.ink3;

    const percentiles = data?.percentiles ?? {};
    const { p25, p75 } = percentiles;
    const histogram = data?.histogram ?? [];
    const conditionSplits = data?.condition_splits ?? [];
    const rosterComparison = data?.roster_comparison ?? [];

    const histData = histogram.map((b) => ({
        ...b,
        mid: ((b.bin_lo + b.bin_hi) / 2).toFixed(1),
        fill: b.bin_hi <= p25 ? 'rgba(232,119,107,0.55)'
            : b.bin_lo >= p75 ? C.acid
            : 'rgba(255,255,255,0.14)',
    }));

    return (
        <DetailBand
            id={id}
            label="Floor / ceiling profile"
            subtitle="Realistic output range and boom/bust classification"
            loading={loading}
            error={error}
        >
            {!data ? null : (
                <div className="flex flex-col gap-8">
                    <div className="flex flex-wrap items-end gap-x-10 gap-y-5">
                        {[
                            ['Floor (p10)', percentiles.p10, 1],
                            ['Median (p50)', percentiles.p50, 1],
                            ['Ceiling (p90)', percentiles.p90, 1],
                            ['Boom / bust', data.boom_bust, 2],
                        ].map(([label, val, dp]) => (
                            <div key={label} className="flex flex-col gap-1.5">
                                <Eyebrow>{label}</Eyebrow>
                                <span className="num text-[26px] font-medium text-ink-0 leading-none">
                                    {fmt(val, dp)}
                                </span>
                            </div>
                        ))}
                        {archetype && (
                            <div className="flex flex-col gap-1.5">
                                <Eyebrow>Archetype</Eyebrow>
                                <span
                                    className="text-[20px] font-semibold leading-none"
                                    style={{ color: archetypeColor }}
                                >
                                    {archetype}
                                </span>
                            </div>
                        )}
                    </div>

                    {histData.length > 0 && (
                        <div className="flex flex-col gap-3">
                            <Eyebrow wide>Output distribution</Eyebrow>
                            <ResponsiveContainer width="100%" height={200}>
                                <BarChart data={histData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.05)" />
                                    <XAxis dataKey="mid" tick={axis} tickLine={false} axisLine={{ stroke: 'var(--hair-rule)' }} />
                                    <YAxis tick={axis} tickLine={false} axisLine={false} width={28} />
                                    <Tooltip content={<ChartTip unit="games" />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                                    {p25 != null && (
                                        <ReferenceLine x={p25.toFixed(1)} stroke={C.alert} strokeDasharray="4 4" />
                                    )}
                                    {p75 != null && (
                                        <ReferenceLine x={p75.toFixed(1)} stroke={C.acid} strokeDasharray="4 4" />
                                    )}
                                    <Bar dataKey="count" radius={[2, 2, 0, 0]} animationDuration={500} animationEasing="ease-out">
                                        {histData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                            <p className="text-xs text-ink-8">
                                Dashed markers are the p25 and p75 boundaries.
                            </p>
                        </div>
                    )}

                    {conditionSplits.length > 0 && (
                        <div className="flex flex-col gap-3">
                            <Eyebrow wide>Condition splits</Eyebrow>
                            <div className="table-scroll">
                                <div className="min-w-[620px]">
                                    <div className="grid grid-cols-[1.4fr_repeat(6,minmax(0,1fr))] gap-3 py-2 border-b border-hair num text-[11px] font-medium tracking-eyebrow uppercase text-ink-8">
                                        <span>Condition</span>
                                        <span className="text-right">N</span>
                                        <span className="text-right">Floor</span>
                                        <span className="text-right">Median</span>
                                        <span className="text-right">Ceiling</span>
                                        <span className="text-right">Floor %</span>
                                        <span className="text-right">Ceiling %</span>
                                    </div>
                                    {conditionSplits.map((r) => (
                                        <div
                                            key={r.label}
                                            className="grid grid-cols-[1.4fr_repeat(6,minmax(0,1fr))] gap-3 py-2.5 border-b border-hair-soft items-baseline"
                                        >
                                            <span className="text-sm text-ink-3 truncate">{r.label}</span>
                                            <span className="num text-[13px] text-ink-8 text-right">{r.n}</span>
                                            <span className="num text-[13px] text-ink-2 text-right">{fmt(r.floor)}</span>
                                            <span className="num text-[13px] text-ink-2 text-right">{fmt(r.median)}</span>
                                            <span className="num text-[13px] text-ink-2 text-right">{fmt(r.ceiling)}</span>
                                            <span
                                                className="num text-[13px] text-right"
                                                style={{ color: r.floor_rate > 0.3 ? C.alert : C.ink5 }}
                                            >
                                                {pct(r.floor_rate)}
                                            </span>
                                            <span
                                                className="num text-[13px] text-right"
                                                style={{ color: r.ceiling_rate > 0.3 ? C.acid : C.ink5 }}
                                            >
                                                {pct(r.ceiling_rate)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {rosterComparison.length > 0 && (
                        <div className="flex flex-col gap-3">
                            <Eyebrow wide>Roster boom/bust comparison</Eyebrow>
                            <ResponsiveContainer width="100%" height={200}>
                                <BarChart data={rosterComparison} margin={{ top: 8, right: 8, left: 0, bottom: 46 }}>
                                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.05)" />
                                    <XAxis
                                        dataKey="player_name"
                                        tick={{ ...axis, fontSize: 10 }}
                                        tickLine={false}
                                        axisLine={{ stroke: 'var(--hair-rule)' }}
                                        angle={-32}
                                        textAnchor="end"
                                        interval={0}
                                    />
                                    <YAxis tick={axis} tickLine={false} axisLine={false} width={32} />
                                    <Tooltip content={<ChartTip unit="boom/bust" />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                                    <Bar dataKey="boom_bust" radius={[2, 2, 0, 0]} animationDuration={500} animationEasing="ease-out">
                                        {rosterComparison.map((entry, i) => (
                                            <Cell
                                                key={i}
                                                fill={
                                                    entry.player_name === data.player_name
                                                        ? C.acid
                                                        : ARCHETYPE_COLOR[entry.archetype] ?? 'rgba(255,255,255,0.14)'
                                                }
                                            />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    )}

                    <Insight text={data.insight} />
                </div>
            )}
        </DetailBand>
    );
}
