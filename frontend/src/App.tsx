import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  Calendar,
  CheckCircle2,
  Clock,
  Database,
  Droplets,
  Power,
  RefreshCw,
  Smartphone
} from "lucide-react";
import clsx from "clsx";
import { useDashboardSummary } from "./hooks/useDashboardSummary";
import { HydrationHeatmap } from "./components/HydrationHeatmap";
import { ClusterInsights } from "./components/ClusterInsights";
import { getLatestSensors, sendActuatorCommand } from "./lib/api";
import type { SensorsLatestResponse } from "./types/dashboard";

const formatIso = (iso?: string | null, fallback = "--:--") => {
  if (!iso) return fallback;
  try {
    return new Date(iso).toLocaleTimeString("es-PE", {
      hour: "2-digit",
      minute: "2-digit"
    });
  } catch (e) {
    return fallback;
  }
};

const formatRelativeTime = (iso?: string | null) => {
  if (!iso) return "Sin registro";
  const now = Date.now();
  const ts = new Date(iso).getTime();
  const diff = now - ts;
  if (diff < 60_000) return "Hace instantes";
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 60) return `Hace ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Hace ${hours} h`;
  const days = Math.floor(hours / 24);
  return `Hace ${days} d`;
};

const formatDateTime = (iso?: string | null) => {
  if (!iso) return "Sin registro";
  return new Date(iso).toLocaleString("es-PE", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short"
  });
};

const formatMl = (ml?: number | null) => `${ml ? Math.round(ml) : 0} ml`;

const sanitizePercent = (value: number) => Math.min(100, Math.max(0, value));

const tankWaveStyle = (value: number) => ({ height: `${sanitizePercent(value)}%` });

const safeNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const summarizeJson = (payload?: Record<string, unknown> | null) => {
  if (!payload) return "Sin datos";
  try {
    return JSON.stringify(payload, null, 2);
  } catch (err) {
    return String(payload);
  }
};

const readField = (obj: Record<string, unknown> | null | undefined, field: string) => {
  if (!obj || typeof obj !== "object") return undefined;
  return (obj as Record<string, unknown>)[field];
};

const App = () => {
  const { data, loading, error, refresh } = useDashboardSummary({ days: 7, pollInterval: 8000 });
  const [currentTime, setCurrentTime] = useState(new Date());
  const [isSending, setIsSending] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [sensors, setSensors] = useState<SensorsLatestResponse | null>(null);
  const [sensorsError, setSensorsError] = useState<string | null>(null);
  const [localSystemOn, setLocalSystemOn] = useState<boolean | null>(null);

  useEffect(() => {
    const id = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    let controller: AbortController | null = null;
    let mounted = true;

    const load = async () => {
      controller?.abort();
      controller = new AbortController();
      try {
        const latest = await getLatestSensors(controller.signal);
        if (mounted) {
          setSensors(latest);
          setSensorsError(null);
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (mounted) {
          setSensorsError(err instanceof Error ? err.message : "Error obteniendo sensores");
        }
      }
    };

    load();
    const id = setInterval(load, 10_000);

    return () => {
      mounted = false;
      controller?.abort();
      clearInterval(id);
    };
  }, []);

  const status = data?.status;
  const hydration = data?.hydration;
  const todayEntry = hydration?.today?.entry ?? null;
  const tankPercent = status?.tank_level_percent ?? 0;
  const backendSystemOn = status?.is_system_on ?? false;
  const isSystemOn = localSystemOn ?? backendSystemOn;
  const isOnline = status?.is_online ?? false;
  const lastDrink = data?.last_drink;
  const lastCommand = data?.last_command ?? sensors?.last_command ?? null;
  const lastEvent = (data?.last_event ?? sensors?.last_event) as Record<string, unknown> | null;
  const rawLast = sensors?.raw_last ?? (data?.raw_last as Record<string, unknown> | null | undefined);
  const levelLast = sensors?.level_last as Record<string, unknown> | null | undefined;

  const lastDrinkDescription = useMemo(() => {
    if (!lastDrink) return "Sin consumo reciente";
    const { iso, ml } = lastDrink;
    return `${formatMl(ml)} · ${formatDateTime(iso)}`;
  }, [lastDrink]);

  const lastCommandLabel = useMemo(() => {
    const payload = lastCommand?.payload;
    if (payload && typeof payload === "object" && "command" in payload) {
      const cmd = (payload as Record<string, unknown>).command;
      return typeof cmd === "string" ? cmd : JSON.stringify(cmd);
    }
    return "Sin acciones recientes";
  }, [lastCommand]);

  const sendCommand = async (payload: Record<string, unknown>, successText: string) => {
    try {
      setIsSending(true);
      await sendActuatorCommand(payload);
      setToast({ type: "success", text: successText });
      refresh();
    } catch (err) {
      setToast({ type: "error", text: err instanceof Error ? err.message : "Error enviando comando" });
    } finally {
      setIsSending(false);
    }
  };

  const handleFill = () => sendCommand({ command: "llenar" }, "Comando de llenado enviado");
  const handlePowerToggle = () => {
    setLocalSystemOn((prev) => {
      const next = !(prev ?? backendSystemOn);
      setToast({ type: "success", text: next ? "Modo manual: sistema encendido" : "Modo manual: sistema apagado" });
      return next;
    });
  };

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(id);
  }, [toast]);

  const loadingState = loading && !data;
  const eventMl = safeNumber(lastEvent?.ml_consumed ?? sensors?.hydration_last?.ml_consumed);
  const eventDuration = safeNumber(lastEvent?.duracion);
  const eventGap = safeNumber(lastEvent?.gap_min);
  const statusVolume = safeNumber(status?.current_volume_ml);
  const levelVolume = safeNumber(readField(levelLast ?? null, "volumen"));
  const hydrationVolumeFromEvent = safeNumber(readField(lastEvent, "volumen_fin"));
  const hydrationVolumeFromSensors = safeNumber(
    readField((sensors?.hydration_last as Record<string, unknown> | null | undefined) ?? null, "volumen_fin")
  );
  const currentVolumeMl =
    statusVolume ?? levelVolume ?? hydrationVolumeFromEvent ?? hydrationVolumeFromSensors ?? null;

  const topic = data?.device?.topic ?? sensors?.subscribed_topic ?? "home/water/consumption";

  useEffect(() => {
    if (typeof status?.is_system_on === "boolean") {
      setLocalSystemOn(status.is_system_on);
    }
  }, [status?.is_system_on]);

  return (
    <div className={clsx("min-h-screen transition-colors duration-500", isSystemOn ? "bg-slate-50" : "bg-slate-100")}> 
      <header className="bg-white/95 backdrop-blur shadow-sm sticky top-0 z-10 border-b border-slate-100">
        <div className="max-w-5xl mx-auto px-4 py-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="bg-blue-600 p-3 rounded-2xl text-white shadow-glow">
              <Droplets className="w-7 h-7" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Smart IoT</p>
              <h1 className="text-2xl font-bold text-slate-800 leading-tight">SmartBowl Dashboard</h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div
              className={clsx(
                "px-4 py-2 rounded-full text-sm font-semibold flex items-center gap-2",
                isOnline ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
              )}
            >
              <span className={clsx("w-2.5 h-2.5 rounded-full", isOnline ? "bg-emerald-500 animate-pulse" : "bg-rose-500")} />
              {isOnline ? "Activo" : "Sin actividad"}
            </div>
            <div className="hidden sm:flex text-xs text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
              Tópico: {topic}
            </div>
            <button
              onClick={refresh}
              className="h-10 w-10 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center hover:bg-slate-200"
              title="Refrescar"
            >
              <RefreshCw className={clsx("w-5 h-5", loading ? "animate-spin" : "")}
            />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        {(error || sensorsError) && (
          <div className="flex items-center gap-2 bg-rose-50 border border-rose-200 text-rose-700 p-4 rounded-xl">
            <AlertCircle className="w-5 h-5" />
            <span>{error ?? sensorsError}</span>
          </div>
        )}
        {toast && (
          <div
            className={clsx(
              "flex items-center gap-2 p-4 rounded-xl",
              toast.type === "success" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
            )}
          >
            <CheckCircle2 className="w-5 h-5" />
            <span>{toast.text}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <section
            className={clsx(
              "relative overflow-hidden rounded-3xl shadow-lg border",
              isSystemOn ? "bg-white border-slate-100" : "bg-slate-900 text-white border-slate-800"
            )}
          >
            <div className="absolute top-5 right-6 text-4xl sm:text-5xl font-extrabold text-blue-500">
              {loadingState ? "--" : `${sanitizePercent(tankPercent).toFixed(0)}%`}
            </div>
            <div className="absolute top-16 right-6 text-sm font-semibold text-slate-500">
              {currentVolumeMl != null ? formatMl(currentVolumeMl) : "Sin volumen"}
            </div>
            <div className="p-6 h-72 flex flex-col justify-between relative z-10">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Nivel del tanque</p>
                <h2 className="text-2xl font-bold">Capacidad estimada</h2>
                <p className="text-sm text-slate-500 mt-1">
                  Última lectura: {formatIso(status?.last_seen_iso, "Sin registro")}
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2 text-slate-600">
                  <Clock className="w-4 h-4" />
                  <span>Hora actual:</span>
                  <strong className="text-slate-900">
                    {currentTime.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </strong>
                </div>
                <div className="flex items-center gap-2 text-slate-600">
                  <Activity className="w-4 h-4 text-blue-500" />
                  <span>Último sorbo:</span>
                  <strong className="text-slate-900">{lastDrinkDescription}</strong>
                </div>
                <div className="flex items-center gap-2 text-sm font-semibold px-3 py-2 rounded-xl w-fit bg-blue-50 text-blue-700">
                  {status?.is_drinking ? "Mascota bebiendo ahora" : "Sin actividad"}
                </div>
              </div>
            </div>
            <div className="absolute bottom-0 left-0 right-0 transition-all duration-1000" style={tankWaveStyle(tankPercent)}>
              <div className="wave rounded-t-[60%] opacity-90 w-full h-full" />
              <div className="h-6 bg-cyan-200 opacity-50 -mt-2 blur-xl" />
            </div>
          </section>

          <section className="rounded-3xl bg-white shadow-lg border border-slate-100 p-6 space-y-5">
            <div
              className={clsx(
                "p-5 rounded-2xl flex items-center justify-between",
                !isSystemOn
                  ? "bg-slate-100"
                  : status?.is_drinking
                    ? "bg-blue-600 text-white"
                    : "bg-slate-50"
              )}
            >
              <div className="flex items-center gap-3">
                <div className={clsx("p-3 rounded-2xl", status?.is_drinking ? "bg-white/20" : "bg-white")}
                >
                  {status?.is_drinking ? <Activity className="w-6 h-6" /> : <CheckCircle2 className="w-6 h-6 text-emerald-500" />}
                </div>
                <div>
                  <p className="text-sm font-semibold">
                    {status?.is_drinking ? "Se detectó un consumo" : isSystemOn ? "Sistema listo" : "Sistema inactivo"}
                  </p>
                  <p className="text-xs text-slate-500">
                    {status?.is_drinking ? "Hidratación en curso" : "Esperando evento"}
                  </p>
                </div>
              </div>
              {status?.is_drinking && <span className="w-3 h-3 bg-white rounded-full animate-ping" />}
            </div>

            {!isOnline && (
              <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 border border-amber-100 px-3 py-2 rounded-xl">
                <AlertCircle className="w-4 h-4" />
                Sin consumos detectados recientemente.
              </div>
            )}

            <h3 className="text-lg font-semibold text-slate-800">Acciones rápidas</h3>
            <div className="space-y-3">
              <button
                onClick={handleFill}
                disabled={isSending || status?.is_filling}
                className={clsx(
                  "w-full py-4 rounded-2xl flex items-center justify-center gap-3 text-white font-semibold",
                  isSending || status?.is_filling ? "bg-blue-300 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"
                )}
              >
                <RefreshCw className={clsx("w-5 h-5", isSending || status?.is_filling ? "animate-spin" : "")}
                />
                {status?.is_filling ? "Llenando..." : "Llenar Tanque"}
              </button>

              <button
                onClick={handlePowerToggle}
                className={clsx(
                  "w-full py-4 rounded-2xl border-2 flex items-center justify-center gap-3 font-semibold",
                  isSystemOn
                    ? "border-rose-200 text-rose-600 hover:bg-rose-50"
                    : "border-emerald-200 text-emerald-600 hover:bg-emerald-50"
                )}
              >
                <Power className="w-5 h-5" />
                {isSystemOn ? "Apagar" : "Encender"}
              </button>

              <div className="flex flex-wrap gap-3 text-sm text-slate-500">
                <div className="flex items-center gap-2 bg-slate-100 px-3 py-2 rounded-xl">
                  <Smartphone className="w-4 h-4" />
                  Última acción: {lastCommandLabel}
                </div>
                <div className="flex items-center gap-2 bg-slate-100 px-3 py-2 rounded-xl">
                  <Clock className="w-4 h-4" />
                  {formatRelativeTime(lastCommand?.iso)}
                </div>
              </div>
            </div>
          </section>
        </div>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              label: "Estado",
              value: isOnline ? "Conectado" : "Sin conexión",
              helper: formatRelativeTime(status?.last_seen_iso),
              icon: <Droplets className="w-5 h-5" />,
              accent: isOnline ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
            },
            {
              label: "Consumo de hoy",
              value: formatMl(hydration?.today?.ml),
              helper: todayEntry?.human_label ?? todayEntry?.level ?? "Sin registro",
              icon: <Activity className="w-5 h-5" />,
              accent: "bg-blue-50 text-blue-700"
            },
            {
              label: "Último sorbo",
              value: lastDrink ? formatDateTime(lastDrink.iso) : "Sin registro",
              helper: formatMl(lastDrink?.ml),
              icon: <Calendar className="w-5 h-5" />,
              accent: "bg-slate-50 text-slate-700"
            }
          ].map((stat) => (
            <article key={stat.label} className={clsx("rounded-2xl p-4 border border-slate-100 flex items-center gap-3", stat.accent)}>
              <div className="p-2 bg-white/70 rounded-xl text-slate-600">{stat.icon}</div>
              <div>
                <p className="text-xs uppercase tracking-wider text-slate-400">{stat.label}</p>
                <p className="text-lg font-semibold text-slate-800">{stat.value}</p>
                <p className="text-xs text-slate-500">{stat.helper}</p>
              </div>
            </article>
          ))}
        </section>

        <HydrationHeatmap
          items={hydration?.week?.items ?? []}
          summary={hydration?.summary ?? "Sin    de hidratación."}
          loading={loadingState}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ClusterInsights kmeans={hydration?.week?.kmeans} today={hydration?.today} todayEntry={todayEntry} />

          <section className="rounded-2xl bg-white border border-slate-100 shadow-lg p-6 space-y-4">
            <header className="flex items-center gap-3 text-slate-800">
              <span className="p-2 rounded-2xl bg-slate-100 text-slate-600">
                <Database className="w-5 h-5" />
              </span>
              <div>
                <h2 className="text-lg font-semibold">Telemetría cruda</h2>
                <p className="text-sm text-slate-500">Último evento procesado por el backend</p>
              </div>
            </header>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-xs text-slate-400 uppercase">Consumo</p>
                <p className="text-lg font-semibold text-slate-800">{formatMl(eventMl ?? undefined)}</p>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-xs text-slate-400 uppercase">Duración</p>
                <p className="text-lg font-semibold text-slate-800">{eventDuration ? `${eventDuration.toFixed(1)} s` : "--"}</p>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-xs text-slate-400 uppercase">Gap</p>
                <p className="text-lg font-semibold text-slate-800">{eventGap ? `${eventGap.toFixed(1)} min` : "--"}</p>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-xs text-slate-400 uppercase">Volumen actual</p>
                <p className="text-lg font-semibold text-slate-800">
                  {currentVolumeMl != null ? formatMl(currentVolumeMl) : "--"}
                </p>
              </div>
            </div>

            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-400 mb-2">Payload</p>
              <pre className="bg-slate-900 text-slate-100 rounded-xl p-4 text-xs overflow-x-auto max-h-48">
                {summarizeJson((rawLast?.parsed as Record<string, unknown>) ?? (rawLast as Record<string, unknown> | null))}
              </pre>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};

export default App;
