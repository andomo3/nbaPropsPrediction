import React from 'react';
import { Outlet } from 'react-router-dom';
import CardNav from './CardNav';

const Layout = () => {
    return (
        <div className="min-h-screen bg-background relative">
            <CardNav
                logoText="PropEdge"
                items={[
                    {
                        label: 'Predictions',
                        links: [
                            { label: 'Scenario', href: '/#predictions' },
                            { label: 'Outputs', href: '/overview' },
                        ],
                    },
                    {
                        label: 'Tools',
                        links: [
                            { label: 'Daily Picks', href: '/picks' },
                            { label: 'Backtesting', href: '/backtest' },
                            { label: 'Season Report', href: '/season-report' },
                        ],
                    },
                    {
                        label: 'Insights',
                        links: [
                            { label: 'How It Works', href: '/overview' },
                            { label: 'Model Notes', href: '/overview' },
                        ],
                    },
                    {
                        label: 'About',
                        links: [
                            { label: 'Team', href: '/about' },
                            { label: 'Contact', href: '/about' },
                        ],
                    },
                ]}
            />
            <main className="container mx-auto px-4 py-20 md:py-32">
                <div className="w-full flex flex-col items-center text-center mt-12 md:mt-16">
                    <Outlet />
                </div>
            </main>
        </div>
    );
};

export default Layout;
