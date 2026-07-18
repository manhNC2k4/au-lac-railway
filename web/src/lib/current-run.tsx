"use client";

import { createContext, useContext, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getApi, qk, type RunSummary, type StopRecord } from "@/api";
import { GOLDEN } from "@/lib/constants";

export interface RunSegment {
  segment_id: number;
  from: StopRecord;
  to: StopRecord;
}

interface CurrentRunContextValue {
  serviceRunId: string;
  setServiceRunId: (id: string) => void;
  runs: RunSummary[];
  runsLoading: boolean;
  stops: StopRecord[];
  segments: RunSegment[];
  isGolden: boolean;
}

const CurrentRunContext = createContext<CurrentRunContextValue | null>(null);

/** Cung cấp "chuyến đang xem" cho toàn bộ trang admin/ops — thay GOLDEN.serviceRunId cứng. */
export function CurrentRunProvider({ children }: { children: React.ReactNode }) {
  const api = getApi();
  const [selected, setSelected] = useState<string | null>(null);

  const runsQuery = useQuery({
    queryKey: qk.runs(),
    queryFn: () => api.listRuns(),
    staleTime: 60_000,
  });
  const runs = runsQuery.data?.runs ?? [];
  // /demo/runs sắp xếp tăng dần theo service_date — mặc định lấy chuyến gần nhất (cuối danh sách).
  const serviceRunId = selected ?? runs[runs.length - 1]?.service_run_id ?? GOLDEN.serviceRunId;

  const stopsQuery = useQuery({
    queryKey: qk.runStops(serviceRunId),
    queryFn: () => api.getRunStops(serviceRunId),
    enabled: Boolean(serviceRunId),
  });
  const stops = stopsQuery.data?.stops ?? [];
  const segments = useMemo<RunSegment[]>(
    () => (stops.length > 1 ? stops.slice(0, -1).map((from, i) => ({ segment_id: i + 1, from, to: stops[i + 1] })) : []),
    [stops],
  );

  const value: CurrentRunContextValue = {
    serviceRunId,
    setServiceRunId: setSelected,
    runs,
    runsLoading: runsQuery.isPending,
    stops,
    segments,
    isGolden: serviceRunId === GOLDEN.serviceRunId,
  };

  return <CurrentRunContext.Provider value={value}>{children}</CurrentRunContext.Provider>;
}

/** "Ga đi → Ga đến" cho một segment_id — thay segmentStations() cứng theo golden network. */
export function segmentLabel(segments: RunSegment[], segmentId: number): string {
  const seg = segments.find((s) => s.segment_id === segmentId);
  return seg ? `${seg.from.station_name} → ${seg.to.station_name}` : `L${segmentId}`;
}

export function useCurrentRun(): CurrentRunContextValue {
  const ctx = useContext(CurrentRunContext);
  if (!ctx) throw new Error("useCurrentRun must be used within CurrentRunProvider");
  return ctx;
}
