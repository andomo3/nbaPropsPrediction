import React from 'react';

export default function Skeleton({ h = 'h-48' }) {
    return <div className={`animate-pulse bg-border rounded-xl ${h}`} />;
}
