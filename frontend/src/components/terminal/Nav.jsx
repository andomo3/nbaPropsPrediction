import React, { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import PlayerSearch from './PlayerSearch';

const NAV_LINKS = [
    { label: 'Board', to: '/' },
    { label: 'Report Card', to: '/season-report' },
    { label: 'Intelligence', to: '/intelligence' },
    { label: 'Leaderboard', to: '/leaderboard' },
];

const SECONDARY_LINKS = [
    { label: 'How it works', to: '/overview' },
    { label: 'Cross-season', to: '/leaderboard-comparison' },
    { label: 'Simulator', to: '/simulator' },
    { label: 'About', to: '/about' },
];

function Wordmark() {
    return (
        <span className="text-[17px] font-bold tracking-[-0.01em] text-ink-1">
            Per<span className="text-acid">Chance</span>
        </span>
    );
}

export default function Nav() {
    const { pathname } = useLocation();
    const [searchOpen, setSearchOpen] = useState(false);
    const [menuOpen, setMenuOpen] = useState(false);
    const [isMac, setIsMac] = useState(false);

    useEffect(() => {
        setIsMac(/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent));
    }, []);

    useEffect(() => setMenuOpen(false), [pathname]);

    useEffect(() => {
        const onKey = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                setSearchOpen(true);
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, []);

    return (
        <>
            <header className="sticky top-0 z-50 h-nav bg-background border-b border-hair">
                <div className="h-full px-5 sm:px-gutter flex items-center justify-between gap-4">
                    <div className="flex items-center gap-6 lg:gap-9 min-w-0">
                        <Link to="/" aria-label="PerChance home" className="shrink-0">
                            <Wordmark />
                        </Link>

                        <nav
                            className="hidden md:flex items-center gap-[26px] h-nav"
                            aria-label="Primary"
                        >
                            {NAV_LINKS.map(({ label, to }) => (
                                <NavLink
                                    key={to}
                                    to={to}
                                    end={to === '/'}
                                    className={({ isActive }) =>
                                        `h-full flex items-center text-sm font-medium transition-colors ${
                                            isActive
                                                ? 'text-ink-1 shadow-[inset_0_-2px_0_var(--acid)]'
                                                : 'text-ink-7 hover:text-ink-3'
                                        }`
                                    }
                                >
                                    {label}
                                </NavLink>
                            ))}
                        </nav>
                    </div>

                    <div className="flex items-center gap-2.5 shrink-0">
                        <button
                            type="button"
                            onClick={() => setSearchOpen(true)}
                            className="flex items-center gap-2 h-8 px-3 border border-hair-control rounded-lg text-[13px] text-ink-5 hover:text-ink-3 hover:border-hair-rule transition-colors"
                        >
                            <span className="hidden sm:inline">Search players</span>
                            <span className="sm:hidden">Search</span>
                            <kbd className="num text-[11px] font-medium text-ink-9 border border-hair-control rounded px-1.5 leading-[15px]">
                                {isMac ? '⌘K' : 'Ctrl K'}
                            </kbd>
                        </button>

                        <span className="hidden lg:inline num text-[11px] font-medium tracking-eyebrow text-ink-8">
                            2025–26
                        </span>

                        <button
                            type="button"
                            className="md:hidden w-8 h-8 flex flex-col items-center justify-center gap-[5px]"
                            onClick={() => setMenuOpen((o) => !o)}
                            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
                            aria-expanded={menuOpen}
                        >
                            <span
                                className={`block w-4 h-px bg-ink-3 transition-transform ${
                                    menuOpen ? 'translate-y-[3px] rotate-45' : ''
                                }`}
                            />
                            <span
                                className={`block w-4 h-px bg-ink-3 transition-transform ${
                                    menuOpen ? '-translate-y-[3px] -rotate-45' : ''
                                }`}
                            />
                        </button>
                    </div>
                </div>

                {menuOpen && (
                    <nav
                        className="md:hidden bg-background border-b border-hair"
                        aria-label="Mobile navigation"
                    >
                        {NAV_LINKS.map(({ label, to }) => (
                            <NavLink
                                key={to}
                                to={to}
                                end={to === '/'}
                                className={({ isActive }) =>
                                    `block px-5 py-3 text-sm font-medium border-b border-hair-soft ${
                                        isActive ? 'text-acid' : 'text-ink-3'
                                    }`
                                }
                            >
                                {label}
                            </NavLink>
                        ))}
                        <div className="px-5 py-3 flex flex-wrap gap-x-5 gap-y-2">
                            {SECONDARY_LINKS.map(({ label, to }) => (
                                <Link key={to} to={to} className="text-[13px] text-ink-7">
                                    {label}
                                </Link>
                            ))}
                        </div>
                    </nav>
                )}
            </header>

            <PlayerSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
        </>
    );
}

export { SECONDARY_LINKS };
