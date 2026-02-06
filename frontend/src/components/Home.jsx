import React, { useEffect, useState } from 'react';
import PredictionForm from './PredictionForm';
import PredictionResults from './PredictionResults';
import TeamSection from './TeamSection';
import TextType from './TextType';
import PredictionLoading from './prediction-loading';
import { FadeIn, PageTransition } from './page-transition';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const FALLBACK_TEAMS = [
    'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS'
];

const mockDistribution = (projection) => {
    const start = Math.max(0, Math.floor(projection) - 10);
    return Array.from({ length: 6 }, (_, idx) => {
        const rangeStart = start + idx * 4;
        const rangeEnd = rangeStart + 4;
        const distance = Math.abs(projection - (rangeStart + rangeEnd) / 2);
        const probability = Math.max(0.05, 0.25 - distance * 0.02);
        return { range: `${rangeStart}-${rangeEnd}`, probability: Number(probability.toFixed(2)) };
    });
};

const mockFactors = (stat) => ([
    {
        factor: 'Recent Form',
        impact: 'positive',
        description: `Last 5 ${stat.toUpperCase()} trend is above baseline.`
    },
    {
        factor: 'Matchup History',
        impact: 'neutral',
        description: 'Opponent defense is league-average in this stat.'
    },
    {
        factor: 'Minutes Projection',
        impact: 'positive',
        description: 'Expected rotation minutes align with season average.'
    }
]);

const buildMockResult = (apiResult) => {
    const projection = Number(
        apiResult?.prediction?.projected_points ?? apiResult.projection ?? 0
    );
    const probabilityOver = Number(
        apiResult?.prediction?.win_probability ?? apiResult.probability_over ?? 0.5
    );
    const recommendation = apiResult?.prediction?.recommendation ?? apiResult.edge;
    const historicalGames = Array.from({ length: 10 }, (_, idx) => ({
        game: `G-${idx + 1}`,
        value: Number((projection + (Math.random() * 8 - 4)).toFixed(1)),
        date: new Date(Date.now() - (idx + 1) * 86400000).toLocaleDateString(),
    })).reverse();

    const avg = historicalGames.reduce((sum, g) => sum + g.value, 0) / historicalGames.length;

    return {
        player: apiResult?.meta?.player ?? apiResult.player,
        stat: apiResult.stat,
        line: apiResult?.prediction?.line ?? apiResult.line,
        prediction:
            recommendation?.toUpperCase() === 'BET_OVER'
                ? 'OVER'
                : recommendation?.toUpperCase() === 'BET_UNDER'
                    ? 'UNDER'
                    : apiResult.edge?.toUpperCase() === 'OVER'
                        ? 'OVER'
                        : 'UNDER',
        confidence: Math.round(probabilityOver * 100),
        probability: probabilityOver,
        projection,
        historicalGames,
        h2hStats: {
            gamesPlayed: 6,
            average: Number(avg.toFixed(1)),
            hitRate: Math.round(probabilityOver * 100),
        },
        distribution: mockDistribution(projection),
        factors: mockFactors(apiResult.stat || 'pts'),
    };
};

const Home = () => {
    const [players, setPlayers] = useState([]);
    const [teams, setTeams] = useState(FALLBACK_TEAMS);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [lastPayload, setLastPayload] = useState(null);
    const [loadingDuration, setLoadingDuration] = useState(6000);

    useEffect(() => {
        const loadOptions = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/options/`);
                if (!res.ok) throw new Error('Failed to load options');
                const data = await res.json();
                if (Array.isArray(data.players)) setPlayers(data.players);
                if (Array.isArray(data.teams) && data.teams.length) setTeams(data.teams);
            } catch (err) {
                setPlayers([]);
            }
        };
        loadOptions();
    }, []);

    const handleSubmit = async (payload) => {
        setError('');
        setLoading(true);
        try {
            setLastPayload(payload);
            const duration = Math.floor(3000 + Math.random() * 2000);
            setLoadingDuration(duration);
            const [res] = await Promise.all([
                fetch(`${API_BASE}/api/predict/manual/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                }),
                new Promise((resolve) => setTimeout(resolve, duration)),
            ]);
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || 'Prediction failed');
            }
            setResult(buildMockResult(data));
        } catch (err) {
            setError(err.message || 'Prediction failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <PageTransition>
            {loading && <PredictionLoading duration={loadingDuration} />}
            <div>
                <FadeIn direction="none">
                    <section className="mt-12 mb-20 md:mb-28 text-center max-w-4xl mx-auto">
                        <TextType
                            text="Prop Predictions"
                            as="h1"
                            className="text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-foreground text-balance"
                            typingSpeed={60}
                            pauseDuration={1200}
                            deletingSpeed={40}
                            loop={false}
                            showCursor
                            cursorCharacter="|"
                        />
                        <p className="text-xl md:text-2xl text-muted-foreground max-w-2xl mx-auto text-pretty leading-relaxed mt-6">
                            Simulate a custom betting scenario by selecting a player, opponent, and line.
                        </p>
                    </section>
                </FadeIn>

                <FadeIn delay={150}>
                    <section id="predictions" className="grid gap-8 md:gap-10 mb-20 md:mb-24 w-full">
                        <div className="rounded-3xl border border-border bg-card p-8 md:p-10 lg:p-12 space-y-8">
                            <div className="mb-8">
                                <h2 className="text-3xl md:text-4xl font-semibold text-foreground mb-2">Prediction Inputs</h2>
                            </div>
                    <PredictionForm
                        players={players}
                        teams={teams}
                        onSubmit={handleSubmit}
                        loading={loading}
                        error={error}
                        lastPayload={lastPayload}
                        apiBase={API_BASE}
                    />
                </div>

                        <div className="space-y-6">
                            <PredictionResults result={result} />
                        </div>
                    </section>
                </FadeIn>

                <FadeIn delay={250}>
                    <TeamSection />
                </FadeIn>
            </div>
        </PageTransition>
    );
};

export default Home;
