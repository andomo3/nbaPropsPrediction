import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import EdgeCalibration from './intelligence/EdgeCalibration';
import FloorCeiling from './intelligence/FloorCeiling';
import OpponentExploitability from './intelligence/OpponentExploitability';
import BehavioralFingerprint from './intelligence/BehavioralFingerprint';
import StatisticalValidation from './intelligence/StatisticalValidation';
import { PLAYERS, STATS, API_BASE } from '../utils/constants';

function useFetch(url) {
    const [state, setState] = useState({ data: null, loading: true, error: null });
    useEffect(() => {
        setState({ data: null, loading: true, error: null });
        fetch(url)
            .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
            .then(data => setState({ data, loading: false, error: null }))
            .catch(err => setState({ data: null, loading: false, error: String(err) }));
    }, [url]);
    return state;
}

export default function PlayerIntelligence() {
    const [searchParams, setSearchParams] = useSearchParams();
    const [player, setPlayer] = useState(searchParams.get('player_name') || PLAYERS[0]);
    const [stat, setStat]     = useState(searchParams.get('stat') || 'pts');

    useEffect(() => { setSearchParams({ player_name: player, stat }); }, [player, stat]);

    const qs = `?player_name=${encodeURIComponent(player)}&stat=${stat}&season=2026`;
    const edge        = useFetch(`${API_BASE}/api/intelligence/edge/${qs}`);
    const floorCeil   = useFetch(`${API_BASE}/api/intelligence/floor-ceiling/${qs}`);
    const opponents   = useFetch(`${API_BASE}/api/intelligence/opponents/${qs}`);
    const fingerprint = useFetch(`${API_BASE}/api/intelligence/fingerprint/${qs}`);
    const validation  = useFetch(`${API_BASE}/api/intelligence/validation/${qs}`);

    return (
        <div className="w-full max-w-4xl mx-auto py-10">

            {/* Page header */}
            <div className="mb-10">
                <p className="text-xs font-semibold tracking-widest uppercase text-muted-foreground mb-3">
                    Player Intelligence
                </p>
                <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
                    {player}
                </h1>
                <p className="text-sm text-muted-foreground mt-2">
                    Edge calibration · floor/ceiling · opponent exploitability · behavioral fingerprint
                </p>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-4 mb-10 flex-wrap">
                <Select value={player} onValueChange={setPlayer}>
                    <SelectTrigger className="w-56">
                        <SelectValue placeholder="Select player" />
                    </SelectTrigger>
                    <SelectContent>
                        {PLAYERS.map(p => (
                            <SelectItem key={p} value={p}>{p}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                <div className="flex gap-1.5">
                    {STATS.map(s => (
                        <button
                            key={s.key}
                            onClick={() => setStat(s.key)}
                            className={`px-5 py-2 rounded-lg text-xs font-semibold tracking-wide uppercase transition-colors ${
                                stat === s.key
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-card border border-border text-muted-foreground hover:text-foreground'
                            }`}
                        >
                            {s.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Sections — Statistical Validation always open; detail sections collapsible */}
            <StatisticalValidation {...validation} />

            <EdgeCalibration
                {...edge}
                collapsible
                defaultOpen={true}
            />
            <FloorCeiling
                {...floorCeil}
                collapsible
                defaultOpen={false}
            />
            <OpponentExploitability
                {...opponents}
                collapsible
                defaultOpen={false}
            />
            <BehavioralFingerprint
                {...fingerprint}
                collapsible
                defaultOpen={false}
            />
        </div>
    );
}
