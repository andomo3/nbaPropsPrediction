import React from 'react';
import { motion } from 'framer-motion';
import TextType from './TextType';

const Overview = () => {
    return (
        <div>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center mb-32"
            >
                <TextType
                    text="How It Works"
                    as="h1"
                    className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-foreground text-balance"
                    typingSpeed={60}
                    pauseDuration={1200}
                    deletingSpeed={40}
                    loop={false}
                    showCursor={false}
                    cursorCharacter="|"
                />
                <p className="text-base text-muted-foreground leading-relaxed max-w-2xl mx-auto mt-4">
                    Understand the pipeline behind PropEdge — from data ingestion to scenario-based predictions.
                </p>
            </motion.div>

            <section className="grid gap-8 md:grid-cols-3 max-w-4xl mx-auto mb-32">
                {[
                    {
                        title: 'Data Ingestion',
                        body: 'We normalize historical box scores and enrich them with context-driven features.',
                    },
                    {
                        title: 'Feature Engineering',
                        body: 'Rolling averages, EMA momentum, and opponent defense signals power the model inputs.',
                    },
                    {
                        title: 'Scenario Engine',
                        body: 'You provide opponent, home/away, and line — the model returns a probability edge.',
                    },
                ].map((card) => (
                    <div key={card.title} className="rounded-2xl border border-border bg-card p-6 md:p-8">
                        <h3 className="text-xl font-semibold text-foreground">{card.title}</h3>
                        <p className="mt-2 text-sm text-muted-foreground">{card.body}</p>
                    </div>
                ))}
            </section>

            <section className="rounded-2xl border border-border bg-card p-6 md:p-8">
                <div className="mb-10">
                    <h2 className="text-xl font-semibold text-foreground mb-1">Prediction Outputs</h2>
                    <p className="text-sm text-muted-foreground">What the model returns</p>
                </div>
                <p className="text-base text-muted-foreground leading-relaxed">
                    The platform highlights projection, probability, and edge. Historical performance and matchup trends
                    help you validate the model’s reasoning before placing a bet.
                </p>
            </section>
        </div>
    );
};

export default Overview;

