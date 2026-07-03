import React, { useState, useEffect } from 'react';
import SeasonReport from './SeasonReport';
import { FadeIn, PageTransition } from './page-transition';

const TEXT1 = 'Stop guessing.';
const TEXT2 = 'Start reading.';

// phases: idle → l1 → indent → l2 → done
function HeroTypewriter() {
    const [phase, setPhase]               = useState('idle');
    const [n1, setN1]                     = useState(0);
    const [n2, setN2]                     = useState(0);
    const [indentActive, setIndentActive] = useState(false);

    // Initial kick-off
    useEffect(() => {
        // Reduced motion: skip the typewriter entirely and show the finished hero.
        if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
            setN1(TEXT1.length);
            setN2(TEXT2.length);
            setIndentActive(true);
            setPhase('done');
            return undefined;
        }
        const t = setTimeout(() => setPhase('l1'), 400);
        return () => clearTimeout(t);
    }, []);

    // Main sequencer
    useEffect(() => {
        let t;
        if (phase === 'l1') {
            if (n1 < TEXT1.length) {
                t = setTimeout(() => setN1(n1 + 1), 55);
            } else {
                // Pause before "pressing Enter"
                t = setTimeout(() => setPhase('indent'), 380);
            }
        } else if (phase === 'indent') {
            // One frame delay so the DOM renders line 2 at flex-grow:0 first,
            // then flip indentActive → CSS transition plays from 0 → 1
            const activate = setTimeout(() => setIndentActive(true), 16);
            // Total indent phase: 450ms transition + 250ms pause at right edge
            t = setTimeout(() => setPhase('l2'), 700);
            return () => { clearTimeout(activate); clearTimeout(t); };
        } else if (phase === 'l2') {
            if (n2 < TEXT2.length) {
                t = setTimeout(() => setN2(n2 + 1), 55);
            } else {
                setPhase('done');
            }
        }
        return () => clearTimeout(t);
    }, [phase, n1, n2]);

    const line2Visible = phase !== 'idle' && phase !== 'l1';

    return (
        <div className="text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.25]">

            {/* Line 1 — left-aligned, red */}
            <div>
                <span className="text-red-400">{TEXT1.slice(0, n1)}</span>
                {phase === 'l1' && <span className="text-red-400 hero-cursor">|</span>}
            </div>

            {/* Line 2 — cursor slides to right edge, then types right-aligned */}
            {line2Visible && (
                <div style={{ display: 'flex', alignItems: 'baseline' }}>
                    {/* Spacer: transitions from 0 → full width, pushing cursor+text to right */}
                    <div style={{
                        flexGrow: indentActive ? 1 : 0,
                        transition: 'flex-grow 0.45s ease-out',
                        minWidth: 0,
                    }} />
                    <span className="text-primary">{TEXT2.slice(0, n2)}</span>
                    <span className={`text-primary ${phase === 'done' ? 'hero-cursor-blink' : 'hero-cursor'}`}>|</span>
                </div>
            )}

        </div>
    );
}

export default function Home() {
    return (
        <PageTransition>
            <div className="w-full">
                <FadeIn direction="none">
                    <section className="mt-8 mb-16 w-full max-w-4xl mx-auto">
                        <p className="text-xs font-semibold tracking-widest uppercase text-muted-foreground mb-6">
                            Perchance · 2025–26 Season
                        </p>
                        <HeroTypewriter />
                        <p className="text-lg text-muted-foreground max-w-md leading-relaxed mt-8">
                            Player intelligence — statistical edge, behavioral signal, and model reliability for every line.
                        </p>
                    </section>
                </FadeIn>

                <FadeIn delay={150}>
                    <section className="w-full">
                        <SeasonReport />
                    </section>
                </FadeIn>
            </div>
        </PageTransition>
    );
}
