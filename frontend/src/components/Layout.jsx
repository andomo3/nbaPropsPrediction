import React, { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import CardNav from './CardNav';

const ROUTE_TITLES = {
    '/': 'Perchance — NBA Player Prop Intelligence',
    '/overview': 'How It Works — Perchance',
    '/about': 'About Us — Perchance',
    '/picks': "Today's Picks — Perchance",
    '/backtest': 'Backtesting — Perchance',
    '/season-report': 'Season Report Card — Perchance',
    '/leaderboard': 'Predictability Leaderboard — Perchance',
    '/leaderboard-comparison': 'Cross-Season Comparison — Perchance',
    '/simulator': 'Season Simulator — Perchance',
    '/intelligence': 'Player Intelligence — Perchance',
};

const Layout = () => {
    const { pathname } = useLocation();

    useEffect(() => {
        document.title = ROUTE_TITLES[pathname] ?? 'Perchance — NBA Player Prop Intelligence';
    }, [pathname]);

    return (
        <div className="min-h-screen bg-background">
            <CardNav logoText="Perchance" />
            <main className="container mx-auto px-4 pt-20 pb-16">
                <Outlet />
            </main>
        </div>
    );
};

export default Layout;
