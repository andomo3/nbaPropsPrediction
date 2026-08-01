import React from 'react';
import { useSearchParams } from 'react-router-dom';
import {
    Band, Eyebrow, FootNotes, GhostSelect, Insight, PageHead, Tabs,
} from './terminal/ui';
import useFetch from './terminal/useFetch';
import EdgePanel from './intelligence/EdgePanel';
import ModuleRow from './intelligence/ModuleRow';
import FloorCeiling from './intelligence/FloorCeiling';
import OpponentExploitability from './intelligence/OpponentExploitability';
import BehavioralFingerprint from './intelligence/BehavioralFingerprint';
import StatisticalValidation from './intelligence/StatisticalValidation';
import { PLAYERS, STATS, API_BASE } from '../utils/constants';
import { C, fmt, hitColor, pct, roiColor, signed } from '../utils/format';

const SEASON = '2026';
const SEASON_LABEL = '2025–26';

const STAT_TABS = STATS.map((s) => ({ value: s.key, label: s.label }));
const PLAYER_OPTIONS = PLAYERS.map((p) => ({ value: p, label: p }));

const VERDICT_COLOR = {
    'Strong signal':      C.acid,
    'Moderate signal':    C.cautionText,
    'Weak signal':        C.cautionText,
    'No reliable signal': C.alert,
    'Insufficient data':  C.ink8,
};

const VERDICT_DOT = {
    'Strong signal':      C.acid,
    'Moderate signal':    C.caution,
    'Weak signal':        C.caution,
    'No reliable signal': C.alert,
    'Insufficient data':  C.ink8,
};

function Figure({ label, value, sub, color }) {
    return (
        <div className="flex flex-col gap-1.5">
            <Eyebrow>{label}</Eyebrow>
            <div
                className="num text-[26px] sm:text-[30px] font-medium leading-none"
                style={{ color: color || 'var(--ink-0)' }}
            >
                {value}
            </div>
            {sub && <div className="text-xs text-ink-7">{sub}</div>}
        </div>
    );
}

export default function PlayerIntelligence() {
    const [params, setParams] = useSearchParams();
    const player = params.get('player_name') || PLAYERS[0];
    const stat = params.get('stat') || 'pts';

    const set = (key, value) => {
        const next = new URLSearchParams();
        next.set('player_name', key === 'player_name' ? value : player);
        next.set('stat', key === 'stat' ? value : stat);
        setParams(next, { replace: true });
    };

    const qs = `?player_name=${encodeURIComponent(player)}&stat=${stat}&season=${SEASON}`;
    const validation  = useFetch(`${API_BASE}/api/intelligence/validation/${qs}`);
    const edge        = useFetch(`${API_BASE}/api/intelligence/edge/${qs}`);
    const floorCeil   = useFetch(`${API_BASE}/api/intelligence/floor-ceiling/${qs}`);
    const opponents   = useFetch(`${API_BASE}/api/intelligence/opponents/${qs}`);
    const fingerprint = useFetch(`${API_BASE}/api/intelligence/fingerprint/${qs}`);
    const summaryReq  = useFetch(`${API_BASE}/api/backtest/season-summary/${qs}`);
    const board       = useFetch(
        `${API_BASE}/api/backtest/leaderboard/?stat=${stat}&model=xgb&season=${SEASON}`,
    );

    const v = validation.data;
    const summary = summaryReq.data?.summary;
    const statLabel = STATS.find((s) => s.key === stat)?.label ?? stat;

    const rankings = board.data?.rankings ?? [];
    const mine = rankings.find((r) => r.player_name === player);
    const rank = mine
        ? {
            rank: mine.rank,
            total: rankings.length,
            tier: mine.predictability_tier,
            score: mine.predictability_score,
          }
        : null;

    const verdict = v?.verdict;
    const games = v?.n_games ?? summary?.total_games;
    const disclosures = v?.disclosures ?? [];
    const rho = v?.edge_correlation?.rho;

    return (
        <>
            <PageHead
                eyebrow={`${statLabel} · ${SEASON_LABEL}${games ? ` · ${games} games modelled` : ''}`}
                title={player}
                controls={
                    <>
                        <GhostSelect
                            value={player}
                            onChange={(val) => set('player_name', val)}
                            options={PLAYER_OPTIONS}
                            label="Player"
                        />
                        <Tabs
                            options={STAT_TABS}
                            value={stat}
                            onChange={(val) => set('stat', val)}
                            ariaLabel="Stat"
                        />
                    </>
                }
            />

            {/* Verdict strip */}
            <Band className="py-6">
                <div className="flex flex-col gap-6 xl:flex-row xl:items-center xl:gap-0">
                    <div className="xl:flex-[1.6] xl:pr-9 flex flex-col gap-2 min-w-0">
                        <Eyebrow wide>Overall verdict</Eyebrow>
                        {verdict ? (
                            <div className="flex items-center gap-3">
                                <span
                                    className="w-2.5 h-2.5 rounded-full shrink-0"
                                    style={{ background: VERDICT_DOT[verdict] ?? C.ink8 }}
                                />
                                <span
                                    className="text-[24px] sm:text-[26px] font-semibold tracking-tightest leading-none"
                                    style={{ color: VERDICT_COLOR[verdict] ?? C.ink8 }}
                                >
                                    {verdict}
                                </span>
                            </div>
                        ) : (
                            <span className="text-[24px] font-semibold text-ink-8 leading-none">
                                {validation.loading ? 'Testing…' : validation.error ? 'Unavailable' : '—'}
                            </span>
                        )}
                        <Insight text={v?.insight} className="max-w-md" />
                    </div>

                    <div className="hidden xl:block w-px h-16 bg-[var(--hair-rule)]" aria-hidden="true" />

                    <div className="xl:flex-[4] xl:pl-8 grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-6">
                        <Figure
                            label="Hit rate"
                            value={v?.hit_rate?.value != null ? pct(v.hit_rate.value) : '—'}
                            color={hitColor(v?.hit_rate?.value)}
                            sub={
                                v?.hit_rate?.p_value != null
                                    ? `vs 52.4% break-even · p=${Number(v.hit_rate.p_value).toFixed(3)}`
                                    : 'vs 52.4% break-even'
                            }
                        />
                        <Figure
                            label="ROI"
                            value={summary ? `${signed(summary.roi)}%` : '—'}
                            color={roiColor(summary?.roi)}
                            sub={summary ? `${signed(summary.total_pnl, 2)}u flat at −110` : undefined}
                        />
                        <Figure
                            label="MAE"
                            value={summary ? fmt(summary.mae, 2) : '—'}
                            sub={rank ? `Rank ${rank.rank} of ${rank.total} players` : undefined}
                        />
                        <Figure
                            label="Bias"
                            value={summary ? signed(summary.bias, 2) : '—'}
                            sub={v?.calibration?.label ?? 'Mean signed error'}
                        />
                    </div>
                </div>
            </Band>

            {/* Edge calibration + conditional splits */}
            <EdgePanel {...edge} />

            {/* Depth modules */}
            <ModuleRow
                floorCeiling={floorCeil.data}
                opponents={opponents.data}
                fingerprint={fingerprint.data}
                rank={rank}
            />

            {/* Depth sections */}
            <FloorCeiling id="floor-ceiling" {...floorCeil} />
            <OpponentExploitability id="opponents" {...opponents} />
            <BehavioralFingerprint id="fingerprint" {...fingerprint} />
            <StatisticalValidation id="validation" {...validation} />

            <FootNotes
                items={[
                    'sig. at α = 0.05 · n.s. = not significant',
                    rho != null
                        ? `Spearman ρ = ${fmt(rho, 2)}${
                            v.edge_correlation.p_value != null
                                ? ` (p=${Number(v.edge_correlation.p_value).toFixed(3)})`
                                : ''
                          }`
                        : null,
                    disclosures.length
                        ? `${disclosures.length} methodology notes & limitations — see Statistical validation`
                        : null,
                ]}
            />
        </>
    );
}
