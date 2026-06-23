import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';

export default function SectionCard({
    title,
    subtitle,
    className = '',
    children,
    collapsible = false,
    defaultOpen = true,
}) {
    const [open, setOpen] = useState(defaultOpen);

    const header = title && (
        <div
            className={`flex items-start justify-between px-8 pt-7 pb-5 ${collapsible ? 'cursor-pointer select-none' : ''}`}
            onClick={collapsible ? () => setOpen(o => !o) : undefined}
        >
            <div>
                <h3 className="text-sm font-semibold tracking-wide text-foreground">{title}</h3>
                {subtitle && (
                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{subtitle}</p>
                )}
            </div>
            {collapsible && (
                <ChevronDown
                    className={`w-4 h-4 mt-0.5 text-muted-foreground flex-shrink-0 transition-transform duration-300 ease-in-out ${open ? 'rotate-180' : ''}`}
                />
            )}
        </div>
    );

    const content = (
        <div className={title ? 'px-8 pb-8' : 'p-8'}>
            {children}
        </div>
    );

    return (
        <div className={`bg-card border border-border rounded-2xl mb-3 overflow-hidden ${className}`}>
            {header}

            {collapsible ? (
                <AnimatePresence initial={false}>
                    {open && (
                        <motion.div
                            key="body"
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                            style={{ overflow: 'hidden' }}
                        >
                            {content}
                        </motion.div>
                    )}
                </AnimatePresence>
            ) : (
                content
            )}
        </div>
    );
}
