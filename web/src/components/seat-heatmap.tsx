"use client";

import { useMemo, useState } from "react";
import { Armchair, CheckCircle2, ChevronDown, Clock } from "lucide-react";
import type { SeatmapSeat, SeatState } from "@/api/types";
import type { RunSegment } from "@/lib/current-run";
import { cn } from "@/lib/utils";

/** Số ghế hiện mặc định mỗi nhóm hạng ghế trước khi phải bấm "Hiện thêm". */
const PAGE_SIZE = 50;

/** Gom ghế theo seat_class, giữ nguyên thứ tự xuất hiện đầu tiên (đã sort theo seat_id từ API). */
function groupByClass(seats: SeatmapSeat[]): Map<string, SeatmapSeat[]> {
  const groups = new Map<string, SeatmapSeat[]>();
  for (const seat of seats) {
    const key = seat.seat_class || "—";
    const list = groups.get(key);
    if (list) list.push(seat);
    else groups.set(key, [seat]);
  }
  return groups;
}

/**
 * Ma trận 40 ghế × 7 chặng — mỗi ô là hình cái ghế trần, không khung/box (theo mockup):
 * Còn trống = ghế rỗng xám nhạt · Đang giữ = ghế vàng + badge đồng hồ ·
 * Đã bán = ghế navy đặc + badge check.
 * Màu không bao giờ là tín hiệu duy nhất — badge góc giữ vai trò phân biệt phi-màu-sắc.
 */

export type CellVisualState = SeatState;

const CELL: Record<
  CellVisualState,
  { label: string; iconClassName: string; badge: React.ReactNode }
> = {
  FREE: {
    label: "Còn trống",
    iconClassName: "text-muted fill-transparent",
    badge: null,
  },
  HELD: {
    label: "Đang giữ",
    iconClassName: "text-warning fill-warning/20",
    badge: <Clock className="h-3 w-3" aria-hidden />,
  },
  SOLD: {
    label: "Đã bán",
    iconClassName: "text-navy fill-navy",
    badge: <CheckCircle2 className="h-3 w-3" aria-hidden />,
  },
};

function SeatGlyph({ state }: { state: CellVisualState }) {
  const c = CELL[state];
  return (
    <span className="relative inline-flex">
      <Armchair className={cn("h-6 w-6", c.iconClassName)} aria-hidden />
      {c.badge && (
        <span
          aria-hidden
          className={cn(
            "absolute -right-1.5 -top-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full",
            state === "SOLD" ? "bg-navy text-white" : "bg-warning-soft text-warning",
          )}
        >
          {c.badge}
        </span>
      )}
    </span>
  );
}

export function HeatmapLegend() {
  return (
    <ul
      className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-line bg-white px-4 py-2.5"
      aria-label="Chú giải trạng thái ô"
    >
      {(Object.keys(CELL) as CellVisualState[]).map((key) => {
        const c = CELL[key];
        return (
          <li key={key} className="flex items-center gap-2 text-[13px] text-ink">
            <SeatGlyph state={key} />
            {c.label}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Thanh tuyến ga "Hà Nội → Ninh Bình → …" — sơ đồ tuyến kiểu bản đồ metro: chấm ga
 * nối bằng đường line ngang, xếp lưới đều (grid, không phải flex) để line thẳng
 * hàng khi tuyến dài (vd 22 ga) tự xuống dòng — thấy hết cả tuyến, không cần kéo.
 * Ga đầu/cuối chấm to + tô đậm để dễ định vị điểm xuất phát/kết thúc.
 */
export function RouteBar({ segments }: { segments: RunSegment[] }) {
  const stations = useMemo(() => {
    if (segments.length === 0) return [];
    return [segments[0].from, ...segments.map((s) => s.to)];
  }, [segments]);

  return (
    <ol
      className="grid gap-x-0 gap-y-4 rounded-xl border border-line bg-white px-4 py-4"
      style={{ gridTemplateColumns: "repeat(auto-fill, minmax(84px, 1fr))" }}
      aria-label="Tuyến ga của chuyến"
    >
      {stations.map((station, i) => {
        const isFirst = i === 0;
        const isLast = i === stations.length - 1;
        const isEndpoint = isFirst || isLast;
        return (
          <li key={station.station_id} className="flex flex-col items-center gap-1.5 px-1.5">
            <div className="relative flex h-2.5 w-full items-center justify-center">
              {!isFirst && (
                <span aria-hidden className="absolute left-0 right-1/2 top-1/2 h-px -translate-y-1/2 bg-line" />
              )}
              {!isLast && (
                <span aria-hidden className="absolute left-1/2 right-0 top-1/2 h-px -translate-y-1/2 bg-line" />
              )}
              <span
                aria-hidden
                className={cn(
                  "relative z-10 shrink-0 rounded-full ring-2 ring-white",
                  isEndpoint ? "h-2.5 w-2.5 bg-primary" : "h-2 w-2 bg-muted",
                )}
              />
            </div>
            <span
              className={cn(
                "truncate text-center text-[12px] leading-tight",
                isEndpoint ? "font-semibold text-primary" : "text-ink",
              )}
              title={station.station_name}
            >
              {station.station_name}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function cellState(seat: SeatmapSeat, segmentId: number): CellVisualState {
  const raw = (seat.states?.[String(segmentId)] ?? "FREE") as SeatState;
  return raw;
}

export function cellLabel(state: CellVisualState): string {
  return CELL[state].label;
}

interface SeatHeatmapProps {
  seats: SeatmapSeat[];
  segments: RunSegment[];
  onCellSelect?: (seat: SeatmapSeat, segmentId: number, state: CellVisualState) => void;
  selected?: { seatId: string; segmentId: number } | null;
}

export function SeatHeatmap({ seats, segments, onCellSelect, selected }: SeatHeatmapProps) {
  const segmentIds = useMemo(() => segments.map((s) => s.segment_id), [segments]);
  const segmentById = useMemo(() => new Map(segments.map((s) => [s.segment_id, s])), [segments]);
  const groups = useMemo(() => groupByClass(seats), [seats]);
  const classNames = useMemo(() => Array.from(groups.keys()), [groups]);
  const firstClassName = classNames[0];

  // Nhóm đầu tiên mở mặc định.
  const [openOverrides, setOpenOverrides] = useState<Record<string, boolean>>({});
  const isOpen = (name: string) => openOverrides[name] ?? name === firstClassName;

  // Mỗi nhóm chỉ hiện PAGE_SIZE ghế đầu, trừ phi user bấm "Hiện thêm".
  const [visibleOverrides, setVisibleOverrides] = useState<Record<string, number>>({});
  const visibleCount = (name: string, total: number) => Math.min(visibleOverrides[name] ?? Math.min(PAGE_SIZE, total), total);

  const columnCount = segmentIds.length + 1;

  function renderSeatRow(seat: SeatmapSeat) {
    return (
      <tr key={seat.seat_id}>
        <th
          scope="row"
          className="sticky left-0 z-10 border-b border-r border-line bg-white px-4 py-1.5 text-left font-medium tabular-nums text-ink"
        >
          {seat.seat_id}
        </th>
        {segmentIds.map((segId) => {
          const st = cellState(seat, segId);
          const c = CELL[st];
          const isSelected = selected?.seatId === seat.seat_id && selected?.segmentId === segId;
          return (
            <td key={segId} className="border-b border-line p-1.5 text-center">
              <button
                type="button"
                onClick={() => onCellSelect?.(seat, segId, st)}
                aria-label={`${seat.seat_id} · L${segId} ${segmentById.get(segId)?.from.station_name ?? ""} → ${segmentById.get(segId)?.to.station_name ?? ""} · ${c.label}`}
                aria-pressed={isSelected}
                className={cn(
                  "inline-flex h-9 w-full min-w-[52px] items-center justify-center rounded-lg",
                  "hover:bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary",
                  isSelected && "bg-primary-soft/60 ring-2 ring-primary ring-offset-1",
                )}
              >
                <SeatGlyph state={st} />
              </button>
            </td>
          );
        })}
      </tr>
    );
  }

  return (
    <div
      className="overflow-x-auto rounded-xl border border-line bg-white"
      role="region"
      aria-label="Ma trận ghế theo chặng"
      tabIndex={0}
    >
      <table className="border-collapse text-sm">
        <thead>
          <tr>
            <th
              scope="col"
              className="sticky left-0 top-0 z-20 min-w-[110px] border-b border-r border-line bg-white px-4 py-2.5 text-left font-semibold text-ink"
            >
              Mã ghế
            </th>
            {segmentIds.map((id) => {
              const seg = segmentById.get(id);
              const title = `${seg?.from.station_name ?? `L${id}`} → ${seg?.to.station_name ?? ""}`;
              return (
                <th
                  key={id}
                  scope="col"
                  title={title}
                  className="sticky top-0 z-20 min-w-[96px] border-b border-line bg-white px-2 py-2 text-center align-bottom font-semibold text-ink"
                >
                  <div className="truncate text-[11.5px] leading-tight text-muted">{seg?.from.station_name ?? `L${id}`}</div>
                  <div className="truncate text-[12.5px] leading-tight">{seg?.to.station_name ?? ""}</div>
                </th>
              );
            })}
          </tr>
        </thead>
        {classNames.map((name) => {
          const list = groups.get(name) ?? [];
          const open = isOpen(name);
          const visible = visibleCount(name, list.length);
          const remaining = list.length - visible;
          return (
            <tbody key={name}>
              <tr>
                <th scope="colgroup" colSpan={columnCount} className="border-b border-line bg-surface p-0 text-left">
                  {/* sticky left-0 (thay vì w-full) — nút toggle luôn hiện ở mép trái, không cần cuộn ngang mới thấy được */}
                  <button
                    type="button"
                    onClick={() => setOpenOverrides((prev) => ({ ...prev, [name]: !open }))}
                    aria-expanded={open}
                    className="sticky left-0 z-0 flex items-center gap-6 px-4 py-2 font-semibold text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                  >
                    <span>
                      {name} · {list.length} ghế
                    </span>
                    <ChevronDown
                      className={cn("h-4 w-4 shrink-0 transition-transform", open && "rotate-180")}
                      aria-hidden
                    />
                  </button>
                </th>
              </tr>
              {open && list.slice(0, visible).map(renderSeatRow)}
              {open && remaining > 0 && (
                <tr>
                  {/* sticky left-0 (thay vì text-center trên cả colSpan) — nút luôn hiện ở mép trái, không cần cuộn ngang mới thấy được */}
                  <td colSpan={columnCount} className="border-b border-line p-0 text-left">
                    <button
                      type="button"
                      onClick={() =>
                        setVisibleOverrides((prev) => ({
                          ...prev,
                          [name]: Math.min(list.length, visible + PAGE_SIZE),
                        }))
                      }
                      className="sticky left-0 z-0 px-4 py-2 text-sm font-medium text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                    >
                      Hiện thêm {Math.min(PAGE_SIZE, remaining)} ghế
                    </button>
                  </td>
                </tr>
              )}
            </tbody>
          );
        })}
      </table>
    </div>
  );
}
