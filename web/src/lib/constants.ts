/** Hằng số golden scenario — trùng backend/seed/scenario.json. */
export const GOLDEN = {
  serviceRunId: "SE1_2026-06-15_LE",
  scenarioId: "golden_scenario_1",
  serviceDate: "2026-06-15",
  seatClass: "NGOI_MEM_DH",
  goldenSeatId: "C01-S017",
  goldenGapSegments: [3, 4] as const,
  origin: "THO",
  dest: "DHO",
  quantity: 1,
  backtestSeeds: ["20260717", "20260718", "20260719", "20260720", "20260721"],
  eventStreamId: "stream_demo_1",
} as const;

export const SEAT_CLASS_LABEL: Record<string, string> = {
  NGOI_MEM_DH: "Ngồi mềm điều hòa",
};

export interface StationInfo {
  id: string;
  name: string;
}

/** 8 ga theo seed/scenario.json (thứ tự tuyến). */
export const STATIONS: StationInfo[] = [
  { id: "HNO", name: "Hà Nội" },
  { id: "NBI", name: "Ninh Bình" },
  { id: "THO", name: "Thanh Hóa" },
  { id: "VIN", name: "Vinh" },
  { id: "DHO", name: "Đồng Hới" },
  { id: "HUE", name: "Huế" },
  { id: "DNA", name: "Đà Nẵng" },
  { id: "SGO", name: "Sài Gòn" },
];

export function stationName(id: string): string {
  return STATIONS.find((s) => s.id === id)?.name ?? id;
}

/** segment_id 1-based: L1 = HNO→NBI … L7 = DNA→SGO. */
export const SEGMENTS = [1, 2, 3, 4, 5, 6, 7].map((id) => ({
  id,
  from: STATIONS[id - 1].id,
  to: STATIONS[id].id,
}));

export function segmentLabel(segmentId: number): string {
  const seg = SEGMENTS[segmentId - 1];
  return seg ? `L${segmentId} ${seg.from}–${seg.to}` : `L${segmentId}`;
}

export function segmentStations(segmentId: number): string {
  const seg = SEGMENTS[segmentId - 1];
  return seg ? `${stationName(seg.from)} → ${stationName(seg.to)}` : `L${segmentId}`;
}
