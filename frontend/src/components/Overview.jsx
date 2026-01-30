import React from 'react';
import HowItWorks from './HowItWorks';
import { PageTransition } from './page-transition';

const Overview = () => {
    return (
        <PageTransition>
            <div>
                <HowItWorks />
            </div>
        </PageTransition>
    );
};

export default Overview;
