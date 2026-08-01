import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
    Eyebrow, FootNotes, GhostSelect, GUTTER, HeadRow, Meter,
    NameCell, Num, PageHead, Row, StateBlock, Tabs, VRule,
} from './terminal/ui';
import BoardEmpty from './BoardEmpty';
import { API_BASE, STATS } from '../utils/constants';
import { C, fmt, signed } from '../utils/format';

const COLS = 'minmax(180px,220px) 84px 84px 84px 84px minmax(140px,1fr) 84px';
const TABLE_MIN = 'min-w-[900px]';

const EDGE_FILTERS = [
    { value: '1', label: 'Edge 1.0+' },
    { value: '2', label: 'Edge 2.0+' },
    { value: '0', label: 'All props' },
];

const STAT_TABS = STATS.map((s) => ({ value: s.key, label: s.label }));

/**
 * Signal is the model's confidence in the side it called, banded so the eye
 * can sort the board without reading every figure.
 */
function signalFor(confidence) {
    if (confidence >= 65) return { label: 'STRONG', color: C.acid };
    if (confidence >= 58) return { label: 'FAIR', color: C.cautionText };
    return { label: 'THIN', color: C.ink8 };
}

/** Colour for the projected edge: the accent goes to overs, amber to unders. */
function edgeColor(edge) {
    if (edge >= 2) return C.acid;
    if (edge <= -2) return C.cautionText;
    if (Math.abs(edge) >= 1) return C.ink3;
    return C.ink5;
}

function matchupLabel(pick) {
    const side = pick.is_home ? 'vs' : '@';
    return [pick.team, side, pick.opponent].filter(Boolean).join(' ');
}

function BoardRow({ pick, called }) {
    const edge = pick.projection - pick.line;
    const signal = signalFor(pick.confidence_pct);
    const meter = Math.max(6, Math.min(100, ((pick.confidence_pct - 50) / 30) * 100));

    return (
        <Row cols={COLS} className={called ? '' : 'opacity-70'}>
            <NameCell name={pick.player_name} meta={matchupLabel(pick)} dim={!called} />
            <Num>{fmt(pick.line)}</Num>
            <Num color={called ? 'var(--ink-1)' : 'var(--ink-3)'} weight={500}>
                {fmt(pick.projection)}
            </Num>
            <Num color={edgeColor(edge)} weight={500}>
                {signed(edge)}
            </Num>
            <Num>{pick.confidence_pct}%</Num>
            <div className="flex items-center gap-2.5 min-w-0">
                <Meter value={meter} color={signal.color} className="flex-1" />
                <span
                    className="num text-[12px] font-medium w-[52px] shrink-0"
                    style={{ color: signal.color }}
                >
                    {signal.label}
                </span>
            </div>
            {called ? (
                <Num color="var(--ink-1)" weight={600} size={14}>
                    {pick.edge.toUpperCase()}
                </Num>
            ) : (
                <Num color="var(--ink-8)" weight={500} size={14}>
                    PASS
                </Num>
            )}
        </Row>
    );
}

/**
 * Narrow-viewport row. The seven-column board only works with width, so below
 * `lg` each prop becomes a stacked block that keeps the same reading order.
 */
function BoardCard({ pick, called }) {
    const edge = pick.projection - pick.line;
    const signal = signalFor(pick.confidence_pct);
    const meter = Math.max(6, Math.min(100, ((pick.confidence_pct - 50) / 30) * 100));

    return (
        <div className={`${GUTTER} py-3.5 flex flex-col gap-3 border-b border-hair-soft ${called ? '' : 'opacity-70'}`}>
            <div className="flex items-baseline justify-between gap-3">
                <div className="flex flex-col gap-0.5 min-w-0">
                    <span className={`text-[15px] font-medium truncate ${called ? 'text-ink-1' : 'text-ink-3'}`}>
                        {pick.player_name}
                    </span>
                    <span className="text-xs text-ink-8">{matchupLabel(pick)}</span>
                </div>
                <span
                    className="num text-sm font-semibold shrink-0"
                    style={{ color: called ? 'var(--ink-1)' : 'var(--ink-8)' }}
                >
                    {called ? pick.edge.toUpperCase() : 'PASS'}
                </span>
            </div>

            <div className="grid grid-cols-4 gap-3">
                {[
                    ['Line', fmt(pick.line), C.ink3],
                    ['Proj', fmt(pick.projection), called ? C.ink0 : C.ink3],
                    ['Edge', signed(edge), edgeColor(edge)],
                    ['Conf', `${pick.confidence_pct}%`, C.ink3],
                ].map(([label, value, color]) => (
                    <div key={label} className="flex flex-col gap-0.5">
                        <span className="num text-[10px] tracking-eyebrow uppercase text-ink-8">{label}</span>
                        <span className="num text-sm" style={{ color }}>{value}</span>
                    </div>
                ))}
            </div>

            <div className="flex items-center gap-2.5">
                <Meter value={meter} color={signal.color} className="flex-1" />
                <span className="num text-[11px] font-medium w-[46px] shrink-0" style={{ color: signal.color }}>
                    {signal.label}
                </span>
            </div>
        </div>
    );
}

function RailSection({ label, children, last = false }) {
    return (
        <div className={`px-5 xl:px-7 py-5 ${last ? '' : 'border-b border-hair'} flex flex-col gap-3.5`}>
            <Eyebrow wide>{label}</Eyebrow>
            {children}
        </div>
    );
}

function Rail({ picks, called, threshold, statLabel }) {
    const overs = called.filter((p) => p.edge === 'Over').length;
    const unders = called.length - overs;
    const avgEdge = called.length
        ? called.reduce((a, p) => a + Math.abs(p.projection - p.line), 0) / called.length
        : 0;

    const strongest = [...picks]
        .sort((a, b) => Math.abs(b.projection - b.line) - Math.abs(a.projection - a.line))
        .slice(0, 3);

    return (
        <aside className="flex flex-col">
            <RailSection label={`Board summary · ${statLabel}`}>
                <div className="grid grid-cols-3 gap-3">
                    <div className="flex flex-col gap-1">
                        <span className="num text-[22px] font-medium text-ink-0 leading-none">
                            {called.length}
                        </span>
                        <span className="text-xs text-ink-8">called</span>
                    </div>
                    <div className="flex flex-col gap-1">
                        <span className="num text-[22px] font-medium text-acid leading-none">
                            {fmt(avgEdge)}
                        </span>
                        <span className="text-xs text-ink-8">avg edge</span>
                    </div>
                    <div className="flex flex-col gap-1">
                        <span className="num text-[22px] font-medium text-ink-0 leading-none">
                            {overs}/{unders}
                        </span>
                        <span className="text-xs text-ink-8">over / under</span>
                    </div>
                </div>
            </RailSection>

            <RailSection label="Strongest edges">
                {strongest.length === 0 && (
                    <p className="text-sm text-ink-7">Nothing on the board yet.</p>
                )}
                {strongest.map((p, i) => {
                    const edge = p.projection - p.line;
                    return (
                        <Link
                            key={`${p.player_name}-${p.stat}`}
                            to={`/intelligence?player_name=${encodeURIComponent(p.player_name)}&stat=${p.stat}`}
                            className={`grid grid-cols-[1fr_auto] gap-3 items-baseline py-2 group ${
                                i === strongest.length - 1 ? '' : 'border-b border-hair-row'
                            }`}
                        >
                            <span className="text-sm text-ink-3 group-hover:text-ink-1 transition-colors truncate">
                                {p.player_name}
                            </span>
                            <span className="num text-sm font-medium" style={{ color: edgeColor(edge) }}>
                                {signed(edge)}
                            </span>
                        </Link>
                    );
                })}
            </RailSection>

            <RailSection label="Rules in force" last>
                <p className="text-sm leading-[1.55] text-ink-4">
                    {threshold > 0
                        ? `Only props with a projected edge of ${fmt(threshold)}+ pts are called; everything else is marked PASS.`
                        : 'No edge floor applied — every modelled prop is called.'}{' '}
                    The API additionally suppresses any pick below its configured confidence floor.
                </p>
                <Link
                    to="/season-report"
                    className="text-[13px] text-ink-3 hover:text-acid transition-colors w-fit"
                >
                    See how the model has performed →
                </Link>
            </RailSection>
        </aside>
    );
}

export default function Board() {
    const [stat, setStat] = useState('pts');
    const [threshold, setThreshold] = useState('1');
    const [state, setState] = useState({ data: null, loading: true, error: null });

    useEffect(() => {
        let cancelled = false;
        setState({ data: null, loading: true, error: null });

        fetch(`${API_BASE}/api/picks/?stat=${stat}`)
            .then((res) => {
                if (!res.ok) throw new Error(`Request failed (HTTP ${res.status})`);
                return res.json();
            })
            .then((data) => !cancelled && setState({ data, loading: false, error: null }))
            .catch((err) => !cancelled && setState({ data: null, loading: false, error: err.message }));

        return () => { cancelled = true; };
    }, [stat]);

    const { data, loading, error } = state;
    const picks = data?.picks ?? [];
    const floor = Number(threshold);

    const sorted = useMemo(
        () => [...picks].sort((a, b) =>
            Math.abs(b.projection - b.line) - Math.abs(a.projection - a.line)),
        [picks],
    );
    const called = useMemo(
        () => sorted.filter((p) => Math.abs(p.projection - p.line) >= floor),
        [sorted, floor],
    );

    const statLabel = STATS.find((s) => s.key === stat)?.label ?? stat;
    const season = data?.season ?? null;
    const matchups = new Set(picks.map((p) => [p.team, p.opponent].sort().join('-'))).size;
    const boardDate = data?.date
        ? new Date(`${data.date}T12:00:00`).toLocaleDateString('en-US', {
            weekday: 'short', day: 'numeric', month: 'short',
          }).toUpperCase()
        : '—';

    // An empty slate is a screen of its own, not a one-line message: the stat
    // tabs and edge filter have nothing to act on, so they come off too.
    const slateEmpty = !loading && !error && picks.length === 0;

    let headEyebrow;
    if (picks.length > 0) {
        headEyebrow = `${boardDate} · ${picks.length} PROPS MODELLED · ${matchups} MATCHUPS`;
    } else if (slateEmpty) {
        headEyebrow = season?.status === 'in_season' || !season
            ? `${boardDate} · NO SLATE`
            : `${boardDate} · OFF-SEASON`;
    } else {
        headEyebrow = `${boardDate} · TODAY'S SLATE`;
    }

    // The empty screen is its own hero — a page title above it would repeat
    // the state twice, once in each eyebrow.
    if (slateEmpty) {
        return <BoardEmpty season={season} statLabel={statLabel} boardDate={boardDate} />;
    }

    return (
        <>
            <PageHead
                eyebrow={headEyebrow}
                title="Tonight's board"
                controls={
                    <>
                        <Tabs options={STAT_TABS} value={stat} onChange={setStat} ariaLabel="Stat" />
                        <VRule className="hidden sm:block" />
                        <GhostSelect
                            value={threshold}
                            onChange={setThreshold}
                            options={EDGE_FILTERS}
                            label="Minimum projected edge"
                        />
                    </>
                }
            />

            <StateBlock loading={loading} error={error}>
                <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_1px_360px]">
                    <div className="flex flex-col min-w-0 border-b border-hair xl:border-b-0">
                        <div className="lg:hidden">
                            {sorted.map((p) => (
                                <BoardCard
                                    key={`m-${p.player_name}-${p.stat}`}
                                    pick={p}
                                    called={Math.abs(p.projection - p.line) >= floor}
                                />
                            ))}
                        </div>

                        <div className="hidden lg:block table-scroll">
                            <div className={TABLE_MIN}>
                                <HeadRow cols={COLS}>
                                    <span>Player</span>
                                    <span className="text-right">Line</span>
                                    <span className="text-right">Proj</span>
                                    <span className="text-right">Edge</span>
                                    <span className="text-right">Conf</span>
                                    <span>Signal</span>
                                    <span className="text-right">Call</span>
                                </HeadRow>
                                {sorted.map((p) => (
                                    <BoardRow
                                        key={`${p.player_name}-${p.stat}`}
                                        pick={p}
                                        called={Math.abs(p.projection - p.line) >= floor}
                                    />
                                ))}
                            </div>
                        </div>
                        <div className={`${GUTTER} py-3.5 flex items-center justify-between gap-4 text-[13px] text-ink-8`}>
                            <span>
                                {called.length} of {picks.length} modelled props clear the edge filter
                            </span>
                            {floor > 0 && called.length < picks.length && (
                                <button
                                    type="button"
                                    onClick={() => setThreshold('0')}
                                    className="text-ink-3 hover:text-acid transition-colors"
                                >
                                    Show all →
                                </button>
                            )}
                        </div>
                    </div>

                    <div className="hidden xl:block bg-hair" aria-hidden="true" />

                    <Rail picks={sorted} called={called} threshold={floor} statLabel={statLabel} />
                </div>
            </StateBlock>

            <div className="border-t border-hair">
                <FootNotes
                    items={[
                        'Edge = model projection − posted line',
                        'Confidence is the modelled probability of the called side',
                        data?.generated_at
                            ? `Generated ${new Date(data.generated_at).toLocaleString()}`
                            : null,
                    ]}
                />
            </div>
        </>
    );
}
