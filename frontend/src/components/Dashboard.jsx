import React from "react";

function Dashboard({ title = "Scenario Mode", children }) {
  return (
    <section className="rounded-2xl border border-white/10 bg-zinc-900/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-white">{title}</h2>
        <span className="text-xs uppercase tracking-widest text-gray-500">
          Manual Line
        </span>
      </div>
      {children}
    </section>
  );
}

export default Dashboard;
