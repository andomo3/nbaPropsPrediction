import React from "react";

const DEFAULT_PROPS = ["points", "rebounds", "assists", "steals", "blocks"];
const DEFAULT_PERIODS = [1, 2, 3, 4];

function PropCalculator({
  players = [],
  propsList = DEFAULT_PROPS,
  periods = DEFAULT_PERIODS,
  onSubmit,
}) {
  const handleSubmit = (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
      player: form.player.value,
      prop: form.prop.value,
      line: Number(form.line.value),
      period: Number(form.period.value),
    };

    if (onSubmit) {
      onSubmit(payload);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm">
          <span className="text-gray-400">Player</span>
          <input
            name="player"
            list="player-options"
            placeholder="Search player..."
            className="w-full rounded-lg border border-white/10 bg-black/30 px-4 py-3 text-white"
          />
        </label>

        <label className="space-y-2 text-sm">
          <span className="text-gray-400">Prop Type</span>
          <select
            name="prop"
            className="w-full rounded-lg border border-white/10 bg-black/30 px-4 py-3 text-white"
          >
            {propsList.map((propType) => (
              <option key={propType} value={propType}>
                {propType}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm">
          <span className="text-gray-400">Line</span>
          <input
            name="line"
            type="number"
            step="0.5"
            placeholder="24.5"
            className="w-full rounded-lg border border-white/10 bg-black/30 px-4 py-3 text-white"
          />
        </label>

        <label className="space-y-2 text-sm">
          <span className="text-gray-400">Period</span>
          <select
            name="period"
            className="w-full rounded-lg border border-white/10 bg-black/30 px-4 py-3 text-white"
          >
            {periods.map((period) => (
              <option key={period} value={period}>
                Q{period}
              </option>
            ))}
          </select>
        </label>
      </div>

      <button
        type="submit"
        className="w-full rounded-lg bg-white py-3 text-sm font-semibold text-black"
      >
        Run Scenario
      </button>

      <datalist id="player-options">
        {players.map((player) => (
          <option key={player.id ?? player.name} value={player.name} />
        ))}
      </datalist>
    </form>
  );
}

export default PropCalculator;
