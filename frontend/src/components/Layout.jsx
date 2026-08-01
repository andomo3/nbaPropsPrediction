import React, { useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import Nav, { SECONDARY_LINKS } from './terminal/Nav';
import { GUTTER } from './terminal/ui';

const ROUTE_TITLES = {
    '/': "Tonight's Board — Perchance",
    '/overview': 'How It Works — Perchance',
    '/about': 'About Us — Perchance',
    '/backtest': 'Backtesting — Perchance',
    '/season-report': 'Season Report Card — Perchance',
    '/leaderboard': 'Predictability Leaderboard — Perchance',
    '/leaderboard-comparison': 'Cross-Season Comparison — Perchance',
    '/simulator': 'Season Simulator — Perchance',
    '/intelligence': 'Player Intelligence — Perchance',
};

function Footer() {
    return (
        <footer className={`${GUTTER} py-7 border-t border-hair flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between`}>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
                {SECONDARY_LINKS.map(({ label, to }) => (
                    <Link
                        key={to}
                        to={to}
                        className="text-[13px] text-ink-7 hover:text-ink-3 transition-colors"
                    >
                        {label}
                    </Link>
                ))}
            </div>
            <p className="text-xs text-ink-9">
                Modelled output for research. Not betting advice.
            </p>
        </footer>
    );
}

const Layout = () => {
    const { pathname } = useLocation();

    useEffect(() => {
        document.title = ROUTE_TITLES[pathname] ?? 'Perchance — NBA Player Prop Intelligence';
    }, [pathname]);

    return (
        <div className="min-h-screen bg-background flex flex-col">
            <Nav />
            <main className="flex-1">
                <Outlet />
            </main>
            <Footer />
        </div>
    );
};

export default Layout;
