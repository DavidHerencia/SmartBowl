import { Activity, Target } from "lucide-react";
import type { HydrationDayItem, KMeansSummary, TodayHydrationSummary } from "../types/dashboard";
import clsx from "clsx";

interface Props {
  kmeans?: KMeansSummary;
  today?: TodayHydrationSummary;
  todayEntry?: HydrationDayItem | null;
}

const LABEL_COLORS: Record<string, string> = {
  Adecuado: "text-emerald-600",
  Medio: "text-amber-500",
  Mínimo: "text-rose-500"
};

export const ClusterInsights = ({ kmeans, today, todayEntry }: Props) => {
  if (!kmeans?.centers?.length) {
    return null;
  }

  const centers = kmeans.centers.map((center, idx) => {
    const label = kmeans.label_map?.[String(idx)] ?? `Cluster ${idx}`;
    return {
      idx,
      label,
      ml: Math.round(center[0]),
      hour: Math.round(center[2]),
      gap: Math.round(center[3])
    };
  });

  return (
    <section className="rounded-2xl bg-white border border-slate-100 shadow-lg p-6 space-y-4">
      <header className="flex items-center gap-3 text-slate-800">
        <span className="p-2 rounded-2xl bg-blue-100 text-blue-600">
          <Target className="w-5 h-5" />
        </span>
        <div>
          <h2 className="text-lg font-semibold">Analítica K-Means</h2>
          <p className="text-sm text-slate-500">Patrones aprendidos del consumo diario</p>
        </div>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {centers.map((center) => (
          <div key={center.idx} className="rounded-xl bg-slate-50 border border-slate-100 p-4">
            <p className={clsx("text-xs uppercase tracking-[0.3em]", LABEL_COLORS[center.label] ?? "text-slate-500")}> 
              {center.label}
            </p>
            <p className="text-2xl font-bold text-slate-900">{center.ml} ml</p>
            <p className="text-xs text-slate-500">Hora típica: {center.hour}h · Gap: {center.gap}m</p>
          </div>
        ))}
      </div>

      {today && todayEntry && today.classification && (
        <div className="p-4 rounded-xl bg-blue-50 border border-blue-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3 text-blue-800">
            <span className="p-2 rounded-2xl bg-white text-blue-600">
              <Activity className="w-5 h-5" />
            </span>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-blue-400">Hoy</p>
              <p className="text-sm font-semibold">
                Clasificación: {today.classification.label ?? `Cluster ${today.classification.cluster}`}
              </p>
              <p className="text-xs text-blue-600">
                {todayEntry.value_ml} ml · Distancia {today.classification.dist?.toFixed(2)}
              </p>
            </div>
          </div>
          <div className="text-xs text-blue-700">
            Vector: {todayEntry.day} - {todayEntry.human_label ?? todayEntry.level}
          </div>
        </div>
      )}
    </section>
  );
};
