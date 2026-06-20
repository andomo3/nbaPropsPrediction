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
        <div className="min-h-screen bg-background text-foreground p-6 max-w-5xl mx-auto">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-foreground">Player Intelligence</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Conditional edge analysis · floor/ceiling profiling · opponent exploitability · behavioral fingerprint
                </p>
            </div>

            <div className="flex items-center gap-4 mb-6 flex-wrap">
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

                <div className="flex gap-1">
                    {STATS.map(s => (
                        <button
                            key={s.key}
                            onClick={() => setStat(s.key)}
                            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                                stat === s.key
                                    ? 'bg-indigo-500 text-white'
                                    : 'bg-card border border-border text-muted-foreground hover:text-foreground'
                            }`}
                        >
                            {s.label}
                        </button>
                    ))}
                </div>
            </div>

            <StatisticalValidation  {...validation} />
            <EdgeCalibration        {...edge} />
            <FloorCeiling           {...floorCeil} />
            <OpponentExploitability {...opponents} />
            <BehavioralFingerprint  {...fingerprint} />
        </div>
    );
}
