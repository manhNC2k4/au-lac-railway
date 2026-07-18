"use client";

import { forwardRef, useMemo } from "react";
import { CheckCircle2, Circle, Clock } from "lucide-react";
import type { SeatmapSeat, SeatState } from "@/api/types";
import type { RunSegment } from "@/lib/current-run";
import { cn } from "@/lib/utils";

/**
 * Ma trận 40 ghế × 7 chặng — ô kiểu pill có icon (theo mockup):
 * Còn trống = viền + vòng tròn rỗng · Đang giữ = vàng + đồng hồ ·
 * Đã bán = navy + check · Khoảng tái sử dụng = viền nét đứt xanh + mũi tên vòng.
 * Màu không bao giờ là tín hiệu duy nhất; mỗi ô focus được bằng bàn phím.
 */

export type CellVisualState = SeatState;

const CELL: Record<CellVisualState, { label: string; className: string; icon: React.ReactNode }> = {
  FREE: {
    label: "Còn trống",
    className: "bg-white border-line text-primary/70 hover:border-primary/50",
    icon: <Circle className="h-4 w-4" aria-hidden />,
  },
  HELD: {
    label: "Đang giữ",
    className: "bg-warning-soft border-warning/50 text-warning",
    icon: <Clock className="h-4 w-4" aria-hidden />,
  },
  SOLD: {
    label: "Đã bán",
    className: "bg-navy border-navy text-white",
    icon: <CheckCircle2 className="h-4 w-4" aria-hidden />,
  },
};

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
            <span
              aria-hidden
              className={cn("inline-flex h-7 w-9 items-center justify-center rounded-lg border", c.className)}
            >
              {c.icon}
            </span>
            {c.label}
          </li>
        );
      })}
    </ul>
  );
}

/** Thanh tuyến ga "Hà Nội → Ninh Bình → …" theo mockup — dựng động theo ga dừng của chuyến. */
export function RouteBar({ segments }: { segments: RunSegment[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-line bg-white px-4 py-2.5 text-[13.5px] font-medium text-ink">
      {segments.map((seg, i) => (
        <span key={seg.segment_id} className="flex items-center gap-2">
          {i === 0 && <span>{seg.from.station_name}</span>}
          <span aria-hidden className="text-muted">→</span>
          <span>{seg.to.station_name}</span>
        </span>
      ))}
    </div>
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
  /** seat_id cần làm nổi bật (vd golden gap C01-S017). */
  highlightSeatId?: string;
  onCellSelect?: (seat: SeatmapSeat, segmentId: number, state: CellVisualState) => void;
  selected?: { seatId: string; segmentId: number } | null;
}

export const SeatHeatmap = forwardRef<HTMLTableRowElement, SeatHeatmapProps>(function SeatHeatmap(
  { seats, segments, highlightSeatId, onCellSelect, selected },
  highlightRowRef,
) {
  const segmentIds = useMemo(() => segments.map((s) => s.segment_id), [segments]);
  const segmentById = useMemo(() => new Map(segments.map((s) => [s.segment_id, s])), [segments]);

  return (
    <div
      className="overflow-x-auto rounded-xl border border-line bg-white"
      role="region"
      aria-label="Ma trận ghế theo chặng"
      tabIndex={0}
    >
      <table className="w-full min-w-[680px] border-collapse text-sm">
        <thead>
          <tr>
            <th
              scope="col"
              className="sticky left-0 z-10 border-b border-r border-line bg-white px-4 py-2.5 text-left font-semibold text-ink"
            >
              Mã ghế
            </th>
            {segmentIds.map((id) => {
              const seg = segmentById.get(id);
              return (
                <th key={id} scope="col" className="border-b border-line px-1 py-2 text-center font-semibold text-ink">
                  <div className="text-[12.5px]">{seg?.from.station_name ?? `L${id}`}–</div>
                  <div className="text-[12.5px]">{seg?.to.station_name ?? ""}</div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {seats.map((seat) => {
            const isHighlight = seat.seat_id === highlightSeatId;
            return (
              <tr
                key={seat.seat_id}
                ref={isHighlight ? highlightRowRef : undefined}
                className={cn(isHighlight && "bg-primary-soft/50")}
              >
                <th
                  scope="row"
                  className={cn(
                    "sticky left-0 z-10 border-b border-r border-line bg-white px-4 py-1.5 text-left font-medium tabular-nums text-ink",
                    isHighlight && "bg-primary-soft font-semibold text-primary",
                  )}
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
                          "inline-flex h-9 w-full min-w-[52px] items-center justify-center rounded-lg border",
                          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary",
                          c.className,
                          isSelected && "ring-2 ring-primary ring-offset-1",
                        )}
                      >
                        {c.icon}
                      </button>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
});
