import React from 'react';
import SectionCard from '../ui/SectionCard';
import Skeleton from '../ui/Skeleton';
import InsightText from '../ui/InsightText';
import { C, pct, fmt } from '../../utils/format';

const VERDICT_COLOR = {
    'Strong signal':       C.green,
    'Moderate signal':     C.amber,
    'Weak signal':         C.red,
    'No reliable signal':  C.red,
    'Insufficient data':   C.slate,
};

function StatRow({ label, value, sublabel, color, pValue, significant }) {
    return (
        <div className="flex items-start justify-between py-3 border-b border-border/40 last:border-0">
            <div>
                <p className="text-sm text-foreground font-medium">{label}</p>
                {sublabel && <p className="text-xs text-muted-foreground mt-0.5">{sublabel}</p>}
            </div>
            <div className="text-right ml-4 flex-shrink-0">
                <p className="text-sm font-bold" style={{ color }}>{value}</p>
                {pValue != null && (
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                        p = {pValue < 0.001 ? '<0.001' : Number(pValue).toFixed(3)}
                        {' '}
                        <span style={{ color: significant ? C.green : C.slate }}>
                            {significant ? '✓ sig.' : '✗ n.s.'}
                        </span>
                    </p>
                )}
            </div>
        </div>
    );
}

function AdequacyBadge({ adequate, warnings }) {
    if (adequate && warnings.length === 0) return null;
    return (
        <div className="mb-4 space-y-1.5">
            {warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 px-3 py-2 rounded-lg text-xs"
                    style={{ background: `${C.amber}15`, color: C.amber }}>
                    <span className="flex-shrink-0 mt-0.5">⚠</span>
                    <span>{w}</span>
                </div>
            ))}
        </div>
    );
}

export default function StatisticalValidation({ data, loading, error }) {
    if (loading) return <SectionCard title="Statistical Validation"><Skeleton /></SectionCard>;
    if (error)   return <SectionCard title="Statistical Validation"><p className="text-sm text-red-400">{error}</p></SectionCard>;
    if (!data)   return null;

    const {
        n_games,
        verdict,
        verdict_color,
        hit_rate = {},
        edge_correlation = {},
        calibration = {},
        sample_adequacy = {},
        insight,
    } = data;

    const vColor = VERDICT_COLOR[verdict] ?? C.slate;

    return (
        <SectionCard
            title="Statistical Validation"
            subtitle="Are these results trustworthy, or plausible noise?"
        >
            {/* Verdict banner */}
            <div className="flex items-center gap-4 mb-6 px-4 py-3 rounded-xl border"
                style={{ background: `${vColor}12`, borderColor: `${vColor}40` }}>
                <div className="flex-1">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">Overall verdict</p>
                    <p className="text-lg font-bold" style={{ color: vColor }}>{verdict}</p>
                </div>
                <div className="text-right">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-0.5">Sample</p>
                    <p className="text-lg font-bold text-foreground">{n_games} games</p>
                </div>
            </div>

            {/* Sample warnings */}
            <AdequacyBadge
                adequate={sample_adequacy.adequate}
                warnings={sample_adequacy.warnings ?? []}
            />

            {/* Test results */}
            <div className="mb-4">
                <StatRow
                    label="Hit rate vs break-even"
                    sublabel={`${hit_rate.hits} correct out of ${hit_rate.n} — break-even is 52.4%`}
                    value={pct(hit_rate.value)}
                    color={hit_rate.significant ? C.green : C.red}
                    pValue={hit_rate.p_value}
                    significant={hit_rate.significant}
                />
                <StatRow
                    label="Edge–outcome correlation"
                    sublabel={
                        edge_correlation.rho != null
                            ? `Spearman ρ = ${fmt(edge_correlation.rho, 2)} — does bigger edge → more hits?`
                            : 'Insufficient data for correlation test'
                    }
                    value={edge_correlation.label}
                    color={
                        edge_correlation.significant ? C.green
                        : edge_correlation.rho != null ? C.red
                        : C.slate
                    }
                    pValue={edge_correlation.p_value}
                    significant={edge_correlation.significant}
                />
                <StatRow
                    label="Projection bias"
                    sublabel={`Mean error ${calibration.mean_error >= 0 ? '+' : ''}${fmt(calibration.mean_error)} — model ${calibration.direction}`}
                    value={calibration.label}
                    color={calibration.significant ? C.red : C.green}
                    pValue={calibration.p_value}
                    significant={calibration.significant}
                />
            </div>

            {/* Legend */}
            <p className="text-[10px] text-muted-foreground mb-4">
                sig. = statistically significant at α = 0.05 · n.s. = not significant
            </p>

            <InsightText text={insight} />
        </SectionCard>
    );
}
