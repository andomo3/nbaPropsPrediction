import React from 'react';

/* ─────────────────────────────────────────────────────────────────────────────
   Terminal primitives.

   Structure comes from hairlines and alignment, never from cards or shadows.
   Bands span the full width, the gutter is constant, and every figure is mono.
   ──────────────────────────────────────────────────────────────────────────── */

/*
 * Page gutter. Widens to 64px on large viewports — the Turn 3 pass found the
 * old 32px let body copy run edge to edge, which reads as cramped no matter
 * how much vertical space sits around it.
 */
export const GUTTER = 'px-5 sm:px-8 lg:px-16';

/** A full-bleed horizontal section closed by a hairline. */
export function Band({ children, className = '', padded = true, last = false }) {
    return (
        <section
            className={`${last ? '' : 'border-b border-hair'} ${padded ? `${GUTTER} py-6` : ''} ${className}`}
        >
            {children}
        </section>
    );
}

/**
 * Mono, letterspaced, uppercase label.
 *
 * `section` is the band-level label (12px / 0.2em), `wide` sits on figures
 * (11px / 0.16em), and the default is for inline labels (11px / 0.14em).
 */
export function Eyebrow({ children, className = '', wide = false, section = false, preserveCase = false }) {
    /* Labels carrying a symbol opt out of uppercasing — a lowercase phi or
       sigma is a different quantity from its capital. */
    const casing = preserveCase ? 'normal-case' : 'uppercase';
    if (section) {
        return (
            <div className={`num text-[12px] font-medium ${casing} leading-none tracking-eyebrow-section text-ink-8 ${className}`}>
                {children}
            </div>
        );
    }
    return (
        <div
            className={`num text-[11px] font-medium ${casing} text-ink-8 ${
                wide ? 'tracking-eyebrow-wide' : 'tracking-eyebrow'
            } ${className}`}
        >
            {children}
        </div>
    );
}

/**
 * Body copy with the measure capped. Running text is never allowed to set
 * its own width — `size` picks the cap: page prose, a narrow column, or a
 * link description.
 */
export function Prose({ children, size = 'default', className = '', as: Tag = 'p' }) {
    const measure = {
        default: 'max-w-measure text-[15px] sm:text-base leading-[1.65]',
        lead: 'max-w-measure text-[17px] sm:text-[19px] leading-[1.7]',
        wide: 'max-w-measure-wide text-[15px] sm:text-base leading-[1.65]',
        narrow: 'max-w-measure-narrow text-[15px] leading-[1.65]',
        link: 'max-w-measure-link text-[15px] sm:text-base leading-[1.65]',
    }[size];
    return (
        <Tag className={`${measure} text-pretty ${className}`}>{children}</Tag>
    );
}

/**
 * Page header band.
 *
 * Vertical rhythm is a fixed four-step scale — 16 / 24 / 40 / 56. Eyebrow,
 * 24 to the headline, 40 to the controls, 56 of section padding. Controls sit
 * on their own row rather than beside the title: crowded against a 44px
 * headline they read as part of it.
 */
export function PageHead({ eyebrow, title, controls }) {
    return (
        <Band className="pt-14 pb-10">
            {eyebrow && <Eyebrow section>{eyebrow}</Eyebrow>}
            <h1 className="mt-6 font-semibold tracking-headline text-ink-0 text-[32px] sm:text-[44px] leading-none text-balance">
                {title}
            </h1>
            {controls && (
                <div className="mt-10 flex flex-wrap items-center gap-2.5">{controls}</div>
            )}
        </Band>
    );
}

/** Segmented control. The selected option is the only filled element. */
export function Tabs({ options, value, onChange, ariaLabel = 'View' }) {
    return (
        <div className="flex items-center gap-1" role="tablist" aria-label={ariaLabel}>
            {options.map((o) => {
                const active = o.value === value;
                return (
                    <button
                        key={o.value}
                        type="button"
                        role="tab"
                        aria-selected={active}
                        onClick={() => onChange(o.value)}
                        className={`h-[38px] px-[18px] rounded-[8px] text-sm transition-colors duration-[130ms] ${
                            active
                                ? 'bg-acid text-acid-ink font-semibold'
                                : 'text-ink-5 font-medium hover:text-[#D9D9D6]'
                        }`}
                    >
                        {o.label}
                    </button>
                );
            })}
        </div>
    );
}

/** Thin vertical hairline used to separate control clusters. */
export function VRule({ className = '' }) {
    return <div className={`w-px h-6 bg-[var(--hair-rule)] mx-2.5 ${className}`} aria-hidden="true" />;
}

/** Bordered ghost dropdown, styled as a chip. */
export function GhostSelect({ value, onChange, options, label, className = '' }) {
    return (
        <div className={`relative ${className}`}>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                aria-label={label}
                className="appearance-none h-[38px] pl-4 pr-9 bg-transparent border border-[rgba(255,255,255,0.12)] rounded-[8px] text-sm font-medium text-ink-2 hover:border-white/20 transition-colors duration-[130ms] cursor-pointer"
            >
                {options.map((o) => (
                    <option key={o.value} value={o.value} className="bg-popover text-ink-2">
                        {o.label}
                    </option>
                ))}
            </select>
            <span
                className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-9 text-[11px]"
                aria-hidden="true"
            >
                ▾
            </span>
        </div>
    );
}

/** One figure in a KPI strip: label, big mono value, caption. */
export function Kpi({ label, value, sub, color, className = '' }) {
    return (
        <div className={`flex flex-col gap-2.5 ${className}`}>
            <Eyebrow wide>{label}</Eyebrow>
            <div
                className="num text-[30px] sm:text-[38px] font-medium leading-none"
                style={{ color: color || 'var(--ink-0)' }}
            >
                {value}
            </div>
            {sub && <div className="text-[13px] text-ink-7">{sub}</div>}
        </div>
    );
}

/**
 * Results read as a row, not a cluster: four across with a 48px gutter so no
 * two figures can be mistaken for a pair.
 */
export function KpiRow({ items, className = '' }) {
    return (
        <div className={`grid grid-cols-2 gap-x-8 gap-y-10 lg:grid-cols-4 lg:gap-x-12 ${className}`}>
            {items.map((it) => (
                <Kpi key={it.label} {...it} />
            ))}
        </div>
    );
}

/**
 * A single labelled claim. The verdict used to be one dense paragraph; three
 * of these carry the same information but can be read in three seconds.
 */
export function ClaimRow({ label, children, last = false }) {
    return (
        <div
            className={`grid grid-cols-1 sm:grid-cols-[120px_minmax(0,1fr)] gap-2 sm:gap-7 items-baseline py-[18px] border-t border-hair ${
                last ? 'border-b' : ''
            }`}
        >
            <Eyebrow>{label}</Eyebrow>
            <p className="text-[16px] sm:text-[17px] leading-[1.6] text-ink-3 text-pretty">
                {children}
            </p>
        </div>
    );
}

/**
 * Verdict + KPIs band. The verdict occupies a wider first column, separated
 * from the figures by a vertical hairline on wide viewports.
 */
export function KpiStrip({ lead, items }) {
    return (
        <Band className="py-6">
            <div className="flex flex-col gap-6 xl:flex-row xl:items-center xl:gap-0">
                {lead && (
                    <>
                        <div className="xl:flex-[1.6] xl:pr-9 min-w-0">{lead}</div>
                        <div className="hidden xl:block w-px h-16 bg-[var(--hair-rule)]" aria-hidden="true" />
                    </>
                )}
                <div
                    className={`grid grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-4 ${
                        lead ? 'xl:flex-[4] xl:pl-8' : 'w-full'
                    }`}
                >
                    {items.map((it) => (
                        <Kpi key={it.label} {...it} />
                    ))}
                </div>
            </div>
        </Band>
    );
}

/**
 * Faint footnotes that close a screen. Stacked rather than run together —
 * these are separate caveats, and a single inline row reads as one sentence.
 */
export function FootNotes({ items }) {
    return (
        <div className={`${GUTTER} pt-10 pb-8 flex flex-col gap-2.5 text-sm leading-[1.6] text-ink-9`}>
            {items.filter(Boolean).map((n, i) => (
                <span key={i}>{n}</span>
            ))}
        </div>
    );
}

/** Loading / error / empty state, sized to sit inside a band. */
export function StateBlock({ loading, error, empty, emptyHint, children }) {
    if (loading) {
        return (
            <div className={`${GUTTER} py-20 flex items-center justify-center`}>
                <span className="num text-[13px] tracking-eyebrow uppercase text-ink-8 animate-pulse">
                    Loading
                </span>
            </div>
        );
    }
    if (error) {
        return (
            <div className={`${GUTTER} py-16 flex flex-col items-center gap-2 text-center`}>
                <Eyebrow className="text-alert">Request failed</Eyebrow>
                <p className="text-sm text-ink-5 max-w-md">{error}</p>
            </div>
        );
    }
    if (empty) {
        return (
            <div className={`${GUTTER} py-16 flex flex-col items-center gap-2 text-center`}>
                <Eyebrow>No data</Eyebrow>
                <p className="text-sm text-ink-5 max-w-md">{empty}</p>
                {emptyHint && <p className="num text-xs text-ink-9">{emptyHint}</p>}
            </div>
        );
    }
    return children;
}

/** Thin progress meter used for signal strength. Draws in from the left. */
export function Meter({ value, color = 'var(--acid)', delay = 0, className = '' }) {
    const w = Math.max(0, Math.min(100, value ?? 0));
    return (
        <div className={`h-1 bg-track ${className}`}>
            <div
                className="h-full motion-grow-x"
                style={{ width: `${w}%`, background: color, '--motion-delay': `${delay}ms` }}
            />
        </div>
    );
}

/**
 * Dense table primitives. Callers pass an explicit grid template so each
 * screen keeps its own column rhythm; the row chrome stays shared.
 */
export function HeadRow({ cols, children, className = '' }) {
    return (
        <div
            style={{ gridTemplateColumns: cols }}
            className={`grid gap-4 ${GUTTER} py-2.5 border-b border-hair num text-[11px] font-medium tracking-eyebrow uppercase text-ink-8 ${className}`}
        >
            {children}
        </div>
    );
}

export function Row({ cols, children, highlight = false, className = '' }) {
    return (
        <div
            style={{ gridTemplateColumns: cols }}
            className={`grid gap-4 items-center ${GUTTER} py-3.5 border-b border-hair-soft transition-colors ${
                highlight ? 'bg-acid-wash shadow-[inset_2px_0_0_var(--acid)]' : 'hover:bg-white/[0.035]'
            } ${className}`}
        >
            {children}
        </div>
    );
}

/** A right-aligned mono figure. */
export function Num({ children, color, weight = 400, size = 15, className = '' }) {
    return (
        <span
            className={`num text-right ${className}`}
            style={{ color: color || 'var(--ink-3)', fontWeight: weight, fontSize: size }}
        >
            {children}
        </span>
    );
}

/** Player name + secondary context line, the first cell of most tables. */
export function NameCell({ name, meta, dim = false }) {
    return (
        <div className="flex flex-col gap-0.5 min-w-0">
            <span className={`text-[15px] font-medium truncate ${dim ? 'text-ink-3' : 'text-ink-1'}`}>
                {name}
            </span>
            {meta && <span className="text-xs text-ink-8 truncate">{meta}</span>}
        </div>
    );
}

/** Prose paragraph used for model-generated read-outs. */
export function Insight({ text, className = '' }) {
    if (!text) return null;
    return (
        <p
            className={`text-sm leading-[1.55] text-ink-6 ${className}`}
            dangerouslySetInnerHTML={{
                __html: text.replace(/\*\*(.*?)\*\*/g, '<strong class="text-ink-2 font-semibold">$1</strong>'),
            }}
        />
    );
}
