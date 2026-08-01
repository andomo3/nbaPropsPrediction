import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
    Band, Eyebrow, FootNotes, GhostSelect, GUTTER, NameCell,
    PageHead, Sparkline, StateBlock, Tabs, VRule,
} from './terminal/ui';
import useFetch from './terminal/useFetch';
import { API_BASE, STATS } from '../utils/constants';
import { C, fmt, signed } from '../utils/format';

const SEASON = '2026';
const SEASON_LABEL = '2025–26';
const PRIOR_SEASON_LABEL = '2024–25';

const MODELS = [
    { value: 'xgb',   label: 'XGBoost' },
    { value: 'rf',    label: 'Random forest' },
    { value: 'lr',    label: 'Linear reg.' },
    { value: 'naive', label: 'Rolling avg' },
];

const STAT_TABS = STATS.map((s) => ({ value: s.key, label: s.label }));

const COLS = '44px minmax(160px,220px) 72px 78px 70px 70px 84px minmax(110px,1fr) 76px';
const TABLE_MIN = 'min-w-[940px]';

const TIER_COLOR = {
    High:     C.acid,
    Moderate: C.ink2,
    Low:      C.ink3,
};

/** Columns the table can be sorted by. `dir` is the default direction. */
const SORTS = {
    rank:       { dir: 'asc',  get: (r) => r.rank },
    score:      { dir: 'desc', get: (r) => r.predictability_score ?? -1 },
    mae:        { dir: 'asc',  get: (r) => r.mae },
    r2:         { dir: 'desc', get: (r) => r.r2 ?? -1 },
    cv:         { dir: 'asc',  get: (r) => r.cv ?? Infinity },
    hit_excess: { dir: 'desc', get: (r) => r.hit_excess ?? -Infinity },
};

function SortHead({ id, label, align = 'right', sort, onSort }) {
    const active = sort.key === id;
    return (
        <button
            type="button"
            onClick={() => onSort(id)}
            className={`num text-[11px] font-medium tracking-eyebrow uppercase transition-colors ${
                align === 'right' ? 'text-right justify-end' : 'text-left'
            } flex items-center gap-1 ${active ? 'text-ink-3' : 'text-ink-8 hover:text-ink-5'}`}
        >
            {label}
            <span aria-hidden="true" className={active ? 'text-acid' : 'opacity-0'}>
                {sort.dir === 'asc' ? '↑' : '↓'}
            </span>
        </button>
    );
}

function Summary({ label, value, sub, subColor }) {
    return (
        <div className="px-5 xl:px-8 py-5 flex flex-col gap-1.5 border-b xl:border-b-0 xl:border-r border-hair-row last:border-r-0 last:border-b-0">
            <Eyebrow>{label}</Eyebrow>
            <span className="text-[20px] sm:text-[22px] font-semibold text-ink-0 truncate">{value}</span>
            <span className="text-[13px]" style={{ color: subColor || 'var(--ink-7)' }}>{sub}</span>
        </div>
    );
}

export default function Leaderboard() {
    const [stat, setStat] = useState('pts');
    const [model, setModel] = useState('xgb');
    const [sort, setSort] = useState({ key: 'rank', dir: 'asc' });

    const board = useFetch(
        `${API_BASE}/api/backtest/leaderboard/?stat=${stat}&model=${model}&season=${SEASON}`,
    );
    const history = useFetch(
        `${API_BASE}/api/backtest/leaderboard-comparison/?stat=${stat}&model=${model}`,
    );

    const rankings = board.data?.rankings ?? [];

    /* Prior-season scores, keyed by player, for the trend column. */
    const prior = useMemo(() => {
        const out = {};
        for (const p of history.data?.players ?? []) {
            const last = p.seasons?.['2025'];
            if (last?.available) out[p.player_name] = last.predictability_score;
        }
        return out;
    }, [history.data]);

    const rows = useMemo(() => {
        const spec = SORTS[sort.key] ?? SORTS.rank;
        const sign = sort.dir === 'asc' ? 1 : -1;
        return [...rankings].sort((a, b) => (spec.get(a) - spec.get(b)) * sign);
    }, [rankings, sort]);

    const onSort = (key) => {
        setSort((s) =>
            s.key === key
                ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' }
                : { key, dir: SORTS[key].dir },
        );
    };

    /* Summary strip — all four figures come straight off the ranked rows. */
    const top = rankings.find((r) => r.rank === 1);
    const movers = useMemo(() => {
        const withDelta = rankings
            .filter((r) => prior[r.player_name] != null && r.predictability_score != null)
            .map((r) => ({ ...r, delta: r.predictability_score - prior[r.player_name] }))
            .sort((a, b) => b.delta - a.delta);
        return { riser: withDelta[0], faller: withDelta[withDelta.length - 1] };
    }, [rankings, prior]);

    const tierSpread = useMemo(() => {
        const counts = { High: 0, Moderate: 0, Low: 0 };
        for (const r of rankings) {
            if (r.predictability_tier in counts) counts[r.predictability_tier] += 1;
        }
        return counts;
    }, [rankings]);

    const statLabel = STATS.find((s) => s.key === stat)?.label ?? stat;

    return (
        <>
            <PageHead
                eyebrow="Composite of R², coefficient of variation and hit-rate excess"
                title="Predictability leaderboard"
                controls={
                    <>
                        <Tabs options={STAT_TABS} value={stat} onChange={setStat} ariaLabel="Stat" />
                        <VRule className="hidden sm:block" />
                        <GhostSelect value={model} onChange={setModel} options={MODELS} label="Model" />
                    </>
                }
            />

            <StateBlock
                loading={board.loading}
                error={board.error}
                empty={rankings.length === 0 ? `No ranked ${statLabel.toLowerCase()} data for ${SEASON_LABEL}.` : null}
                emptyHint="python manage.py seed_season_backtest --season 2026"
            >
                <Band padded={false} className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4">
                    <Summary
                        label="Most predictable"
                        value={top?.player_name ?? '—'}
                        sub={
                            top
                                ? `Score ${fmt(top.predictability_score, 1)} · ${top.predictability_tier} · MAE ${fmt(top.mae, 2)}`
                                : '—'
                        }
                    />
                    <Summary
                        label="Biggest riser"
                        value={movers.riser?.player_name ?? '—'}
                        sub={
                            movers.riser
                                ? `${signed(movers.riser.delta, 1)} score vs ${PRIOR_SEASON_LABEL}`
                                : `No ${PRIOR_SEASON_LABEL} comparison`
                        }
                        subColor={movers.riser ? C.acid : undefined}
                    />
                    <Summary
                        label="Biggest faller"
                        value={movers.faller?.player_name ?? '—'}
                        sub={
                            movers.faller
                                ? `${signed(movers.faller.delta, 1)} score vs ${PRIOR_SEASON_LABEL}`
                                : `No ${PRIOR_SEASON_LABEL} comparison`
                        }
                        subColor={movers.faller ? C.alert : undefined}
                    />
                    <Summary
                        label="Tier spread"
                        value={`${tierSpread.High} High · ${tierSpread.Moderate} Mod · ${tierSpread.Low} Low`}
                        sub={`${rankings.length} qualified players`}
                    />
                </Band>

                <div className="table-scroll border-b border-hair">
                    <div className={TABLE_MIN}>
                        <div
                            style={{ gridTemplateColumns: COLS }}
                            className={`grid gap-4 ${GUTTER} py-2.5 border-b border-hair`}
                        >
                            <SortHead id="rank" label="#" align="left" sort={sort} onSort={onSort} />
                            <span className="num text-[11px] font-medium tracking-eyebrow uppercase text-ink-8 self-center">
                                Player
                            </span>
                            <SortHead id="score" label="Score" sort={sort} onSort={onSort} />
                            <SortHead id="mae" label="MAE" sort={sort} onSort={onSort} />
                            <SortHead id="r2" label="R²" sort={sort} onSort={onSort} />
                            <SortHead id="cv" label="CV" sort={sort} onSort={onSort} />
                            <SortHead id="hit_excess" label="Hit exc." sort={sort} onSort={onSort} />
                            <span className="num text-[11px] font-medium tracking-eyebrow uppercase text-ink-8 self-center">
                                vs {PRIOR_SEASON_LABEL}
                            </span>
                            <span className="num text-[11px] font-medium tracking-eyebrow uppercase text-ink-8 text-right self-center">
                                Tier
                            </span>
                        </div>

                        {rows.map((r) => {
                            const tierColor = TIER_COLOR[r.predictability_tier] ?? C.ink8;
                            const was = prior[r.player_name];
                            const delta = was != null && r.predictability_score != null
                                ? r.predictability_score - was
                                : null;
                            const trendColor = delta == null ? C.ink8
                                : delta > 1 ? C.acid
                                : delta < -1 ? C.alert
                                : C.ink3;

                            return (
                                <Link
                                    key={r.player_name}
                                    to={`/intelligence?player_name=${encodeURIComponent(r.player_name)}&stat=${stat}`}
                                    style={{ gridTemplateColumns: COLS }}
                                    className={`grid gap-4 items-center ${GUTTER} py-3 border-b border-hair-soft hover:bg-white/[0.02] transition-colors`}
                                >
                                    <span
                                        className="num text-sm font-medium"
                                        style={{ color: r.rank === 1 ? C.acid : C.ink8 }}
                                    >
                                        {String(r.rank).padStart(2, '0')}
                                    </span>
                                    <NameCell name={r.player_name} meta={`${r.total_games} games`} />
                                    <span
                                        className="num text-base font-semibold text-right"
                                        style={{ color: tierColor }}
                                    >
                                        {fmt(r.predictability_score, 0)}
                                    </span>
                                    <span className="num text-[15px] text-ink-3 text-right">{fmt(r.mae, 2)}</span>
                                    <span className="num text-[15px] text-ink-3 text-right">{fmt(r.r2, 2)}</span>
                                    <span className="num text-[15px] text-ink-3 text-right">{fmt(r.cv, 2)}</span>
                                    <span
                                        className="num text-[15px] text-right"
                                        style={{ color: r.hit_excess > 0 ? C.acid : C.ink5 }}
                                    >
                                        {signed(r.hit_excess, 1)}
                                    </span>
                                    <div className="flex items-center gap-2.5 min-w-0">
                                        <Sparkline
                                            values={delta == null ? [] : [was, r.predictability_score]}
                                            color={trendColor}
                                        />
                                        <span
                                            className="num text-xs w-[38px] shrink-0 text-right"
                                            style={{ color: trendColor }}
                                        >
                                            {delta == null ? '—' : signed(delta, 1)}
                                        </span>
                                    </div>
                                    <span
                                        className="num text-sm font-semibold text-right"
                                        style={{ color: tierColor }}
                                    >
                                        {r.predictability_tier ?? '—'}
                                    </span>
                                </Link>
                            );
                        })}
                    </div>
                </div>

                <FootNotes
                    items={[
                        'Score = 0.5·R² + 0.3·(1−CV) + 0.2·hit-rate excess, rescaled 0–100',
                        'Minimum 5 graded games to qualify',
                        `Trend compares ${SEASON_LABEL} with ${PRIOR_SEASON_LABEL} on the same model`,
                        'Hit exc. = hit rate minus the 52.4% break-even, in points',
                    ]}
                />
            </StateBlock>
        </>
    );
}
