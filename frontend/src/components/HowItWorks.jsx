import React from 'react';
import {
    Brain,
    TrendingUp,
    BarChart3,
    Layers,
    Database,
    Target,
} from 'lucide-react';
import TextType from './TextType';

const FEATURES = [
    {
        icon: Brain,
        title: 'Gradient Boosted Model',
        description:
            'XGBoost-based forecasting tuned for player props, trained on historical box scores and validated with time-aware splits.',
        tags: ['XGBoost', 'Cross-Validated'],
    },
    {
        icon: TrendingUp,
        title: 'Rolling Window Analysis',
        description:
            'L5/L10 rolling averages plus EMA (span=5) capture short-term form while respecting rest days and usage shifts.',
        tags: ['L5/L10', 'EMA L5'],
    },
    {
        icon: BarChart3,
        title: 'Probabilistic Scoring',
        description:
            'We translate projections into over/under likelihoods with calibrated uncertainty and opponent context.',
        tags: ['Probability', 'Uncertainty'],
    },
    {
        icon: Layers,
        title: 'Engineered Features',
        description:
            'Minutes trends, FG% form, and opponent points allowed (L10) are combined with home/away context to build inputs.',
        tags: ['Opp L10', 'Minutes'],
    },
    {
        icon: Database,
        title: 'PostgreSQL Pipeline',
        description:
            'Structured schema tracks Team, Player, Game, and PlayerStats (period 0/1-4) plus PlayerPropLine + Prediction outputs.',
        tags: ['PlayerStats', 'Prop Lines'],
    },
    {
        icon: Target,
        title: 'Actionable Output',
        description:
            'Each call returns a projection, probability_over, and an edge recommendation for the custom scenario you enter.',
        tags: ['Projection', 'Edge'],
    },
];

const HowItWorks = () => {
    return (
    <section id="how-it-works" className="py-20">
            <div className="container mx-auto px-4 max-w-6xl">
                <div className="text-center mb-16 md:mb-20">
                    <span className="text-sm uppercase tracking-[0.2em] text-primary font-medium mb-4 block">
                        Under The Hood
                    </span>
                    <TextType
                        text="How It Works"
                        as="h2"
                        className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-foreground mb-6"
                        typingSpeed={60}
                        pauseDuration={1200}
                        deletingSpeed={40}
                        loop={false}
                        showCursor
                        cursorCharacter="|"
                    />
                    <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
                        Our prediction engine combines historical NBA data, feature engineering, and probabilistic
                        scoring to generate scenario-specific prop edges.
                    </p>
                </div>

                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
                    {FEATURES.map((feature, index) => (
                        <div
                            key={index}
                            className="group rounded-3xl border border-border bg-card p-8 md:p-10 hover:border-primary/30 transition-all duration-300"
                        >
                            <div className="w-14 h-14 md:w-16 md:h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-6">
                                <feature.icon className="w-7 h-7 md:w-8 md:h-8 text-primary" />
                            </div>
                            <h3 className="text-xl md:text-2xl font-semibold text-foreground mb-3 tracking-tight">
                                {feature.title}
                            </h3>
                            <p className="text-base md:text-lg text-muted-foreground leading-relaxed mb-6">
                                {feature.description}
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {feature.tags.map((tag, tagIndex) => (
                                    <span
                                        key={tagIndex}
                                        className={`text-sm font-medium px-3 py-1.5 rounded-full ${
                                            tagIndex === 0
                                                ? 'bg-primary/10 text-primary border border-primary/20'
                                                : 'bg-secondary text-muted-foreground border border-border'
                                        }`}
                                    >
                                        {tag}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
};

export default HowItWorks;
