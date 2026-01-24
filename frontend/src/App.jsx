import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { motion } from 'framer-motion';
import logo from './assets/perchave_final.png';
import Layout from './components/Layout';
import Home from './components/Home';
import Overview from './components/Overview';
import AboutUs from './components/AboutUs';

const IntroAnimation = ({ onComplete }) => {
  useEffect(() => {
    const timer = setTimeout(onComplete, 2500);
    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <motion.div
      className="fixed inset-0 z-50 bg-black flex flex-col items-center justify-center"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.8, ease: "easeInOut" } }}
    >
      <div className="relative">
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.3, 0.6, 0.3],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute inset-0 bg-electric-blue/30 blur-2xl rounded-full"
        />

        <motion.img
          src={logo}
          alt="Loading..."
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="w-32 h-auto relative z-10"
        />
      </div>

      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.5, duration: 0.5 }}
        className="mt-8 flex flex-col items-center gap-2"
      >
        <h2 className="text-2xl font-bold tracking-tighter text-white">
          PROP <span className="text-electric-blue">PREDICTOR</span>
        </h2>
        <div className="flex items-center gap-2 text-xs text-gray-500 font-mono tracking-widest uppercase">
          <motion.div
            animate={{ opacity: [0, 1, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, times: [0, 0.5, 1] }}
            className="w-2 h-2 bg-emerald-500 rounded-full"
          />
          Initializing Models...
        </div>
      </motion.div>
    </motion.div>
  );
};

function App() {
  const [showIntro, setShowIntro] = useState(false);

  useEffect(() => {
    const hasVisited = sessionStorage.getItem('hasVisited');
    if (!hasVisited) {
      setShowIntro(true);
      sessionStorage.setItem('hasVisited', 'true');
    }
  }, []);

  if (showIntro) {
    return <IntroAnimation onComplete={() => setShowIntro(false)} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="overview" element={<Overview />} />
          <Route path="about" element={<AboutUs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
