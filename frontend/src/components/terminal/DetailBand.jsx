import React, { useState } from 'react';
import { Eyebrow, GUTTER } from './ui';

/**
 * A depth section: a hairline-separated band whose body can be collapsed.
 * The summary row keeps the same eyebrow rhythm as the rest of the screen,
 * so an expanded section never reads as a card dropped onto the page.
 *
 * Open/close is controlled rather than a native <details> so the body can
 * animate its height. The grid-row trick does that without measuring.
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
    const [open, setOpen] = useState(defaultOpen);

    return (
        <section id={id} className="border-b border-hair">
            <button
                type="button"
                onClick={() => setOpen((o) => !o)}
                aria-expanded={open}
                aria-controls={id ? `${id}-body` : undefined}
                className={`${GUTTER} w-full py-5 flex items-start justify-between gap-4 text-left`}
            >
                <div className="flex flex-col gap-1.5 min-w-0">
                    <Eyebrow wide>{label}</Eyebrow>
                    {subtitle && <p className="text-sm text-ink-5">{subtitle}</p>}
                </div>
                <span className="flex items-center gap-2 shrink-0 mt-0.5 text-[13px] text-ink-7">
                    {open ? 'Collapse' : 'Expand'}
                    <span
                        aria-hidden="true"
                        className="inline-block transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
                        style={{ transform: `rotate(${open ? -90 : 90}deg)` }}
                    >
                        ›
                    </span>
                </span>
            </button>

            <div id={id ? `${id}-body` : undefined} className="motion-collapse" data-open={open}>
                <div>
                    <div className={`${GUTTER} pb-7 border-t border-hair pt-6`}>
                        {loading && (
                            <div className="h-40 flex items-center justify-center">
                                <span className="num text-[13px] tracking-eyebrow uppercase text-ink-8 animate-pulse">
                                    Loading
                                </span>
                            </div>
                        )}
                        {!loading && error && <p className="text-sm text-alert">{error}</p>}
                        {!loading && !error && children}
                    </div>
                </div>
            </div>
        </section>
    );
}
