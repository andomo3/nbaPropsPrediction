import React from 'react';
import SeasonReport from './SeasonReport';
import TeamSection from './TeamSection';
import TextType from './TextType';
import { FadeIn, PageTransition } from './page-transition';

const Home = () => {
    return (
        <PageTransition>
            <div>
                <FadeIn direction="none">
                    <section className="mt-12 mb-20 md:mb-28 text-center max-w-4xl mx-auto">
                        <TextType
                            text="Season Report Card"
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
                            See how the model performed game-by-game for top NBA players over a full season.
                        </p>
                    </section>
                </FadeIn>

                <FadeIn delay={150}>
                    <section className="mb-20 md:mb-24 w-full">
                        <SeasonReport />
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
