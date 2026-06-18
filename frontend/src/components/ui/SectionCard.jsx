import React from 'react';

export default function SectionCard({ title, subtitle, className = '', children }) {
    return (
        <div className={`bg-card border border-border rounded-2xl p-6 mb-4 ${className}`}>
            {title && (
                <div className="mb-4">
                    <h3 className="text-base font-semibold text-foreground">{title}</h3>
                    {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
                </div>
            )}
            {children}
        </div>
    );
}
