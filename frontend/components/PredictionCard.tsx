interface PredictionCardProps {
  title: string;
  detail: string;
  probability: number;
}

export default function PredictionCard({
  title,
  detail,
  probability,
}: PredictionCardProps) {
  const pct = Math.round(probability * 100);

  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-900/70 p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-neutral-400">
            {title}
          </p>
          <h3 className="mt-2 text-2xl font-semibold text-neutral-100">
            {detail}
          </h3>
        </div>
        <div className="rounded-full border border-emerald-400/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200">
          {pct}% Prob
        </div>
      </div>
    </div>
  );
}