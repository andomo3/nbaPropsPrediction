import React from 'react';
import { Link, NavLink } from 'react-router-dom';
import { Activity } from 'lucide-react';

const Header = () => {
    return (
        <header className="border-b border-border/50 sticky top-0 z-50 backdrop-blur-md bg-background/80">
            <div className="container mx-auto px-4 h-16 flex items-center justify-between">
                <Link to="/about" className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                        <Activity className="h-4 w-4 text-primary" />
                    </div>
                    <span className="text-lg font-semibold text-foreground tracking-tight">PropEdge</span>
                </Link>
                <nav className="hidden md:flex items-center gap-8">
                    <NavLink
                        to="/#predictions"
                        className={({ isActive }) => `text-sm text-muted-foreground hover:text-foreground transition-colors`}
                    >
                        Predictions
                    </NavLink>
                    <NavLink
                        to="/overview"
                        className={({ isActive }) => `text-sm text-muted-foreground hover:text-foreground transition-colors`}
                    >
                        How It Works
                    </NavLink>
                    <NavLink
                        to="/about"
                        className={({ isActive }) => `text-sm text-muted-foreground hover:text-foreground transition-colors`}
                    >
                        About Us
                    </NavLink>
                </nav>
            </div>
        </header>
    );
};

export default Header;
