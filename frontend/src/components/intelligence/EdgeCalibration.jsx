import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
    Tooltip, ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts';
import SectionCard from '../ui/SectionCard';
import Skeleton from '../ui/Skeleton';
import InsightText from '../ui/InsightText';
import { C, BREAK_EVEN, pct, fmt, hitColor, roiColor } from '../../utils/format';

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

function SplitRow({ r }) {
    return (
        <div className="flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-background/60">
            <span className="text-foreground">{r.label}</span>
            <span className="text-muted-foreground mr-2">n={r.n}</span>
            <span style={{ color: hitColor(r.hit_rate) }}>{pct(r.hit_rate)}</span>
            <span className="ml-2" style={{ color: roiColor(r.roi) }}>{fmt(r.roi, 1)}%</span>
        </div>
    );
}

export default function EdgeCalibration({ data, loading, error }) {
    if (loading) return <SectionCard title="Edge Calibration"><Skeleton /></SectionCard>;
    if (error)   return <SectionCard title="Edge Calibration"><p className="text-sm text-red-400">{error}</p></SectionCard>;
    if (!data)   return null;

    const { edge_bands = [], rest_analysis = [], form_analysis = [], cross_tab = [], best_threshold, insight } = data;

    return (
        <SectionCard
            title="Edge Calibration"
            subtitle="Does a larger model edge actually translate to profit?"
        >
            {best_threshold && (
                <div className="border border-green-500 bg-green-500/10 rounded-xl px-4 py-3 mb-4 text-sm text-foreground">
                    Edge ≥ <strong>{fmt(best_threshold.threshold)}</strong> pts →{' '}
                    <strong style={{ color: C.green }}>{pct(best_threshold.hit_rate)}</strong> hit rate ·{' '}
                    <strong>{best_threshold.n}</strong> games ·{' '}
                    <strong style={{ color: roiColor(best_threshold.roi) }}>{fmt(best_threshold.roi, 1)}%</strong> ROI
                </div>
            )}

            {edge_bands.length > 0 && (
                <div className="mb-6">
                    <p className="text-xs text-muted-foreground mb-2">Hit rate by projected edge bucket</p>
                    <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={edge_bands} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: C.slate }} />
                            <YAxis tickFormatter={v => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} tick={{ fontSize: 11, fill: C.slate }} />
                            <Tooltip content={<EdgeBandTooltip />} />
                            <ReferenceLine y={BREAK_EVEN} stroke={C.amber} strokeDasharray="4 2"
                                label={{ value: '52.4%', fill: C.amber, fontSize: 10, position: 'right' }} />
                            <Bar dataKey="hit_rate" radius={[4, 4, 0, 0]}>
                                {edge_bands.map((entry, i) => (
                                    <Cell key={i} fill={entry.hit_rate >= BREAK_EVEN ? C.green : C.red} />
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
                        <div className="space-y-1">{rest_analysis.map((r, i) => <SplitRow key={i} r={r} />)}</div>
                    </div>
                )}
                {form_analysis.length > 0 && (
                    <div>
                        <p className="text-xs font-semibold text-muted-foreground mb-2">Form splits</p>
                        <div className="space-y-1">{form_analysis.map((r, i) => <SplitRow key={i} r={r} />)}</div>
                    </div>
                )}
            </div>

            {cross_tab.length > 0 && (
                <div className="mb-2">
                    <p className="text-xs font-semibold text-muted-foreground mb-2">Edge × Rest cross-tab</p>
                    <div className="space-y-1">{cross_tab.map((r, i) => <SplitRow key={i} r={r} />)}</div>
                </div>
            )}

            <InsightText text={insight} />
        </SectionCard>
    );
}
