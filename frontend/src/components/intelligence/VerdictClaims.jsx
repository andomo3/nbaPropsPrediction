import React from 'react';
import { ClaimRow } from '../terminal/ui';
import { fmt, pct } from '../../utils/format';

/** p=0.081, or <0.001 once it stops being worth printing. */
function p(value) {
    if (value == null) return '—';
    return value < 0.001 ? 'p<0.001' : `p=${Number(value).toFixed(3)}`;
}

/**
 * The verdict, as three labelled claims rather than one paragraph.
 *
 * Same information, but each test gets its own hairline row so the reader can
 * take the headline in three seconds and stop, or read across. Every sentence
 * is composed from the structured test output — never parsed back out of the
 * prose the API also returns.
 */
export default function VerdictClaims({ validation, className = '' }) {
    if (!validation) return null;

    const hit = validation.hit_rate ?? {};
    const corr = validation.edge_correlation ?? {};
    const cal = validation.calibration ?? {};

    return (
        <div className={`flex flex-col max-w-measure-claim ${className}`}>
            <ClaimRow label="Hit rate">
                {hit.value != null ? (
                    <>
                        {pct(hit.value)} over {hit.n} games is{' '}
                        <strong className="font-medium text-ink-2">
                            {hit.significant ? 'significantly above' : 'not significantly above'}
                        </strong>{' '}
                        break-even ({p(hit.p_value)}) —{' '}
                        {hit.significant ? 'unlikely to be chance.' : 'it could be noise.'}
                    </>
                ) : (
                    'Not enough graded games to test the hit rate.'
                )}
            </ClaimRow>

            <ClaimRow label="Edge">
                {corr.rho == null ? (
                    'Not enough graded games to test whether a bigger projected edge converts.'
                ) : corr.rho >= 0 ? (
                    <>
                        Larger edges were associated with{' '}
                        <strong className="font-medium text-ink-2">more hits</strong>{' '}
                        (Spearman ρ={fmt(corr.rho, 2)}, {p(corr.p_value)}) — a correlation, not
                        proof of profitability.
                    </>
                ) : (
                    <>
                        Larger edges were associated with{' '}
                        <strong className="font-medium text-ink-2">fewer hits</strong>{' '}
                        (Spearman ρ={fmt(corr.rho, 2)}, {p(corr.p_value)}) — the projected edge is
                        not pointing the right way.
                    </>
                )}
            </ClaimRow>

            <ClaimRow label="Bias" last>
                {cal.mean_error == null ? (
                    'Not enough graded games to test for projection bias.'
                ) : cal.significant ? (
                    <>
                        The model{' '}
                        <strong className="font-medium text-ink-2">
                            systematically {cal.direction}
                        </strong>{' '}
                        (mean error {cal.mean_error >= 0 ? '+' : '−'}
                        {fmt(Math.abs(cal.mean_error), 2)}, {p(cal.p_value)}).
                    </>
                ) : (
                    <>
                        No systematic projection bias detected (mean error{' '}
                        {cal.mean_error >= 0 ? '+' : '−'}
                        {fmt(Math.abs(cal.mean_error), 2)}, {p(cal.p_value)}).
                    </>
                )}
            </ClaimRow>
        </div>
    );
}
