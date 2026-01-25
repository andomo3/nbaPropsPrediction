import React from 'react';
import { motion } from 'framer-motion';
import TextType from './TextType';

const AboutUs = () => {
    return (
        <div className="max-w-4xl mx-auto px-4 py-40 relative z-10">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-center mb-12"
            >
                <TextType
                    as="h1"
                    text="Who we are"
                    typingSpeed={60}
                    pauseDuration={1200}
                    deletingSpeed={40}
                    loop={false}
                    showCursor={false}
                    className="text-4xl md:text-5xl font-bold tracking-tighter mb-4 bg-gradient-to-b from-white via-white to-gray-500 bg-clip-text text-transparent"
                />
                <p className="text-lg text-gray-400 max-w-2xl mx-auto leading-relaxed">
                    The team behind the predictions.
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
                        Founded by data scientists and sports enthusiasts, we set out to solve a simple problem: there was too much noise and not enough signal in the sports betting world.
                    </p>
                    <p>
                        We believe in transparency and accuracy. Our mission is to democratize access to institutional-grade sports analytics.
                    </p>

                    <div className="mt-8 border-t border-white/5 pt-8">
                        <h3 className="text-xl font-bold text-white mb-4">Our Core Values</h3>
                        <ul className="grid md:grid-cols-3 gap-4">
                            <li className="bg-black/20 p-4 rounded-xl border border-white/5 text-center">
                                <span className="block text-electric-blue font-bold mb-1">Precision</span>
                                <span className="text-sm">Data-driven accuracy above all else.</span>
                            </li>
                            <li className="bg-black/20 p-4 rounded-xl border border-white/5 text-center">
                                <span className="block text-neon-green font-bold mb-1">Integrity</span>
                                <span className="text-sm">Honest tracking of our model's performance.</span>
                            </li>
                            <li className="bg-black/20 p-4 rounded-xl border border-white/5 text-center">
                                <span className="block text-indigo-400 font-bold mb-1">Innovation</span>
                                <span className="text-sm">Constantly refining our algorithms.</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </motion.div>
        </div>
    );
};

export default AboutUs;
