import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import './CardNav.css';
import logo from '../assets/perchance_final.png';

const NAV_LINKS = [
    { label: 'Leaderboard', href: '/leaderboard' },
    { label: 'Intelligence', href: '/intelligence' },
];

const CardNav = ({ logoText = 'Perchance' }) => {
    const [open, setOpen] = useState(false);
    const location = useLocation();

    useEffect(() => setOpen(false), [location.pathname]);

    return (
        <header className="card-nav-container">
            <div className="card-nav-inner">
                <Link to="/" className="logo-link">
                    <img src={logo} alt={logoText} className="logo" />
                </Link>

                <nav className="nav-links" aria-label="Primary navigation">
                    {NAV_LINKS.map((link) => (
                        <Link
                            key={link.href}
                            to={link.href}
                            className={`nav-link${location.pathname === link.href ? ' nav-link-active' : ''}`}
                        >
                            {link.label}
                        </Link>
                    ))}
                    <Link to="/overview" className="nav-cta">
                        How It Works
                    </Link>
                </nav>

                <button
                    className={`nav-hamburger${open ? ' open' : ''}`}
                    onClick={() => setOpen((o) => !o)}
                    aria-label={open ? 'Close menu' : 'Open menu'}
                    aria-expanded={open}
                >
                    <span />
                    <span />
                </button>
            </div>

            <nav className={`nav-mobile${open ? ' open' : ''}`} aria-label="Mobile navigation">
                {NAV_LINKS.map((link) => (
                    <Link key={link.href} to={link.href} className="nav-mobile-link">
                        {link.label}
                    </Link>
                ))}
                <Link to="/overview" className="nav-mobile-link nav-mobile-cta">
                    How It Works
                </Link>
            </nav>
        </header>
    );
};

export default CardNav;
