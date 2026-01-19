export default function PlayerSearch() {
  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-900/60 p-4">
      <label className="text-xs uppercase tracking-[0.25em] text-neutral-400">
        Search player
      </label>
      <input
        className="mt-3 w-full rounded-xl border border-neutral-700 bg-neutral-950 px-4 py-3 text-sm text-neutral-100 placeholder:text-neutral-600"
        placeholder="Type a player name"
        type="text"
      />
    </div>
  );
}