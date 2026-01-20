import React from "react";

function PredictionResult({ result }) {
  if (!result) {
    return (
      <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-sm text-gray-400">
        Run a scenario to see the model output.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-4">
      <div className="text-sm text-gray-400">Projected</div>
      <div className="text-3xl font-semibold text-white">
        {result.projected ?? "--"}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
          <div className="text-emerald-300">Over</div>
          <div className="text-lg font-semibold text-emerald-200">
            {result.prob_over != null
              ? `${Math.round(result.prob_over * 100)}%`
              : "--"}
          </div>
        </div>
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3">
          <div className="text-rose-300">Under</div>
          <div className="text-lg font-semibold text-rose-200">
            {result.prob_under != null
              ? `${Math.round(result.prob_under * 100)}%`
              : "--"}
          </div>
        </div>
      </div>
    </div>
  );
}

export default PredictionResult;
