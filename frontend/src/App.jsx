import React, { useState, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, TrendingUp, Activity, Target, Shield, Award, BarChart3, Clock, Users, Zap, Check } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

const STATS = [
  { id: 'PTS', label: 'Points', icon: '🎯' },
  { id: 'REB', label: 'Rebounds', icon: '🏀' },
  { id: 'AST', label: 'Assists', icon: '⚡' },
  { id: 'STL', label: 'Steals', icon: '🔥' },
  { id: 'BLK', label: 'Blocks', icon: '🛡️' },
  { id: '3PM', label: '3-Pointers', icon: '💫' },
];

const STAT_SUFFIX = {
  PTS: 'pts',
  REB: 'reb',
  AST: 'ast',
  STL: 'stl',
  BLK: 'blk',
  '3PM': '3pm',
};

const PERIODS = [1, 2, 3, 4];

const MOCK_PLAYERS = [
  'LeBron James', 'Stephen Curry', 'Kevin Durant', 'Giannis Antetokounmpo',
  'Luka Doncic', 'Jayson Tatum', 'Joel Embiid', 'Nikola Jokic',
  'Devin Booker', 'Damian Lillard', 'Anthony Edwards', 'Shai Gilgeous-Alexander'
];

function App() {
  const [playerName, setPlayerName] = useState('');
  const [selectedStat, setSelectedStat] = useState('PTS');
  const [lineValue, setLineValue] = useState('');
  const [period, setPeriod] = useState(1);
  const [opponentTeam, setOpponentTeam] = useState('');
  const [isHome, setIsHome] = useState(true);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [searchSuggestions, setSearchSuggestions] = useState(false);

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setSearchSuggestions(false);
    window.addEventListener('click', handleClickOutside);
    return () => window.removeEventListener('click', handleClickOutside);
  }, []);

  const filteredPlayers = useMemo(() => {
    if (!playerName.trim()) return [];
    return MOCK_PLAYERS.filter(p =>
      p.toLowerCase().includes(playerName.toLowerCase())
    ).slice(0, 5);
  }, [playerName]);

  const generateScenarioPrediction = (userLine) => {
    // Generate mock historical data (last 10 games)
    const historicalData = Array.from({ length: 10 }, (_, i) => ({
      game: i + 1,
      value: Math.floor(Math.random() * 20) + 15,
    }));

    const avgValue = historicalData.reduce((sum, d) => sum + d.value, 0) / historicalData.length;
    const projected = avgValue + (Math.random() * 6 - 3);
    const clampedProjected = Math.max(0, Number(projected.toFixed(1)));

    const zScore = (clampedProjected - userLine) / 4;
    const probOver = 1 / (1 + Math.exp(-zScore));
    const probUnder = 1 - probOver;
    const recommendation =
      probOver >= 0.55 ? 'Lean Over' : probOver <= 0.45 ? 'Lean Under' : 'Toss-up';

    return {
      historicalData,
      userLine,
      projected: clampedProjected,
      probOver,
      probUnder,
      recommendation,
    };
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!playerName.trim()) return;
    if (lineValue === '' || Number.isNaN(Number(lineValue))) return;

    setIsLoading(true);
    // Simulate API call
    setTimeout(() => {
      const lineNumber = Number(lineValue);
      const prediction = generateScenarioPrediction(lineNumber);
      setResult({
        playerName: playerName.trim(),
        stat: STATS.find(s => s.id === selectedStat)?.label || selectedStat,
        statSuffix: STAT_SUFFIX[selectedStat] || selectedStat.toLowerCase(),
        period,
        line: lineNumber,
        opponentTeam: opponentTeam.trim(),
        isHome,
        hitChance: Math.round(prediction.probOver * 100),
        missChance: Math.round(prediction.probUnder * 100),
        ...prediction
      });
      setIsLoading(false);
    }, 800);
  };

  const ConfidenceDial = ({ percentage, size = 120 }) => {
    const circumference = 2 * Math.PI * (size / 2 - 10);
    const offset = circumference - (percentage / 100) * circumference;

    return (
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="transform -rotate-90 w-full h-full">
          <circle
            cx="50%"
            cy="50%"
            r="40%"
            stroke="rgba(255, 255, 255, 0.05)"
            strokeWidth="8"
            fill="none"
          />
          <circle
            cx="50%"
            cy="50%"
            r="40%"
            stroke="url(#gradient)"
            strokeWidth="8"
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-1000 ease-out"
          />
          <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#00D9FF" />
              <stop offset="100%" stopColor="#00FF88" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-white tracking-tighter">{percentage}%</span>
          <span className="text-[10px] uppercase tracking-widest text-gray-500 font-medium">Confidence</span>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white relative selection:bg-electric-blue/30 selection:text-white overflow-hidden">

      {/* Ambient Background Lights */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-electric-blue/10 blur-[120px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-neon-green/5 blur-[120px]" />
        <div className="absolute top-[40%] left-[30%] w-[30%] h-[30%] rounded-full bg-indigo-500/5 blur-[100px] animate-pulse" />
      </div>

      {/* Grid Pattern Overlay */}
      <div className="fixed inset-0 z-0 opacity-[0.03] pointer-events-none" style={{
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
        backgroundSize: '40px 40px'
      }}></div>

      {/* Top Navigation */}
      <div className="z-50 relative border-b border-white/5 bg-zinc-950/50 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="absolute inset-0 bg-electric-blue/20 blur-lg rounded-full"></div>
            </div>
            <span className="font-bold tracking-tight text-lg">Prop-Predictor</span>
          </div>
          <div className="flex items-center gap-6 text-sm font-medium">
            <div className="hidden md:flex items-center gap-2 text-emerald-400 bg-emerald-400/10 px-3 py-1 rounded-full border border-emerald-400/20">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              System Online
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-12 relative z-10 flex flex-col items-center">

        {/* Main Hero Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12 w-full max-w-3xl"
        >
          {/* <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-gray-400 mb-6">
            <Zap className="w-3 h-3 text-electric-blue" />
            <span>Powered by Advanced AI Models</span>
          </div> */}
          <h1 className="text-5xl md:text-7xl font-bold tracking-tighter mb-6 bg-gradient-to-b from-white via-white to-gray-500 bg-clip-text text-transparent">
            Predict the Future.
          </h1>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto leading-relaxed">
            Wouldn't you like to know?
          </p>
        </motion.div>

        {/* Input Card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className="w-full max-w-3xl glass-panel rounded-2xl p-1 bg-zinc-900/40"
        >
          <div className="p-6 md:p-8 space-y-8">
            {/* Search Input */}
            <div className="relative group">
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 block">Scenario Mode</label>
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-electric-blue transition-colors" />
                <input
                  type="text"
                  value={playerName}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSearchSuggestions(true);
                  }}
                  onChange={(e) => {
                    setPlayerName(e.target.value);
                    setSearchSuggestions(true);
                  }}
                  placeholder="Search for a player..."
                  className="w-full bg-black/20 border border-white/10 rounded-xl py-4 pl-12 pr-4 text-lg focus:outline-none focus:border-electric-blue/50 focus:ring-1 focus:ring-electric-blue/50 transition-all placeholder:text-gray-600"
                />
              </div>

              {/* Suggestions Dropdown */}
              <AnimatePresence>
                {searchSuggestions && filteredPlayers.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="absolute top-full left-0 right-0 mt-2 bg-zinc-900 border border-white/10 rounded-xl overflow-hidden shadow-2xl z-20"
                  >
                    {filteredPlayers.map((player, idx) => (
                      <button
                        key={idx}
                        onClick={(e) => {
                          e.stopPropagation();
                          setPlayerName(player);
                          setSearchSuggestions(false);
                        }}
                        className="w-full text-left px-4 py-3 hover:bg-white/5 transition-colors flex items-center justify-between group"
                      >
                        <span className="font-medium text-gray-300 group-hover:text-white">{player}</span>
                        <ArrowUpRightIcon className="w-4 h-4 text-gray-600 group-hover:text-white opacity-0 group-hover:opacity-100 transition-all" />
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Stat Selection */}
            <div>
              <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 block">Target Metric</label>
              <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                {STATS.map((stat) => (
                  <button
                    key={stat.id}
                    onClick={() => setSelectedStat(stat.id)}
                    className={`relative p-3 rounded-xl border transition-all duration-200 group ${selectedStat === stat.id
                      ? 'bg-electric-blue/10 border-electric-blue/50 text-electric-blue shadow-[0_0_15px_rgba(0,217,255,0.15)]'
                      : 'bg-black/20 border-white/5 text-gray-400 hover:bg-white/5 hover:border-white/10 hover:text-gray-200'
                      }`}
                  >
                    <div className="text-xl mb-1 filter grayscale group-hover:grayscale-0 transition-all">{stat.icon}</div>
                    <div className="text-xs font-semibold">{stat.label}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 block">Line</label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={lineValue}
                  onChange={(e) => setLineValue(e.target.value)}
                  placeholder="25.5"
                  className="w-full bg-black/20 border border-white/10 rounded-xl py-4 px-4 text-lg focus:outline-none focus:border-electric-blue/50 focus:ring-1 focus:ring-electric-blue/50 transition-all placeholder:text-gray-600"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 block">Period</label>
                <div className="grid grid-cols-4 gap-2">
                  {PERIODS.map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setPeriod(value)}
                      className={`rounded-xl border px-3 py-4 text-sm font-semibold transition-all ${period === value
                        ? 'bg-electric-blue/10 border-electric-blue/50 text-electric-blue'
                        : 'bg-black/20 border-white/5 text-gray-400 hover:bg-white/5 hover:border-white/10 hover:text-gray-200'
                        }`}
                    >
                      Q{value}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 block">Opponent</label>
                <input
                  type="text"
                  value={opponentTeam}
                  onChange={(e) => setOpponentTeam(e.target.value)}
                  placeholder="Opponent team"
                  className="w-full bg-black/20 border border-white/10 rounded-xl py-4 px-4 text-lg focus:outline-none focus:border-electric-blue/50 focus:ring-1 focus:ring-electric-blue/50 transition-all placeholder:text-gray-600"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 block">Fixture</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setIsHome(true)}
                    className={`rounded-xl border px-3 py-4 text-sm font-semibold transition-all ${isHome
                      ? 'bg-electric-blue/10 border-electric-blue/50 text-electric-blue'
                      : 'bg-black/20 border-white/5 text-gray-400 hover:bg-white/5 hover:border-white/10 hover:text-gray-200'
                      }`}
                  >
                    Home
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsHome(false)}
                    className={`rounded-xl border px-3 py-4 text-sm font-semibold transition-all ${!isHome
                      ? 'bg-electric-blue/10 border-electric-blue/50 text-electric-blue'
                      : 'bg-black/20 border-white/5 text-gray-400 hover:bg-white/5 hover:border-white/10 hover:text-gray-200'
                      }`}
                  >
                    Away
                  </button>
                </div>
              </div>
            </div>

            {/* Action Button */}
            <button
              onClick={handleSubmit}
              disabled={!playerName.trim() || lineValue === '' || isLoading}
              className="w-full py-4 bg-white text-black font-bold rounded-xl hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl hover:scale-[1.01] active:scale-[0.99] flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                  <span>Scoring Scenario...</span>
                </>
              ) : (
                <>
                  <BarChart3 className="w-5 h-5" />
                  <span>Run Scenario</span>
                </>
              )}
            </button>
          </div>
        </motion.div>

        {/* Results Section */}
        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 40 }}
              className="w-full max-w-3xl mt-8"
            >
              <div className="glass-panel rounded-2xl p-1 bg-zinc-900/60 overflow-hidden backdrop-blur-2xl">

                {/* Result Header */}
                <div className="p-6 md:p-8 border-b border-white/5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-3xl font-bold text-white tracking-tight">{result.playerName}</h2>
                    <div className="flex items-center gap-2 text-gray-400 text-sm mt-1">
                      <span>Q{result.period} {result.stat} vs {result.line}</span>
                      {result.opponentTeam ? (
                        <>
                          <span className="w-1 h-1 bg-gray-600 rounded-full" />
                          <span>{result.isHome ? 'Home' : 'Away'} vs {result.opponentTeam}</span>
                        </>
                      ) : null}
                      <span className="w-1 h-1 bg-gray-600 rounded-full" />
                      <span>{new Date().toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="px-4 py-2 rounded-full border flex items-center gap-2 bg-electric-blue/10 border-electric-blue/20 text-electric-blue">
                    <Target className="w-4 h-4" />
                    <span className="text-sm font-semibold">Scenario Mode</span>
                  </div>
                </div>

                <div className="p-6 md:p-8">
                  {/* Key Metrics Grid */}
                  <div className="grid md:grid-cols-2 gap-8 mb-8">
                    {/* Confidence Visual */}
                    <div className="bg-black/20 rounded-xl p-6 border border-white/5 flex flex-col items-center justify-center relative overflow-hidden group">
                      <div className="absolute inset-0 bg-gradient-to-br from-electric-blue/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                      <ConfidenceDial percentage={result.hitChance} size={160} />
                      <div className="mt-4 text-center z-10">
                        <div className="text-2xl font-bold bg-gradient-to-r from-electric-blue to-neon-green bg-clip-text text-transparent">
                          {result.recommendation}
                        </div>
                        <p className="text-sm text-gray-500 mt-1">
                          Projected {result.projected} {result.statSuffix}
                        </p>
                      </div>
                    </div>

                    {/* Stats Breakdown */}
                    <div className="space-y-4">
                      <div className="bg-black/20 rounded-xl p-5 border border-white/5 flex items-center justify-between">
                        <div>
                          <div className="text-sm text-gray-500 font-medium mb-1">User Line</div>
                          <div className="text-3xl font-bold text-white tracking-tight">
                            {result.userLine} <span className="text-lg text-gray-600 font-normal">{result.statSuffix}</span>
                          </div>
                        </div>
                        <div className="h-10 w-10 rounded-full bg-white/5 flex items-center justify-center">
                          <Activity className="w-5 h-5 text-gray-400" />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-4">
                          <div className="text-xs text-emerald-500/70 font-semibold uppercase tracking-wider mb-1">Over Prob.</div>
                          <div className="text-2xl font-bold text-emerald-400">{result.hitChance}%</div>
                        </div>
                        <div className="bg-rose-500/5 border border-rose-500/10 rounded-xl p-4">
                          <div className="text-xs text-rose-500/70 font-semibold uppercase tracking-wider mb-1">Under Prob.</div>
                          <div className="text-2xl font-bold text-rose-400">{result.missChance}%</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Chart */}
                  <div className="pt-6 border-t border-white/5">
                    <div className="flex items-center justify-between mb-6">
                      <h3 className="font-semibold text-gray-300 flex items-center gap-2">
                        <TrendingUp className="w-4 h-4 text-electric-blue" />
                        Historical Performance (Period Match)
                      </h3>
                      <div className="text-xs text-gray-500">Last 10 Games</div>
                    </div>

                    <div className="h-[200px] w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={result.historicalData}>
                          <defs>
                            <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#00D9FF" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#00D9FF" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                          <XAxis dataKey="game" hide />
                          <YAxis hide domain={['dataMin - 5', 'dataMax + 5']} />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: '#18181b',
                              border: '1px solid rgba(255,255,255,0.1)',
                              borderRadius: '8px',
                              boxShadow: '0 10px 30px -10px rgba(0,0,0,0.5)',
                              color: '#fff'
                            }}
                            itemStyle={{ color: '#fff' }}
                            labelStyle={{ display: 'none' }}
                          />
                          <ReferenceLine y={result.userLine} stroke="#00FF88" strokeDasharray="3 3" opacity={0.5} />
                          <Area
                            type="monotone"
                            dataKey="value"
                            stroke="#00D9FF"
                            strokeWidth={3}
                            fillOpacity={1}
                            fill="url(#chartGradient)"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </div>
  );
}

// Helper Icon
const ArrowUpRightIcon = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="M7 7h10v10" /><path d="M7 17 17 7" /></svg>
)

export default App;
