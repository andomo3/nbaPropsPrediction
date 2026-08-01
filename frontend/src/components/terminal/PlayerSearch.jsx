import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PLAYERS } from '../../utils/constants';

/**
 * ⌘K player search. Opens on Cmd/Ctrl+K or by clicking the nav affordance,
 * and jumps straight to that player's Intelligence page.
 */
export default function PlayerSearch({ open, onClose }) {
    const navigate = useNavigate();
    const inputRef = useRef(null);
    const [query, setQuery] = useState('');
    const [cursor, setCursor] = useState(0);

    const matches = useMemo(() => {
        const q = query.trim().toLowerCase();
        if (!q) return PLAYERS;
        return PLAYERS.filter((p) => p.toLowerCase().includes(q));
    }, [query]);

    useEffect(() => {
        if (open) {
            setQuery('');
            setCursor(0);
            // Focus after the dialog paints, otherwise Safari drops it.
            const t = setTimeout(() => inputRef.current?.focus(), 0);
            return () => clearTimeout(t);
        }
        return undefined;
    }, [open]);

    useEffect(() => setCursor(0), [query]);

    if (!open) return null;

    const go = (player) => {
        navigate(`/intelligence?player_name=${encodeURIComponent(player)}&stat=pts`);
        onClose();
    };

    const onKeyDown = (e) => {
        if (e.key === 'Escape') {
            onClose();
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            setCursor((c) => Math.min(c + 1, matches.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setCursor((c) => Math.max(c - 1, 0));
        } else if (e.key === 'Enter' && matches[cursor]) {
            e.preventDefault();
            go(matches[cursor]);
        }
    };

    return (
        <div
            className="fixed inset-0 z-[100] flex items-start justify-center px-4 pt-[12vh] bg-black/70 animate-fade-in"
            onClick={onClose}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-label="Search players"
                className="w-full max-w-lg bg-[#101012] border border-hair-control rounded-lg overflow-hidden animate-fade-up"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center gap-3 px-4 h-12 border-b border-hair">
                    <span className="eyebrow">FIND</span>
                    <input
                        ref={inputRef}
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={onKeyDown}
                        placeholder="Search players"
                        /* The dialog only opens focused on this field, so the
                           global focus ring would be permanent noise here. */
                        className="flex-1 bg-transparent text-[15px] text-ink-1 placeholder:text-ink-8 outline-none focus-visible:outline-none"
                    />
                    <kbd className="num text-[11px] font-medium text-ink-9 border border-hair-control rounded px-1.5 py-0.5">
                        ESC
                    </kbd>
                </div>

                <div className="max-h-[320px] overflow-y-auto py-1">
                    {matches.length === 0 && (
                        <p className="px-4 py-6 text-sm text-ink-7 text-center">
                            No player matches “{query}”.
                        </p>
                    )}
                    {matches.map((p, i) => (
                        <button
                            key={p}
                            type="button"
                            onMouseEnter={() => setCursor(i)}
                            onClick={() => go(p)}
                            className={`w-full flex items-center justify-between gap-4 px-4 py-2.5 text-left text-[15px] transition-colors ${
                                i === cursor ? 'bg-acid-wash text-ink-1' : 'text-ink-3 hover:text-ink-1'
                            }`}
                        >
                            <span>{p}</span>
                            {i === cursor && (
                                <span className="num text-[11px] text-acid">INTELLIGENCE →</span>
                            )}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
