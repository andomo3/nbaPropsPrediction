import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link, Outlet } from 'react-router-dom';
import logo from '../assets/perchave_final.png';

const Layout = () => {
    const [isNavHovered, setIsNavHovered] = useState(false);

    return (
        <div className="min-h-screen bg-zinc-950 text-white relative selection:bg-electric-blue/30 selection:text-white overflow-hidden font-sans">

            {/* Ambient Background Lights */}
            <div className="fixed inset-0 z-0 pointer-events-none">
                <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-electric-blue/10 blur-[120px]" />
                <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-neon-green/5 blur-[120px]" />
                <div className="absolute top-[40%] left-[30%] w-[30%] h-[30%] rounded-full bg-indigo-500/5 blur-[100px] animate-pulse" />
            </div>

            {/* Grid Pattern Overlay */}
            <div className="fixed inset-0 z-0 opacity-[0.03] pointer-events-none" style={{
                backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
                backgroundSize: '40px 40px'
            }}></div>

            {/* Navigation */}
            <nav className="fixed top-0 left-0 w-full z-40 flex items-center justify-between p-8">
                <Link to="/" className="cursor-pointer block transition-transform hover:scale-105 active:scale-95 duration-300">
                    <img src={logo} alt="Prop-Predictor Logo" className="h-[54px] w-auto opacity-90" />
                </Link>

                <div className="flex items-center gap-8">
                    <Link to="/overview" className="text-sm font-medium text-gray-300 hover:text-white transition-colors uppercase tracking-widest hover:tracking-[0.15em] duration-300">Overview</Link>
                    <Link to="/about" className="text-sm font-medium text-gray-300 hover:text-white transition-colors uppercase tracking-widest hover:tracking-[0.15em] duration-300">About Us</Link>
                </div>
            </nav>

            {/* Page Content */}
            <Outlet />
        </div>
    );
};

export default Layout;
