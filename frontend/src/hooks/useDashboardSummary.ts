import { useCallback, useEffect, useRef, useState } from "react";
import { getDashboardSummary } from "../lib/api";
import type { DashboardSummaryResponse } from "../types/dashboard";

interface Options {
  days?: number;
  pollInterval?: number;
}

export const useDashboardSummary = ({ days = 7, pollInterval = 10000 }: Options = {}) => {
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    if (!data) {
      setLoading(true);
    }

    try {
      const response = await getDashboardSummary(days, controller.signal);
      setData(response);
      setError(null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }, [days, data]);

  useEffect(() => {
    fetchData();
    return () => controllerRef.current?.abort();
  }, [fetchData]);

  useEffect(() => {
    if (!pollInterval) return;
    const id = setInterval(fetchData, pollInterval);
    return () => clearInterval(id);
  }, [fetchData, pollInterval]);

  return { data, loading, error, refresh: fetchData };
};
