import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './components/Home';
import Overview from './components/Overview';
import AboutUs from './components/AboutUs';
import DailyPicks from './components/DailyPicks';
import Backtest from './components/Backtest';
import SeasonReport from './components/SeasonReport';
import Leaderboard from './components/Leaderboard';
import Simulator from './components/Simulator';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="overview" element={<Overview />} />
          <Route path="about" element={<AboutUs />} />
          <Route path="picks" element={<DailyPicks />} />
          <Route path="backtest" element={<Backtest />} />
          <Route path="season-report" element={<SeasonReport />} />
          <Route path="leaderboard" element={<Leaderboard />} />
          <Route path="simulator" element={<Simulator />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
