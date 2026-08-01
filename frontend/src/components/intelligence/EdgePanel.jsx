import React from 'react';
import { Eyebrow, GUTTER, Insight } from '../terminal/ui';
import { BREAK_EVEN, C, fmt, hitColor, pct, roiColor } from '../../utils/format';

/** Bar fill for an edge bucket — the accent is reserved for the best bucket. */
function bucketFill(hitRate, isBest) {
    if (isBest) return C.acid;
    if (hitRate == null) return 'var(--track)';
    if (hitRate < BREAK_EVEN) return 'rgba(232,119,107,0.5)';
    const lift = Math.min(1, (hitRate - BREAK_EVEN) / 0.2);
    return `rgba(200,255,77,${(0.22 + lift * 0.42).toFixed(2)})`;
}

function SplitTable({ label, rows }) {
    if (!rows?.length) return null;
    return (
        <div className="flex flex-col gap-3.5">
            <Eyebrow wide>{label}</Eyebrow>
            <div className="flex flex-col">
                {rows.map((r, i) => (
                    <div
                        key={r.label}
                        className={`grid grid-cols-[1fr_auto_76px] gap-3.5 items-baseline py-2.5 ${
                            i === rows.length - 1 ? '' : 'border-b border-hair-row'
                        }`}
                    >
                        <span className="text-sm text-ink-3 truncate">{r.label}</span>
                        <span className="num text-xs text-ink-8">n={r.n}</span>
                        <span
                            className="num text-[15px] font-medium text-right"
                            style={{ color: hitColor(r.hit_rate) }}
                        >
                            {pct(r.hit_rate)}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}

/**
 * The centrepiece of the Intelligence screen: does a bigger projected edge
 * actually convert? Bars are hit rate by edge bucket against the −110
 * break-even line, with the conditional splits alongside.
 */
export default function EdgePanel({ data, loading, error }) {
    if (loading) {
        return (
            <div className={`${GUTTER} py-24 flex items-center justify-center border-b border-hair`}>
                <span className="num text-[13px] tracking-eyebrow uppercase text-ink-8 animate-pulse">
                    Loading calibration
                </span>
            </div>
        );
    }
    if (error) {
        return (
            <div className={`${GUTTER} py-16 border-b border-hair`}>
                <p className="text-sm text-alert">{error}</p>
            </div>
        );
    }
    if (!data) return null;

    const bands = data.edge_bands ?? [];
    const rest = data.rest_analysis ?? [];
    const form = data.form_analysis ?? [];
    const crossTab = data.cross_tab ?? [];
    const best = data.best_threshold;
    const bestBucket = bands.length
        ? bands.reduce((a, b) => (b.hit_rate > a.hit_rate ? b : a))
        : null;
    const bestCombo = crossTab.length
        ? crossTab.reduce((a, b) => (b.hit_rate > a.hit_rate ? b : a))
        : null;
    const worstCombo = crossTab.length
        ? crossTab.reduce((a, b) => (b.hit_rate < a.hit_rate ? b : a))
        : null;

    return (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_1px_380px] border-b border-hair">
            {/* Calibration */}
            <div className="px-5 sm:px-9 py-7 flex flex-col min-w-0">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                    <div className="flex flex-col gap-1">
                        <h2 className="text-[18px] font-semibold tracking-[-0.01em] text-ink-1">
                            Edge calibration
                        </h2>
                        <p className="text-sm text-ink-5">
                            Does a bigger projected edge actually convert? Hit rate by edge bucket.
                        </p>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-ink-7 shrink-0">
                        <span className="flex items-center gap-2">
                            <span className="w-3.5 h-0.5 bg-acid" />
                            Hit rate
                        </span>
                        <span className="flex items-center gap-2">
                            <span className="w-3.5 border-t border-dashed border-ink-7" />
                            Break-even 52.4%
                        </span>
                    </div>
                </div>

                {bands.length === 0 ? (
                    <p className="text-sm text-ink-7 py-12">
                        Not enough graded games to bucket by edge.
                    </p>
                ) : (
                    <>
                        <div
                            className="relative mt-7 grid gap-4 sm:gap-7 items-end"
                            style={{
                                height: 260,
                                gridTemplateColumns: `repeat(${bands.length}, minmax(0,1fr))`,
                            }}
                        >
                            <div
                                className="absolute left-0 right-0 border-t border-dashed"
                                style={{ bottom: `${BREAK_EVEN * 100}%`, borderColor: 'rgba(255,255,255,0.22)' }}
                                aria-hidden="true"
                            />
                            {bands.map((b) => {
                                const isBest = bestBucket && b.bucket === bestBucket.bucket;
                                return (
                                    <div key={b.bucket} className="flex flex-col justify-end h-full gap-3">
                                        <div
                                            className="num text-lg sm:text-[22px] font-medium text-center leading-none"
                                            style={{ color: isBest ? C.acid : b.hit_rate >= BREAK_EVEN ? C.ink2 : C.ink4 }}
                                        >
                                            {pct(b.hit_rate)}
                                        </div>
                                        <div
                                            className="rounded-t"
                                            style={{
                                                height: `${Math.max(2, (b.hit_rate ?? 0) * 100)}%`,
                                                background: bucketFill(b.hit_rate, isBest),
                                            }}
                                        />
                                    </div>
                                );
                            })}
                        </div>

                        <div
                            className="grid gap-4 sm:gap-7 pt-3 mt-2.5 border-t border-hair-rule"
                            style={{ gridTemplateColumns: `repeat(${bands.length}, minmax(0,1fr))` }}
                        >
                            {bands.map((b) => (
                                <div key={b.bucket} className="flex flex-col gap-1 text-center">
                                    <span className="num text-[13px] font-medium text-ink-3">{b.bucket}</span>
                                    <span className="text-xs text-ink-8">n={b.n}</span>
                                </div>
                            ))}
                        </div>
                    </>
                )}

                {best && (
                    <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 mt-7 pt-5 border-t border-hair">
                        <Eyebrow className="shrink-0">Actionable rule</Eyebrow>
                        <p className="text-[15px] sm:text-base leading-[1.5] text-ink-2">
                            Only take lines with an edge of{' '}
                            <strong className="font-semibold" style={{ color: C.acid }}>
                                {fmt(best.threshold)}+ pts
                            </strong>{' '}
                            — {pct(best.hit_rate)} hit rate over {best.n} games,{' '}
                            <span className="num" style={{ color: roiColor(best.roi) }}>
                                {best.roi >= 0 ? '+' : '−'}{Math.abs(best.roi).toFixed(1)}%
                            </span>{' '}
                            ROI.
                        </p>
                    </div>
                )}
            </div>

            <div className="hidden xl:block bg-hair" aria-hidden="true" />

            {/* Conditional splits */}
            <aside className="px-5 sm:px-8 py-7 flex flex-col gap-7 border-t border-hair xl:border-t-0">
                <SplitTable label="Splits by rest" rows={rest} />
                <SplitTable label="Splits by form" rows={form} />
                {bestCombo && (
                    <div className="flex flex-col gap-2.5">
                        <Eyebrow wide>Best combination</Eyebrow>
                        <p className="text-[15px] leading-[1.55] text-ink-2">
                            <strong className="font-semibold text-ink-1">{bestCombo.label}</strong>:{' '}
                            {pct(bestCombo.hit_rate)} over {bestCombo.n} games,{' '}
                            <span className="num" style={{ color: roiColor(bestCombo.roi) }}>
                                {bestCombo.roi >= 0 ? '+' : '−'}{Math.abs(bestCombo.roi).toFixed(1)}%
                            </span>{' '}
                            ROI.
                            {worstCombo && worstCombo.label !== bestCombo.label && (
                                <>
                                    {' '}Avoid {worstCombo.label.toLowerCase()} — {pct(worstCombo.hit_rate)},{' '}
                                    <span className="num" style={{ color: roiColor(worstCombo.roi) }}>
                                        {worstCombo.roi >= 0 ? '+' : '−'}{Math.abs(worstCombo.roi).toFixed(1)}%
                                    </span>.
                                </>
                            )}
                        </p>
                    </div>
                )}
                <Insight text={data.insight} />
            </aside>
        </div>
    );
}
