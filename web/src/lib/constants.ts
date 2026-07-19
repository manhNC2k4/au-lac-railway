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
  NAM_K6: "Giường nằm khoang 6",
  NAM_K4: "Giường nằm khoang 4",
};

export const BOOKING_STATUS_LABEL: Record<string, string> = {
  SUBMITTED: "Đã tiếp nhận",
  AI_PROCESSING: "AI đang xử lý",
  PENDING_ADMIN: "Chờ nhân viên duyệt",
  APPROVED: "Đã duyệt",
  REJECTED: "Đã từ chối",
  EXPIRED: "Đã hết hạn",
  SELECTED: "Đã chọn ghế",
  CONFIRMED: "Đã xác nhận",
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
  return STATION_NAMES[id] ?? id;
}

export function trainDisplayName(serviceRunId: string): string {
  const canonical = serviceRunId.match(/^RUN:([^:]+):/);
  if (canonical) return `Tàu ${canonical[1]}`;
  const legacy = serviceRunId.match(/^([^_]+)_\d{4}-\d{2}-\d{2}/);
  return legacy ? `Tàu ${legacy[1]}` : "Chuyến tàu đã chọn";
}

export function seatDisplayName(seatId: string, seatClass?: string): string {
  const indexed = seatId.match(/:(\d+)$/);
  const legacy = seatId.match(/-S(\d+)$/);
  if (indexed && seatClass) {
    const seatIndex = Number(indexed[1]);
    const layout = DERIVED_SEAT_LAYOUT[seatClass];
    if (layout && Number.isFinite(seatIndex)) {
      const coach = layout.firstCoach + Math.floor(seatIndex / layout.capacity);
      const seat = 1 + seatIndex % layout.capacity;
      return `Toa ${coach} · ${seatClass.startsWith("NAM_") ? "Giường" : "Ghế"} ${seat}`;
    }
  }
  const number = legacy ? Number(legacy[1]) : null;
  if (number === null || !Number.isFinite(number)) return "Chỗ đã chọn";
  return seatClass?.startsWith("NAM_") ? `Giường ${number}` : `Ghế ${number}`;
}

// Phải khớp DERIVED_UI_LAYOUT_V1 trong migration V9; đây chỉ là nhãn UI,
// seat_id/seat_index nguồn vẫn được giữ nguyên khi gửi model và API.
const DERIVED_SEAT_LAYOUT: Record<string, { firstCoach: number; capacity: number }> = {
  NGOI_MEM_DH: { firstCoach: 1, capacity: 56 },
  NAM_K6: { firstCoach: 4, capacity: 42 },
  NAM_K4: { firstCoach: 6, capacity: 28 },
};

const STATION_NAMES: Record<string, string> = {
  HNO: "Hà Nội", PLY: "Phủ Lý", NDI: "Nam Định", NBI: "Ninh Bình",
  BSO: "Bỉm Sơn", THO: "Thanh Hóa", VIN: "Vinh", YTR: "Yên Trung",
  HPO: "Hương Phố", DLE: "Đồng Lê", DHO: "Đồng Hới", DHA: "Đông Hà",
  HUE: "Huế", DNA: "Đà Nẵng", TKY: "Tam Kỳ", QNG: "Quảng Ngãi",
  DTR: "Diêu Trì", THA: "Tuy Hòa", GIA: "Giã", NTR: "Nha Trang",
  TCH: "Tháp Chàm", BTH: "Bình Thuận", BHO: "Biên Hòa", DAN: "Dĩ An",
  SGO: "Sài Gòn",
};

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
