import React from 'react';
import DetailBand from '../terminal/DetailBand';
import { Eyebrow, Insight } from '../terminal/ui';
import { C, pct, fmt } from '../../utils/format';

function TestRow({ label, sublabel, value, color, pValue, significant, last }) {
    return (
        <div
            className={`grid grid-cols-[1fr_auto] gap-6 items-start py-3.5 ${
                last ? '' : 'border-b border-hair-row'
            }`}
        >
            <div className="min-w-0">
                <p className="text-sm text-ink-2">{label}</p>
                {sublabel && <p className="text-xs text-ink-7 mt-0.5">{sublabel}</p>}
            </div>
            <div className="text-right shrink-0">
                <p className="num text-[15px] font-medium" style={{ color }}>{value}</p>
                {pValue != null && (
                    <p className="num text-[11px] text-ink-8 mt-0.5">
                        p = {pValue < 0.001 ? '<0.001' : Number(pValue).toFixed(3)}{' '}
                        <span style={{ color: significant ? C.acid : C.ink8 }}>
                            {significant ? 'sig.' : 'n.s.'}
                        </span>
                    </p>
                )}
            </div>
        </div>
    );
}

export default function StatisticalValidation({ id, data, loading, error }) {
    const hitRate = data?.hit_rate ?? {};
    const correlation = data?.edge_correlation ?? {};
    const calibration = data?.calibration ?? {};
    const warnings = data?.sample_adequacy?.warnings ?? [];
    const disclosures = data?.disclosures ?? [];

    return (
        <DetailBand
            id={id}
            label="Statistical validation"
            subtitle="Are these results trustworthy, or plausible noise?"
            loading={loading}
            error={error}
        >
            {!data ? null : (
                <div className="flex flex-col gap-7">
                    {warnings.length > 0 && (
                        <div className="flex flex-col gap-2">
                            {warnings.map((w, i) => (
                                <p
                                    key={i}
                                    className="text-[13px] leading-[1.5] pl-3 border-l-2"
                                    style={{ borderColor: C.caution, color: C.cautionText }}
                                >
                                    {w}
                                </p>
                            ))}
                        </div>
                    )}

                    <div className="flex flex-col">
                        <TestRow
                            label="Hit rate vs break-even"
                            sublabel={`${hitRate.hits} correct of ${hitRate.n} — break-even is 52.4%`}
                            value={pct(hitRate.value)}
                            color={hitRate.significant ? C.acid : C.cautionText}
                            pValue={hitRate.p_value}
                            significant={hitRate.significant}
                        />
                        <TestRow
                            label="Edge–outcome correlation"
                            sublabel={
                                correlation.rho != null
                                    ? `Spearman ρ = ${fmt(correlation.rho, 2)} — does a bigger edge mean more hits?`
                                    : 'Insufficient data for the correlation test'
                            }
                            value={correlation.label}
                            color={
                                correlation.significant ? C.acid
                                : correlation.rho != null ? C.cautionText
                                : C.ink8
                            }
                            pValue={correlation.p_value}
                            significant={correlation.significant}
                        />
                        <TestRow
                            last
                            label="Projection bias"
                            sublabel={`Mean error ${calibration.mean_error >= 0 ? '+' : '−'}${fmt(Math.abs(calibration.mean_error))} — model ${calibration.direction}`}
                            value={calibration.label}
                            color={calibration.significant ? C.alert : C.acid}
                            pValue={calibration.p_value}
                            significant={calibration.significant}
                        />
                    </div>

                    <Insight text={data.insight} />

                    {disclosures.length > 0 && (
                        <div className="flex flex-col gap-2.5 pt-5 border-t border-hair">
                            <Eyebrow>Methodology notes &amp; limitations ({disclosures.length})</Eyebrow>
                            <ul className="flex flex-col gap-1.5">
                                {disclosures.map((d, i) => (
                                    <li key={i} className="text-[13px] leading-[1.55] text-ink-6 pl-4 relative">
                                        <span className="absolute left-0 text-ink-9">·</span>
                                        {d}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
        </DetailBand>
    );
}
