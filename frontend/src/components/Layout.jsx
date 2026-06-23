import React from 'react';
import { Outlet } from 'react-router-dom';
import CardNav from './CardNav';

const Layout = () => {
    return (
        <div className="min-h-screen bg-background">
            <CardNav logoText="perChance" />
            <main className="container mx-auto px-4 pt-20 pb-16">
                <Outlet />
            </main>
        </div>
    );
};

export default Layout;
