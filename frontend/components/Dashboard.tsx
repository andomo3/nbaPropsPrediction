interface DashboardProps {
  title?: string;
}

export default function Dashboard({ title = "Prop Dashboard" }: DashboardProps) {
  return (
    <section className="rounded-3xl border border-neutral-800 bg-neutral-900/60 p-6">
      <h2 className="text-xl font-semibold text-neutral-100">{title}</h2>
      <p className="mt-2 text-sm text-neutral-400">
        Hook the period-specific predictions into this view.
      </p>
    </section>
  );
}