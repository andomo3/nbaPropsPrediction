import React from 'react';

const TeamCard = ({ name, role, bio }) => {
    return (
        <div className="rounded-2xl border border-border bg-card p-6 md:p-8 text-center">
            <div className="mx-auto mb-4 h-20 w-20 rounded-xl bg-primary/10 border border-primary/20" />
            <h4 className="text-xl font-semibold text-foreground">{name}</h4>
            <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium mt-1">{role}</p>
            <p className="mt-3 text-sm text-muted-foreground">{bio}</p>
        </div>
    );
};

export default TeamCard;
