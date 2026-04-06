import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from './ui/select';

const PredictionForm = ({
    players = [],
    teams = [],
    onSubmit,
    loading,
    error,
    lastPayload,
    apiBase,
}) => {
    const [playerName, setPlayerName] = useState('');
    const [playerQuery, setPlayerQuery] = useState('');
    const [playerOpen, setPlayerOpen] = useState(false);
    const [playerResults, setPlayerResults] = useState([]);
    const [playerLoading, setPlayerLoading] = useState(false);
    const [opponentTicker, setOpponentTicker] = useState('');
    const [stat, setStat] = useState('pts');
    const [line, setLine] = useState('');
    const [isHome, setIsHome] = useState(true);
    const [fieldErrors, setFieldErrors] = useState({});
    const searchTimeoutRef = useRef(null);

    const playerOptions = useMemo(() => [...players].sort(), [players]);
    const teamOptions = useMemo(() => [...teams].sort(), [teams]);
    const filteredPlayers = useMemo(() => {
        const query = playerQuery.trim().toLowerCase();
        const source = playerResults.length ? playerResults : playerOptions;
        if (!query) return [];
        return source
            .filter((player) => player.toLowerCase().includes(query))
            .slice(0, 8);
    }, [playerOptions, playerQuery, playerResults]);

    useEffect(() => {
        if (!apiBase) return;
        const query = playerQuery.trim();
        if (!query) {
            setPlayerResults([]);
            setPlayerLoading(false);
            return;
        }
        if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current);
        }
        setPlayerLoading(true);
        searchTimeoutRef.current = setTimeout(async () => {
            try {
                const res = await fetch(`${apiBase}/api/players/?q=${encodeURIComponent(query)}`);
                if (!res.ok) throw new Error('Failed to search players');
                const data = await res.json();
                const names = Array.isArray(data)
                    ? data
                          .map((player) => player.full_name)
                          .filter(Boolean)
                    : [];
                setPlayerResults(names);
            } catch (err) {
                setPlayerResults([]);
            } finally {
                setPlayerLoading(false);
            }
        }, 200);
        return () => {
            if (searchTimeoutRef.current) {
                clearTimeout(searchTimeoutRef.current);
            }
        };
    }, [apiBase, playerQuery]);

    const validate = () => {
        const nextErrors = {};
        if (!playerName.trim()) {
            nextErrors.playerName = 'Player name is required.';
        } else if (filteredPlayers.length && !filteredPlayers.includes(playerName.trim())) {
            nextErrors.playerName = 'Select a player from the list.';
        }
        if (!opponentTicker) nextErrors.opponentTicker = 'Opponent is required.';
        if (line === '' || Number.isNaN(Number(line))) nextErrors.line = 'Enter a valid line.';
        setFieldErrors(nextErrors);
        return Object.keys(nextErrors).length === 0;
    };

    const handleSubmit = (event) => {
        event.preventDefault();
        if (!validate()) return;
        onSubmit({
            player_name: playerName.trim(),
            opponent_ticker: opponentTicker,
            is_home: isHome,
            stat,
            line: Number(line),
        });
    };

    const currentPayload = {
        player_name: playerName.trim(),
        line: line === '' ? '' : Number(line),
        opponent_ticker: opponentTicker,
        is_home: isHome,
        stat,
    };

    const isSameAsLast =
        lastPayload &&
        JSON.stringify(lastPayload) === JSON.stringify(currentPayload);

    return (
        <form onSubmit={handleSubmit} className="space-y-8">
            <div className="grid gap-6 md:gap-8 md:grid-cols-2">
                <div className="space-y-3 relative">
                    <Label className="text-sm uppercase tracking-wider font-semibold text-primary">player_name</Label>
                    <Input
                        value={playerQuery}
                        onChange={(e) => {
                            const nextValue = e.target.value;
                            setPlayerQuery(nextValue);
                            setPlayerName(nextValue);
                            setPlayerOpen(true);
                        }}
                        onFocus={() => setPlayerOpen(true)}
                        onBlur={() => setTimeout(() => setPlayerOpen(false), 120)}
                        className="h-12 md:h-14 text-base bg-input border-border rounded-xl text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:ring-2 focus:ring-primary/20"
                        placeholder="Search player"
                        autoComplete="off"
                    />
                    {playerOpen && (
                        <div className="absolute z-50 mt-1 w-full rounded-md border border-border bg-popover text-popover-foreground max-h-56 overflow-y-auto">
                            {playerLoading && (
                                <div className="px-3 py-2 text-base text-muted-foreground">Searching...</div>
                            )}
                            {!playerLoading && filteredPlayers.length ? (
                                filteredPlayers.map((player) => (
                                    <button
                                        type="button"
                                        key={player}
                                        className="w-full text-left px-3 py-2 text-sm hover:bg-accent hover:text-accent-foreground"
                                        onMouseDown={(event) => event.preventDefault()}
                                        onClick={() => {
                                            setPlayerName(player);
                                            setPlayerQuery(player);
                                            setPlayerOpen(false);
                                        }}
                                    >
                                        {player}
                                    </button>
                                ))
                            ) : null}
                            {!playerLoading && !filteredPlayers.length && (
                                <div className="px-3 py-2 text-base text-muted-foreground">No matches</div>
                            )}
                        </div>
                    )}
                    {fieldErrors.playerName && (
                        <p className="text-sm text-muted-foreground">{fieldErrors.playerName}</p>
                    )}
                </div>
                <div className="space-y-3">
                    <Label className="text-sm uppercase tracking-wider font-semibold text-primary">opponent_ticker</Label>
                    <Select value={opponentTicker} onValueChange={setOpponentTicker}>
                        <SelectTrigger className="h-12 md:h-14 text-base bg-input border-border rounded-xl text-foreground">
                            <SelectValue placeholder="Select opponent" />
                        </SelectTrigger>
                    <SelectContent className="bg-popover border-border rounded-xl">
                        {teamOptions.map((team) => (
                            <SelectItem key={team} value={team} className="text-base text-popover-foreground py-3">
                                {team}
                            </SelectItem>
                        ))}
                    </SelectContent>
                    </Select>
                    {fieldErrors.opponentTicker && (
                        <p className="text-sm text-muted-foreground">{fieldErrors.opponentTicker}</p>
                    )}
                </div>
            </div>

            <div className="grid gap-6 md:gap-8 md:grid-cols-2">
                <div className="space-y-3">
                    <Label className="text-sm uppercase tracking-wider font-semibold text-primary">stat</Label>
                    <Select value={stat} onValueChange={setStat}>
                        <SelectTrigger className="h-12 md:h-14 text-base bg-input border-border rounded-xl text-foreground">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-popover border-border rounded-xl">
                            <SelectItem value="pts" className="text-base text-popover-foreground py-3">Points</SelectItem>
                            <SelectItem value="reb" className="text-base text-popover-foreground py-3">Rebounds</SelectItem>
                            <SelectItem value="ast" className="text-base text-popover-foreground py-3">Assists</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
                <div className="space-y-3">
                    <Label className="text-sm uppercase tracking-wider font-semibold text-primary">line</Label>
                    <Input
                        type="number"
                        step="0.5"
                        value={line}
                        onChange={(e) => setLine(e.target.value)}
                        className="h-12 md:h-14 text-base bg-input border-border rounded-xl text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:ring-2 focus:ring-primary/20"
                        placeholder="24.5"
                    />
                    {fieldErrors.line && (
                        <p className="text-sm text-muted-foreground">{fieldErrors.line}</p>
                    )}
                </div>
            </div>

            <div className="grid gap-6 md:gap-8 md:grid-cols-2">
                <div className="space-y-3">
                    <Label className="text-sm uppercase tracking-wider font-semibold text-primary">is_home</Label>
                    <div className="flex items-center gap-2 h-12 md:h-14 bg-input border border-border rounded-xl px-2">
                        <button
                            type="button"
                            onClick={() => setIsHome(true)}
                            className={`flex-1 h-10 md:h-12 rounded-xl text-sm font-medium ${isHome ? 'bg-primary/10 text-primary' : 'text-muted-foreground'}`}
                        >
                            Home
                        </button>
                        <button
                            type="button"
                            onClick={() => setIsHome(false)}
                            className={`flex-1 h-10 md:h-12 rounded-xl text-sm font-medium ${!isHome ? 'bg-primary/10 text-primary' : 'text-muted-foreground'}`}
                        >
                            Away
                        </button>
                    </div>
                </div>
            </div>

            {error && (
                <p className="text-sm text-muted-foreground">{error}</p>
            )}

            <Button
                size="lg"
                className="w-full h-14 md:h-16 text-base font-semibold tracking-wide rounded-xl"
                type="submit"
                disabled={loading || isSameAsLast}
            >
                {loading ? 'Running Scenario...' : 'Run Prediction'}
                <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            {isSameAsLast && !loading && (
                <p className="text-sm text-muted-foreground">
                    Update an input to run a new prediction.
                </p>
            )}
        </form>
    );
};

export default PredictionForm;
