import React from 'react';
import { C, fmt, signed } from '../../utils/format';

function Module({ title, value, valueColor, blurb, viz, href, last = false }) {
    return (
        <a
            href={href}
            className={`px-5 sm:px-7 py-6 flex flex-col gap-2 border-b xl:border-b-0 ${
                last ? '' : 'xl:border-r'
            } border-hair group hover:bg-white/[0.02] transition-colors`}
        >
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <span className="text-[15px] font-semibold text-ink-1">{title}</span>
                <span
                    className="num text-[13px] font-medium"
                    style={{ color: valueColor || C.ink2 }}
                >
                    {value}
                </span>
            </div>
            <p className="text-[13px] leading-[1.5] text-ink-6">{blurb}</p>
            <div className="mt-1.5">{viz}</div>
        </a>
    );
}

/**
 * The four depth modules, summarised. Each tile shows the one figure that
 * decides whether the section below is worth opening.
 */
export default function ModuleRow({ floorCeiling, opponents, fingerprint, rank }) {
    /* Floor / ceiling: the p25–p75 box drawn inside the p10–p90 range. */
    const p = floorCeiling?.percentiles ?? {};
    const span = (p.p90 ?? 0) - (p.p10 ?? 0);
    const boxLeft = span > 0 ? ((p.p25 - p.p10) / span) * 100 : 0;
    const boxRight = span > 0 ? ((p.p90 - p.p75) / span) * 100 : 0;

    const favorable = opponents?.favorable ?? [];

    const dims = fingerprint?.radar?.length
        ? fingerprint.radar.map((d) => d.value)
        : Object.values(fingerprint?.dimensions ?? {});

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 border-b border-hair">
            <Module
                href="#floor-ceiling"
                title="Floor / ceiling"
                value={p.p10 != null ? `${fmt(p.p10)} – ${fmt(p.p90)}` : '—'}
                valueColor={C.acid}
                blurb="p10–p90 output range, boom/bust class and condition splits."
                viz={
                    <div className="h-1.5 rounded-full bg-track relative">
                        {span > 0 && (
                            <div
                                className="absolute inset-y-0 rounded-full bg-acid motion-grow-x"
                                style={{ left: `${boxLeft}%`, right: `${boxRight}%` }}
                            />
                        )}
                    </div>
                }
            />

            <Module
                href="#opponents"
                title="Opponent exploitability"
                value={favorable.length ? `${favorable.length} targets` : '—'}
                valueColor={favorable.length ? C.acid : C.ink8}
                blurb="Per-matchup delta against the season average, with hit rate and ROI."
                viz={
                    <div className="flex gap-1.5 flex-wrap">
                        {favorable.slice(0, 2).map((o, i) => (
                            <span
                                key={o.opponent}
                                className="num text-[11px] font-medium px-1.5 py-0.5 rounded"
                                style={
                                    i === 0
                                        ? { background: C.acid, color: 'var(--acid-ink)' }
                                        : { background: 'rgba(255,255,255,0.1)', color: C.ink3 }
                                }
                            >
                                {o.opponent} {signed(o.delta)}
                            </span>
                        ))}
                        {favorable.length === 0 && (
                            <span className="text-[11px] text-ink-8">No favourable matchups found</span>
                        )}
                    </div>
                }
            />

            <Module
                href="#fingerprint"
                title="Behavioral fingerprint"
                value={fingerprint?.archetype ?? '—'}
                valueColor={C.cautionText}
                blurb="Five-dimension profile with an archetype and a plain-English read."
                viz={
                    <div className="flex gap-1 items-end h-6">
                        {(dims.length ? dims : [0, 0, 0, 0, 0]).slice(0, 5).map((v, i) => (
                            <div
                                key={i}
                                className="w-2.5 motion-grow-y"
                                style={{
                                    height: `${Math.max(6, Math.min(100, v))}%`,
                                    background: 'rgba(200,255,77,0.7)',
                                    '--motion-delay': `${i * 45}ms`,
                                }}
                            />
                        ))}
                    </div>
                }
            />

            <Module
                href="#validation"
                last
                title="Predictability rank"
                value={rank?.rank ? `#${rank.rank} / ${rank.total}` : '—'}
                blurb="Composite of R², CV and hit-rate excess, tracked across seasons."
                viz={
                    <p className="text-[13px] text-ink-6">
                        {rank?.tier ? (
                            <>
                                Tier <strong className="font-semibold text-ink-1">{rank.tier}</strong>
                                {rank.score != null && <> · score {fmt(rank.score, 0)}</>}
                            </>
                        ) : (
                            'Not ranked this season'
                        )}
                    </p>
                }
            />
        </div>
    );
}
