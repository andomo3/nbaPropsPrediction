import React from 'react';
import { Eyebrow, GUTTER } from './ui';

/**
 * A depth section: a hairline-separated band whose body can be collapsed.
 * The summary row keeps the same eyebrow rhythm as the rest of the screen,
 * so an expanded section never reads as a card dropped onto the page.
 */
export default function DetailBand({
    id,
    label,
    subtitle,
    defaultOpen = false,
    loading = false,
    error = null,
    children,
}) {
    return (
        <section id={id} className="border-b border-hair">
            <details open={defaultOpen} className="group">
                <summary
                    className={`${GUTTER} py-5 flex items-start justify-between gap-4 cursor-pointer select-none list-none`}
                >
                    <div className="flex flex-col gap-1.5 min-w-0">
                        <Eyebrow wide>{label}</Eyebrow>
                        {subtitle && <p className="text-sm text-ink-5">{subtitle}</p>}
                    </div>
                    <span className="text-[13px] text-ink-7 shrink-0 mt-0.5 group-open:hidden">
                        Expand →
                    </span>
                    <span className="text-[13px] text-ink-7 shrink-0 mt-0.5 hidden group-open:inline">
                        Collapse
                    </span>
                </summary>

                <div className={`${GUTTER} pb-7 border-t border-hair pt-6`}>
                    {loading && (
                        <div className="h-40 flex items-center justify-center">
                            <span className="num text-[13px] tracking-eyebrow uppercase text-ink-8 animate-pulse">
                                Loading
                            </span>
                        </div>
                    )}
                    {!loading && error && (
                        <p className="text-sm text-alert">{error}</p>
                    )}
                    {!loading && !error && children}
                </div>
            </details>
        </section>
    );
}
