import React, { useMemo, useState } from 'react';
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

const PROP_TYPES = [
    { value: 'pts', label: 'Points' },
    { value: 'reb', label: 'Rebounds' },
    { value: 'ast', label: 'Assists' },
    { value: 'stl', label: 'Steals' },
    { value: 'blk', label: 'Blocks' },
    { value: 'pra', label: 'Pts + Reb + Ast' },
];

const PredictionForm = ({
    players = [],
    teams = [],
    onSubmit,
    loading,
    error,
}) => {
    const [playerName, setPlayerName] = useState('');
    const [playerQuery, setPlayerQuery] = useState('');
    const [playerOpen, setPlayerOpen] = useState(false);
    const [opponent, setOpponent] = useState('');
    const [stat, setStat] = useState('pts');
    const [line, setLine] = useState('');
    const [isHome, setIsHome] = useState(true);
    const [daysRest, setDaysRest] = useState(2);
    const [fieldErrors, setFieldErrors] = useState({});

    const playerOptions = useMemo(() => [...players].sort(), [players]);
    const teamOptions = useMemo(() => [...teams].sort(), [teams]);
    const filteredPlayers = useMemo(() => {
        const query = playerQuery.trim().toLowerCase();
        if (!query) return playerOptions;
        return playerOptions.filter((player) => player.toLowerCase().includes(query));
    }, [playerOptions, playerQuery]);

    const validate = () => {
        const nextErrors = {};
        if (!playerName.trim()) nextErrors.playerName = 'Player name is required.';
        if (!opponent) nextErrors.opponent = 'Opponent is required.';
        if (!stat) nextErrors.stat = 'Stat type is required.';
        if (line === '' || Number.isNaN(Number(line))) nextErrors.line = 'Enter a valid line.';
        setFieldErrors(nextErrors);
        return Object.keys(nextErrors).length === 0;
    };

    const handleSubmit = (event) => {
        event.preventDefault();
        if (!validate()) return;
        onSubmit({
            player_name: playerName.trim(),
            stat,
            line: Number(line),
            opponent,
            is_home: isHome,
            days_rest: Number(daysRest) || 2,
        });
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-8">
            <div className="grid gap-6 md:gap-8 md:grid-cols-2">
                <div className="space-y-3 relative">
                    <Label className="text-sm text-muted-foreground uppercase tracking-wider font-medium">Player</Label>
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
                            {filteredPlayers.length ? (
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
                            ) : (
                                <div className="px-3 py-2 text-base text-muted-foreground">No matches</div>
                            )}
                        </div>
                    )}
                    {fieldErrors.playerName && (
                        <p className="text-sm text-muted-foreground">{fieldErrors.playerName}</p>
                    )}
                </div>
                <div className="space-y-3">
                    <Label className="text-sm text-muted-foreground uppercase tracking-wider font-medium">Opponent</Label>
                    <Select value={opponent} onValueChange={setOpponent}>
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
                    {fieldErrors.opponent && (
                        <p className="text-sm text-muted-foreground">{fieldErrors.opponent}</p>
                    )}
                </div>
            </div>

            <div className="grid gap-6 md:gap-8 md:grid-cols-2">
                <div className="space-y-3">
                    <Label className="text-sm text-muted-foreground uppercase tracking-wider font-medium">Prop Type</Label>
                    <Select value={stat} onValueChange={setStat}>
                        <SelectTrigger className="h-12 md:h-14 text-base bg-input border-border rounded-xl text-foreground">
                            <SelectValue placeholder="Select prop" />
                        </SelectTrigger>
                    <SelectContent className="bg-popover border-border rounded-xl">
                        {PROP_TYPES.map((prop) => (
                            <SelectItem key={prop.value} value={prop.value} className="text-base text-popover-foreground py-3">
                                {prop.label}
                            </SelectItem>
                        ))}
                    </SelectContent>
                    </Select>
                    {fieldErrors.stat && (
                        <p className="text-sm text-muted-foreground">{fieldErrors.stat}</p>
                    )}
                </div>
                <div className="space-y-3">
                    <Label className="text-sm text-muted-foreground uppercase tracking-wider font-medium">Line</Label>
                    <Input
                        type="number"
                        step="0.5"
                        value={line}
                        onChange={(e) => setLine(e.target.value)}
                        className="h-12 md:h-14 text-base bg-input border-border rounded-xl text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:ring-2 focus:ring-primary/20"
                        placeholder="25.5"
                    />
                    {fieldErrors.line && (
                        <p className="text-sm text-muted-foreground">{fieldErrors.line}</p>
                    )}
                </div>
            </div>

            <div className="grid gap-6 md:gap-8 md:grid-cols-2">
                <div className="space-y-3">
                    <Label className="text-sm text-muted-foreground uppercase tracking-wider font-medium">Days Rest</Label>
                    <Input
                        type="number"
                        min="0"
                        max="7"
                        value={daysRest}
                        onChange={(e) => setDaysRest(e.target.value)}
                        className="h-12 md:h-14 text-base bg-input border-border rounded-xl text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:ring-2 focus:ring-primary/20"
                    />
                </div>
                <div className="space-y-3">
                    <Label className="text-sm text-muted-foreground uppercase tracking-wider font-medium">Fixture</Label>
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
                disabled={loading}
            >
                {loading ? 'Running Scenario...' : 'Run Prediction'}
                <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
        </form>
    );
};

export default PredictionForm;
