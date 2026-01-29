import React from 'react';
import { motion } from 'framer-motion';
import TextType from './TextType';
import TeamSection from './TeamSection';

const AboutUs = () => {
    return (
        <div>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center mb-32"
            >
                <TextType
                    text="About Us"
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
                    We build responsible, data-driven NBA props tooling for serious bettors and analysts.
                </p>
            </motion.div>

            <section className="grid gap-6 md:grid-cols-3 mb-32">
                {[
                    {
                        title: 'Mission',
                        body: 'Deliver transparent model-driven projections that help users make informed decisions.',
                    },
                    {
                        title: 'Approach',
                        body: 'Blend historical performance, opponent context, and scenario inputs to score edges.',
                    },
                    {
                        title: 'Values',
                        body: 'Accuracy, clarity, and measurable impact in every release.',
                    },
                ].map((card) => (
                    <div key={card.title} className="rounded-2xl border border-border bg-card p-6 md:p-8">
                        <h3 className="text-xl font-semibold text-foreground">{card.title}</h3>
                        <p className="mt-2 text-sm text-muted-foreground">{card.body}</p>
                    </div>
                ))}
            </section>

            {/* <section className="rounded-2xl border border-border bg-card p-6 md:p-8 mb-32">
                <div className="mb-10">
                    <h2 className="text-xl font-semibold text-foreground mb-1">Our Story</h2>
                    <p className="text-sm text-muted-foreground">How PropEdge was built</p>
                </div>
                <p className="text-base text-muted-foreground leading-relaxed">
                    PropEdge was built by a cross-disciplinary team of data scientists, engineers, and sports researchers.
                    Our focus is to make predictive tooling accessible while maintaining institutional-grade rigor.
                </p>
            </section> */}

            <TeamSection />
        </div>
    );
};

export default AboutUs;

