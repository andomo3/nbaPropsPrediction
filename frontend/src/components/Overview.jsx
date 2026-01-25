import React from 'react';
import { motion } from 'framer-motion';
import TextType from './TextType';

const Overview = () => {
    return (
        <div className="max-w-4xl mx-auto px-4 py-40 relative z-10">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center mb-12"
            >
                <TextType
                    as="h1"
                    text="Platform Overview"
                    typingSpeed={60}
                    pauseDuration={1200}
                    deletingSpeed={40}
                    loop={false}
                    showCursor={false}
                    className="text-4xl md:text-5xl font-bold tracking-tighter mb-4 bg-gradient-to-b from-white via-white to-gray-500 bg-clip-text text-transparent"
                />
                <p className="text-lg text-gray-400 max-w-2xl mx-auto leading-relaxed">
                    Understanding how our predictive models work.
                </p>
            </motion.div>

            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1 }}
                className="w-full backdrop-blur-xl shadow-xl rounded-2xl p-8 bg-zinc-900/20 border border-white/5"
            >
                <div className="space-y-6 text-gray-300">
                    <p>
                        Prop-Predictor is a state-of-the-art sports analytics platform designed to give bettors an edge. We leverage machine learning to analyze historical player performance, matchup data, and real-time game conditions.
                    </p>

                    <div className="grid md:grid-cols-2 gap-6 mt-8">
                        <div className="bg-black/20 p-6 rounded-xl border border-white/5">
                            <h3 className="text-xl font-bold text-white mb-2">Data Aggregation</h3>
                            <p className="text-sm">We process thousands of data points from every game, including advanced metrics that go beyond the box score.</p>
                        </div>
                        <div className="bg-black/20 p-6 rounded-xl border border-white/5">
                            <h3 className="text-xl font-bold text-white mb-2">Predictive Modeling</h3>
                            <p className="text-sm">Our proprietary algorithms calculate hit probabilities for player props, identifying value where the sportsbooks might have missed it.</p>
                        </div>
                    </div>
                </div>
            </motion.div>
        </div>
    );
};

export default Overview;
