import { Calendar } from "lucide-react";
import clsx from "clsx";
import type { HydrationDayItem } from "../types/dashboard";

const COLOR_CLASS: Record<string, string> = {
  high: "from-emerald-500 to-emerald-400",
  medium: "from-amber-400 to-amber-300",
  low: "from-rose-500 to-rose-400"
};

interface Props {
  items: HydrationDayItem[];
  summary: string;
  loading?: boolean;
}

const formatMl = (ml?: number) => `${ml ?? 0} ml`;

export const HydrationHeatmap = ({ items, summary, loading }: Props) => {
  const hasData = items.length > 0;

  return (
    <section className="rounded-2xl shadow-lg bg-white border border-slate-100 p-6 space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-slate-800">
          <span className="p-2 rounded-xl bg-violet-100 text-violet-600">
            <Calendar className="w-5 h-5" />
          </span>
          <div>
            <h2 className="font-semibold text-lg">Historial de Hidratación</h2>
            <p className="text-sm text-slate-500">Días clasificados por K-Means</p>
          </div>
        </div>
        <div className="flex gap-4 text-xs text-slate-500">
          {[
            { label: "Adecuado", color: "bg-emerald-500" },
            { label: "Medio", color: "bg-amber-400" },
            { label: "Mínimo", color: "bg-rose-500" }
          ].map(({ label, color }) => (
            <span key={label} className="flex items-center gap-1">
              <span className={clsx("w-3 h-3 rounded-full", color)} />
              {label}
            </span>
          ))}
        </div>
      </header>

      <div className={clsx("grid gap-3 sm:gap-4", "grid-cols-2 sm:grid-cols-4 lg:grid-cols-7")}>
        {(loading && !hasData ? Array.from({ length: 7 }).map(() => null) : items).map((item, index) => (
          <div key={item?.date ?? index} className="group space-y-2">
            <div
              className={clsx(
                "relative rounded-2xl aspect-[3/4] overflow-hidden text-white",
                "shadow-lg shadow-black/10 border border-white/25",
                loading && !item
                  ? "bg-slate-200 animate-pulse"
                  : `bg-gradient-to-br ${COLOR_CLASS[item?.level ?? "medium"]}`
              )}
            >
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-3">
                <span className="text-[11px] uppercase tracking-[0.3em] opacity-80">
                  {item ? (item.human_label ?? item.level) : "--"}
                </span>
                <span className="text-xl font-bold">
                  {item ? `${item.value_ml} ml` : ""}
                </span>
                <span className="text-xs opacity-70">Cluster {item?.cluster ?? "-"}</span>
              </div>
              <div className="absolute top-3 left-3 text-[11px] font-semibold tracking-wide uppercase">
                {item ? item.day : "--"}
              </div>
              <div className="absolute bottom-3 right-3 text-[11px] opacity-80">
                {item ? item.date : "--"}
              </div>
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-slate-600">{item ? item.day : "--"}</p>
              <p className="text-xs text-slate-400">{item ? formatMl(item.value_ml) : "Cargando"}</p>
            </div>
          </div>
        ))}
      </div>

      <footer className="p-4 rounded-xl bg-blue-50 border border-blue-100 text-sm text-blue-700">
        {summary}
      </footer>
    </section>
  );
};
