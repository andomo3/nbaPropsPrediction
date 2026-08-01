import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Board from './components/Board';
import Overview from './components/Overview';
import AboutUs from './components/AboutUs';
import Backtest from './components/Backtest';
import SeasonReport from './components/SeasonReport';
import Leaderboard from './components/Leaderboard';
import LeaderboardComparison from './components/LeaderboardComparison';
import Simulator from './components/Simulator';
import PlayerIntelligence from './components/PlayerIntelligence';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Board />} />
          <Route path="overview" element={<Overview />} />
          <Route path="about" element={<AboutUs />} />
          {/* The board is the home page now — keep the old picks URL working. */}
          <Route path="picks" element={<Navigate to="/" replace />} />
          <Route path="backtest" element={<Backtest />} />
          <Route path="season-report" element={<SeasonReport />} />
          <Route path="leaderboard" element={<Leaderboard />} />
          <Route path="leaderboard-comparison" element={<LeaderboardComparison />} />
          <Route path="simulator" element={<Simulator />} />
          <Route path="intelligence" element={<PlayerIntelligence />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
