import PredictionCard from "../../../components/PredictionCard";
import PlayerSearch from "../../../components/PlayerSearch";

interface PlayerDetailPageProps {
  params: {
    id: string;
  };
}

export default function PlayerDetailPage({ params }: PlayerDetailPageProps) {
  return (
    <main className="min-h-screen bg-neutral-950 p-8 text-neutral-100">
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-neutral-400">
            Player Profile
          </p>
          <h1 className="text-3xl font-semibold">Player {params.id}</h1>
        </div>
        <PlayerSearch />
        <PredictionCard
          title="Q1 Rebounds"
          detail="Over 2.5"
          probability={0.65}
        />
      </div>
    </main>
  );
}