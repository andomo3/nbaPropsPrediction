import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
    Tooltip, ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts';
import SectionCard from '../ui/SectionCard';
import Skeleton from '../ui/Skeleton';
import InsightText from '../ui/InsightText';
import { C, pct, fmt } from '../../utils/format';

const ARCHETYPE_COLOR = {
    'Consistent Workhorse': C.green,
    'Reliable Contributor': C.green,
    'Steady Performer':     C.amber,
    'Volatile Scorer':      C.amber,
    'Boom/Bust Gamble':     C.red,
};

export default function FloorCeiling({ data, loading, error }) {
    if (loading) return <SectionCard title="Floor / Ceiling Profile"><Skeleton /></SectionCard>;
    if (error)   return <SectionCard title="Floor / Ceiling Profile"><p className="text-sm text-red-400">{error}</p></SectionCard>;
    if (!data)   return null;

    const {
        percentiles = {},
        boom_bust, archetype,
        histogram = [],
        condition_splits = [],
        roster_comparison = [],
        insight,
    } = data;

    const { p25, p75 } = percentiles;
    const archetypeColor = ARCHETYPE_COLOR[archetype] ?? C.slate;

    const histData = histogram.map(b => {
        const mid = ((b.bin_lo + b.bin_hi) / 2).toFixed(1);
        const fill = b.bin_hi <= p25 ? C.red : b.bin_lo >= p75 ? C.green : C.amber;
        return { ...b, mid, fill };
    });

    return (
        <SectionCard
            title="Floor / Ceiling Profile"
            subtitle="Realistic output range and boom/bust classification"
        >
            <div className="flex items-center gap-6 mb-6 flex-wrap">
                {[['Floor (p10)', percentiles.p10], ['Median (p50)', percentiles.p50], ['Ceiling (p90)', percentiles.p90], ['Boom/Bust', boom_bust]].map(([label, val]) => (
                    <div key={label} className="text-center">
                        <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
                        <p className="text-2xl font-bold text-foreground">{fmt(val, label === 'Boom/Bust' ? 2 : 1)}</p>
                    </div>
                ))}
                {archetype && (
                    <span className="px-3 py-1 rounded-full text-xs font-semibold"
                        style={{ background: `${archetypeColor}22`, color: archetypeColor }}>
                        {archetype}
                    </span>
                )}
            </div>

            {histData.length > 0 && (
                <div className="mb-6">
                    <p className="text-xs text-muted-foreground mb-2">Output distribution</p>
                    <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={histData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="mid" tick={{ fontSize: 10, fill: C.slate }} />
                            <YAxis tick={{ fontSize: 11, fill: C.slate }} />
                            <Tooltip formatter={v => [v, 'Games']} />
                            {p25 != null && <ReferenceLine x={p25?.toFixed(1)} stroke={C.red} strokeDasharray="4 2" label={{ value: 'p25', fill: C.red, fontSize: 10 }} />}
                            {p75 != null && <ReferenceLine x={p75?.toFixed(1)} stroke={C.green} strokeDasharray="4 2" label={{ value: 'p75', fill: C.green, fontSize: 10 }} />}
                            <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                                {histData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
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
                                {['Condition', 'N', 'Floor', 'Median', 'Ceiling', 'Floor%', 'Ceiling%'].map(h => (
                                    <th key={h} className={`py-1.5 ${h === 'Condition' ? 'text-left pr-3' : 'text-right px-2'}`}>{h}</th>
                                ))}
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

            {roster_comparison.length > 0 && (
                <div className="mb-4">
                    <p className="text-xs font-semibold text-muted-foreground mb-2">Roster boom/bust comparison</p>
                    <ResponsiveContainer width="100%" height={180}>
                        <BarChart data={roster_comparison} margin={{ top: 8, right: 16, left: 0, bottom: 40 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="player_name" tick={{ fontSize: 9, fill: C.slate }} angle={-30} textAnchor="end" interval={0} />
                            <YAxis tick={{ fontSize: 11, fill: C.slate }} />
                            <Tooltip formatter={v => [Number(v).toFixed(2), 'Boom/Bust']} />
                            <Bar dataKey="boom_bust" radius={[3, 3, 0, 0]}>
                                {roster_comparison.map((entry, i) => (
                                    <Cell key={i} fill={ARCHETYPE_COLOR[entry.archetype] ?? C.slate} />
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
