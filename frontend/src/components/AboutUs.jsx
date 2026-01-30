import React from 'react';
import TextType from './TextType';
import TeamSection from './TeamSection';
import HowItWorks from './HowItWorks';
import { FadeIn, PageTransition } from './page-transition';

const AboutUs = () => {
    return (
        <PageTransition>
            <div>
                <FadeIn direction="none">
                    <div className="text-center mb-20 md:mb-28 max-w-4xl mx-auto">
                        <TextType
                            text="About Us"
                            as="h1"
                            className="text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-foreground text-balance"
                            typingSpeed={60}
                            pauseDuration={1200}
                            deletingSpeed={40}
                            loop={false}
                            showCursor={false}
                            cursorCharacter="|"
                        />
                        <p className="text-xl md:text-2xl text-muted-foreground max-w-2xl mx-auto text-pretty leading-relaxed mt-6">
                            We build responsible, data-driven NBA props tooling for serious bettors and analysts.
                        </p>
                    </div>
                </FadeIn>

                <FadeIn delay={150}>
                    <section className="grid gap-8 md:gap-10 md:grid-cols-3 mb-20 md:mb-24">
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
                            <div key={card.title} className="rounded-3xl border border-border bg-card p-8 md:p-10 lg:p-12">
                                <h3 className="text-2xl font-semibold text-foreground">{card.title}</h3>
                                <p className="mt-3 text-base text-muted-foreground leading-relaxed">{card.body}</p>
                            </div>
                        ))}
                    </section>
                </FadeIn>

                <FadeIn delay={250}>
                    <HowItWorks />
                </FadeIn>

                <FadeIn delay={350}>
                    <TeamSection />
                </FadeIn>
            </div>
        </PageTransition>
    );
};

export default AboutUs;
