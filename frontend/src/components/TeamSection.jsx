import React from 'react';
import Carousel from './Carousel';

const TEAM = [
    {
        name: 'Alex Johnson',
        role: 'Founder · Data Science',
        bio: 'Shapes the modeling strategy and feature pipelines that drive PropEdge.',
        image: 'https://placehold.co/480x320/png?text=Alex+Johnson',
    },
    {
        name: 'Maya Chen',
        role: 'Founder · ML Engineering',
        bio: 'Owns training infrastructure, monitoring, and model evaluation workflows.',
        image: 'https://placehold.co/480x320/png?text=Maya+Chen',
    },
    {
        name: 'Jordan Lee',
        role: 'Founder · Backend',
        bio: 'Designs the APIs and data ingestion services that fuel predictions.',
        image: 'https://placehold.co/480x320/png?text=Jordan+Lee',
    },
];

const TeamSection = () => {
    return (
        <section className="mb-32">
            <div className="mb-10">
                <h3 className="text-2xl md:text-3xl font-bold text-foreground">Meet the Team</h3>
                <p className="text-base text-muted-foreground leading-relaxed">
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
                    baseWidth={360}
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
