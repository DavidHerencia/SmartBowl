export type HydrationLevel = "high" | "medium" | "low";

export interface HydrationDayItem {
  day: string;
  date: string;
  value_ml: number;
  level: HydrationLevel;
  human_label?: string | null;
  cluster?: number | null;
}

export interface KMeansClusterAssignment {
  day: string;
  cluster: number;
  label: string;
}

export interface KMeansSummary {
  centers?: number[][];
  assignments?: KMeansClusterAssignment[];
  label_map?: Record<string, string>;
}

export interface HydrationWeekPackage {
  items: HydrationDayItem[];
  kmeans?: KMeansSummary;
}

export interface TodayHydrationSummary {
  day: string;
  ml: number;
  updated_ts: number | null;
  entry?: HydrationDayItem | null;
  classification?: {
    cluster: number;
    dist: number;
    label?: string | null;
  } | null;
}

export interface DashboardHydration {
  today: TodayHydrationSummary;
  week: HydrationWeekPackage;
  summary: string;
}

export interface DeviceStatus {
  is_online: boolean;
  is_system_on: boolean;
  is_drinking: boolean;
  is_filling: boolean;
  tank_level_percent: number;
  last_seen_ts?: number | null;
  last_seen_iso?: string | null;
  last_drink_ts?: number | null;
  last_drink_ml?: number | null;
  estimated_capacity_ml?: number | null;
  current_volume_ml?: number | null;
}

export interface LastCommand {
  topic: string;
  payload: Record<string, unknown>;
  ts: number;
  iso?: string;
}

export interface LastDrinkInfo {
  ts: number;
  iso?: string | null;
  ml?: number;
  volumen_inicio?: number;
  volumen_fin?: number;
  duracion?: number;
}

export interface DashboardSummaryResponse {
  device: {
    id: string | null;
    topic: string;
  };
  status: DeviceStatus;
  last_command?: LastCommand | null;
  last_drink?: LastDrinkInfo | null;
  hydration: DashboardHydration;
  last_event?: Record<string, unknown> | null;
  raw_last?: Record<string, unknown> | null;
}

export interface SensorTopicEntry {
  topic: string;
  raw?: string;
  parsed?: Record<string, unknown> | null;
  ts?: number;
}

export interface SensorsLatestResponse {
  subscribed_topic?: string;
  raw_last?: SensorTopicEntry | null;
  hydration_last?: Record<string, unknown> | null;
  level_last?: Record<string, unknown> | null;
  topics?: SensorTopicEntry[];
  last_event?: Record<string, unknown> | null;
  status?: Record<string, unknown> | null;
  last_command?: LastCommand | null;
}
