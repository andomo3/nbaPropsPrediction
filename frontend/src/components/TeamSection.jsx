import React from 'react';
import Carousel from './Carousel';
import abbaFounder from '../assets/Abba_founder.png';
import husaamFounder from '../assets/Husaam_founder.png';
import patelFounder from '../assets/Patel_founder.png';

const TEAM = [
    {
        name: 'Abba Ndomo',
        role: 'Founder · Data Engineering & Backend',
        bio: 'Shapes the modeling strategy and feature pipelines that drive PropEdge.',
        image: abbaFounder,
    },
    {
        name: 'Husaam Idris',
        role: 'Founder · Machine Learning Developer',
        bio: 'Owns training infrastructure, monitoring, and model evaluation workflows.',
        image: husaamFounder,
    },
    {
        name: 'Patel',
        role: 'Founder · Frontend',
        bio: 'Designs the APIs and data ingestion services that fuel predictions.',
        image: patelFounder,
    },
];

const TeamSection = () => {
    return (
        <section className="mb-20 md:mb-24">
            <div className="mb-8">
                <h3 className="text-3xl md:text-4xl font-bold text-foreground">Meet the Team</h3>
                <p className="text-lg text-muted-foreground leading-relaxed">
                    A focused group of engineers and analysts building a smarter props engine.
                </p>
            </div>
            <div className="flex justify-center">
                <Carousel
                    items={TEAM.map((member, index) => ({
                        ...member,
                        id: index,
                        initials: member.name
                            .split(' ')
                            .map((part) => part[0])
                            .join('')
                            .slice(0, 2)
                            .toUpperCase(),
                    }))}
                    baseWidth={420}
                    autoplay
                    autoplayDelay={3500}
                    pauseOnHover
                    loop
                />
            </div>
        </section>
    );
};

export default TeamSection;
