export const BREAK_EVEN = 0.524;

/**
 * Terminal signal palette. One accent (acid) for the best value in a group,
 * amber for caution, red only for genuinely negative, greys for everything
 * else. Keys are kept from the previous palette so existing callers keep
 * working; the values now point at the Terminal system.
 */
export const C = {
    acid:    '#C8FF4D',
    caution: '#E8A33D',
    cautionText: '#F4C87A',
    alert:   '#E8776B',
    ink0:    '#F7F7F5',
    ink2:    '#EDEDEA',
    ink3:    '#C7C7CC',
    ink4:    '#9A9AA2',
    ink5:    '#8C8C93',
    ink8:    '#6E6E76',

    /* Legacy aliases */
    green:  '#C8FF4D',
    red:    '#E8776B',
    amber:  '#E8A33D',
    indigo: '#C7C7CC',
    slate:  '#6E6E76',
};

/** Format a 0–1 rate as a percentage string, e.g. 0.524 → "52.4%" */
export function pct(v) {
    return v == null ? '—' : `${(v * 100).toFixed(1)}%`;
}

/** Format a number to d decimal places */
export function fmt(v, d = 1) {
    return v == null ? '—' : Number(v).toFixed(d);
}

/** Format a number with an explicit sign, e.g. 3.8 → "+3.8", -2.1 → "−2.1" */
export function signed(v, d = 1) {
    if (v == null) return '—';
    const n = Number(v);
    return `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(d)}`;
}

/** Inline colour for a hit rate vs break-even */
export function hitColor(hr) {
    if (hr == null) return C.ink8;
    if (hr >= 0.60) return C.acid;
    if (hr >= BREAK_EVEN) return C.ink2;
    return C.alert;
}

/** Inline colour for ROI — acid when clearly profitable, red when negative */
export function roiColor(roi) {
    if (roi == null) return C.ink8;
    if (roi > 0) return C.acid;
    if (roi === 0) return C.ink3;
    return C.alert;
}

/**
 * Colour for a signed delta where positive is good (edge, hit-rate excess).
 * Amber rather than red for small negatives — red is reserved for results
 * that are genuinely bad, not merely below zero.
 */
export function deltaColor(v, strong = 2) {
    if (v == null) return C.ink8;
    if (v >= strong) return C.acid;
    if (v >= 0) return C.ink3;
    if (v > -strong) return C.cautionText;
    return C.alert;
}
