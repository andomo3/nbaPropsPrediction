import React from 'react';

export default function InsightText({ text }) {
    if (!text) return null;
    return (
        <p
            className="text-sm text-muted-foreground mt-4 leading-relaxed"
            dangerouslySetInnerHTML={{
                __html: text.replace(/\*\*(.*?)\*\*/g, '<strong class="text-foreground">$1</strong>'),
            }}
        />
    );
}
