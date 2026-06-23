export const BREAK_EVEN = 0.524;

export const C = {
    green:  '#22c55e',  /* green-500 */
    red:    '#ef4444',  /* red-500 */
    amber:  '#f59e0b',  /* amber-500 */
    indigo: '#818cf8',  /* indigo-400 — bright for dark surfaces */
    slate:  '#94a3b8',  /* slate-400 */
};

/** Format a 0–1 rate as a percentage string, e.g. 0.524 → "52.4%" */
export function pct(v) {
    return v == null ? '—' : `${(v * 100).toFixed(1)}%`;
}

/** Format a number to d decimal places */
export function fmt(v, d = 1) {
    return v == null ? '—' : Number(v).toFixed(d);
}

/** Inline color for a hit rate vs break-even */
export function hitColor(hr) {
    return hr >= BREAK_EVEN ? C.green : C.red;
}

/** Inline color for ROI — green if positive, red if negative */
export function roiColor(roi) {
    return roi >= 0 ? C.green : C.red;
}
