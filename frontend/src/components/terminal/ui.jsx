import React from 'react';

/* ─────────────────────────────────────────────────────────────────────────────
   Terminal primitives.

   Structure comes from hairlines and alignment, never from cards or shadows.
   Bands span the full width, the gutter is constant, and every figure is mono.
   ──────────────────────────────────────────────────────────────────────────── */

export const GUTTER = 'px-5 sm:px-gutter';

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

/** Mono, letterspaced, uppercase section label. */
export function Eyebrow({ children, className = '', wide = false }) {
    return (
        <div
            className={`num text-[11px] font-medium uppercase text-ink-8 ${
                wide ? 'tracking-eyebrow-wide' : 'tracking-eyebrow'
            } ${className}`}
        >
            {children}
        </div>
    );
}

/**
 * Page header band: eyebrow + title on the left, controls on the right.
 * Wraps to two rows below `md`, so the controls never crush the title.
 */
export function PageHead({ eyebrow, title, controls, size = 'lg' }) {
    return (
        <Band className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between pt-7 pb-5">
            <div className="flex flex-col gap-2 min-w-0">
                {eyebrow && <Eyebrow className="text-[12px]">{eyebrow}</Eyebrow>}
                <h1
                    className={`font-semibold tracking-tightest text-ink-0 leading-none ${
                        size === 'lg' ? 'text-[30px] sm:text-[38px]' : 'text-[26px] sm:text-[34px]'
                    }`}
                >
                    {title}
                </h1>
            </div>
            {controls && (
                <div className="flex flex-wrap items-center gap-2 shrink-0">{controls}</div>
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
                        className={`h-[34px] px-4 rounded-lg text-[13px] transition-colors ${
                            active
                                ? 'bg-acid text-acid-ink font-semibold'
                                : 'text-ink-5 font-medium hover:text-ink-2'
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
    return <div className={`w-px h-[34px] bg-hair mx-1.5 ${className}`} aria-hidden="true" />;
}

/** Bordered ghost dropdown, styled as a chip. */
export function GhostSelect({ value, onChange, options, label, className = '' }) {
    return (
        <div className={`relative ${className}`}>
            <select
                value={value}
                onChange={(e) => onChange(e.target.value)}
                aria-label={label}
                className="appearance-none h-[34px] pl-3.5 pr-8 bg-transparent border border-hair-control rounded-lg text-[13px] font-medium text-ink-3 hover:border-hair-rule transition-colors cursor-pointer"
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
        <div className={`flex flex-col gap-1.5 ${className}`}>
            <Eyebrow>{label}</Eyebrow>
            <div className="num text-[26px] sm:text-[30px] font-medium leading-none" style={{ color: color || 'var(--ink-0)' }}>
                {value}
            </div>
            {sub && <div className="text-xs text-ink-7">{sub}</div>}
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

/** Faint footnote strip that closes a screen. */
export function FootNotes({ items }) {
    return (
        <div className={`${GUTTER} py-[18px] flex flex-wrap items-center gap-x-6 gap-y-1.5 text-xs text-ink-9`}>
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

/** Thin progress meter used for signal strength. */
export function Meter({ value, color = 'var(--acid)', className = '' }) {
    const w = Math.max(0, Math.min(100, value ?? 0));
    return (
        <div className={`h-1 bg-track ${className}`}>
            <div className="h-full" style={{ width: `${w}%`, background: color }} />
        </div>
    );
}

/**
 * Inline sparkline. Values are normalised to the series' own range, so the
 * shape reads as a trend rather than an absolute level.
 */
export function Sparkline({ values, color = 'var(--ink-3)', width = 200, height = 24 }) {
    const pts = (values ?? []).filter((v) => v != null && Number.isFinite(v));
    if (pts.length < 2) {
        return (
            <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="w-full" style={{ height }} aria-hidden="true">
                <line x1="0" y1={height / 2} x2={width} y2={height / 2} stroke="var(--track)" strokeWidth="2" />
            </svg>
        );
    }
    const min = Math.min(...pts);
    const max = Math.max(...pts);
    const span = max - min || 1;
    const pad = 3;
    const d = pts
        .map((v, i) => {
            const x = (i / (pts.length - 1)) * width;
            const y = height - pad - ((v - min) / span) * (height - pad * 2);
            return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(' ');
    return (
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="w-full" style={{ height }} aria-hidden="true">
            <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
        </svg>
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
                highlight ? 'bg-acid-wash shadow-[inset_2px_0_0_var(--acid)]' : 'hover:bg-white/[0.02]'
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
