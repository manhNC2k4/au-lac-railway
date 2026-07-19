"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Filter, X, ChevronDown } from "lucide-react";
import { getApi, qk, type SeatmapSeat } from "@/api";
import { segmentLabel, useCurrentRun } from "@/lib/current-run";
import { ErrorState } from "@/components/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { SeatHeatmap, HeatmapLegend, RouteBar, cellLabel, type CellVisualState } from "@/components/seat-heatmap";
import { StatusBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";

type StatusFilter = "ALL" | "FREE" | "HELD" | "SOLD";

const FILTERS: { value: StatusFilter; label: string }[] = [
  { value: "ALL", label: "Tất cả" },
  { value: "FREE", label: "Còn trống" },
  { value: "HELD", label: "Đang giữ" },
  { value: "SOLD", label: "Đã bán" },
];

export default function SeatmapPage() {
  const api = getApi();
  const { serviceRunId, segments } = useCurrentRun();
  const [filter, setFilter] = useState<StatusFilter>("ALL");
  const [techOpen, setTechOpen] = useState(true);
  const [selected, setSelected] = useState<{
    seat: SeatmapSeat;
    segmentId: number;
    state: CellVisualState;
  } | null>(null);

  const seatmap = useQuery({
    queryKey: qk.seatmap(serviceRunId),
    queryFn: () => api.getSeatmap(serviceRunId),
  });

  const seats = useMemo(() => seatmap.data?.seats ?? [], [seatmap.data]);

  const filteredSeats = useMemo(() => {
    if (filter === "ALL") return seats;
    return seats.filter((seat) => {
      return Object.values(seat.states ?? {}).includes(filter);
    });
  }, [seats, filter]);

  const classLabel = useMemo(() => {
    const classes = Array.from(new Set(seats.map((s) => s.seat_class)));
    return classes.join(" · ") || "—";
  }, [seats]);

  if (seatmap.isPending) return <PageSkeleton />;
  if (seatmap.isError) return <ErrorState error={seatmap.error} onRetry={() => seatmap.refetch()} />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[26px] font-bold text-ink">Ma trận trạng thái ghế theo chặng</h1>
        <p className="mt-1 text-sm text-muted">Theo dõi một ghế được sử dụng trên từng chặng của hành trình.</p>
      </div>

      <RouteBar segments={segments} />

      {/* Bộ lọc */}
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Lọc theo trạng thái">
        <span className="flex items-center gap-1.5 text-sm text-muted">
          <Filter className="h-4 w-4" aria-hidden /> Lọc:
        </span>
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFilter(f.value)}
            aria-pressed={filter === f.value}
            className={cn(
              "min-h-[36px] rounded-full border px-3.5 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary",
              filter === f.value
                ? "border-primary bg-primary text-white"
                : "border-line bg-white text-ink hover:bg-primary-soft",
            )}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-[13px] tabular-nums text-muted">
          {filteredSeats.length}/{seats.length} ghế · {classLabel}
        </span>
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-3">
          {filteredSeats.length === 0 ? (
            <Card>
              <CardBody className="py-10 text-center">
                <p className="text-sm text-muted">Không có ghế nào khớp bộ lọc.</p>
                <Button size="sm" variant="secondary" className="mt-3" onClick={() => setFilter("ALL")}>
                  Xóa bộ lọc
                </Button>
              </CardBody>
            </Card>
          ) : (
            <SeatHeatmap
              seats={filteredSeats}
              segments={segments}
              selected={selected ? { seatId: selected.seat.seat_id!, segmentId: selected.segmentId } : null}
              onCellSelect={(seat, segmentId, state) => setSelected({ seat, segmentId, state })}
            />
          )}
          <HeatmapLegend />
        </div>

        {/* Chi tiết ô đã chọn */}
        <div className="min-w-0 space-y-3">
          <Card>
            <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
              <h2 className="text-[16px] font-semibold text-ink">Chi tiết ô đã chọn</h2>
              {selected && (
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  aria-label="Bỏ chọn ô"
                  className="rounded-lg p-1.5 text-muted hover:bg-surface hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                >
                  <X className="h-4 w-4" aria-hidden />
                </button>
              )}
            </div>
            <CardBody className="space-y-3 text-sm">
              {!selected ? (
                <p className="text-muted">Bấm vào một ô trong ma trận để xem chi tiết.</p>
              ) : (
                <>
                  <DetailRow label="Mã ghế">
                    <span className="text-[15px] font-semibold tabular-nums text-ink">{selected.seat.seat_id}</span>
                  </DetailRow>
                  <DetailRow label="Chặng">
                    <span className="font-medium text-ink">{segmentLabel(segments, selected.segmentId)}</span>
                  </DetailRow>
                  <DetailRow label="Trạng thái">
                    <StatusBadge status={selected.state} label={cellLabel(selected.state)} />
                  </DetailRow>
                </>
              )}
            </CardBody>
          </Card>

          {selected && (
            <Card>
              <button
                type="button"
                onClick={() => setTechOpen((v) => !v)}
                aria-expanded={techOpen}
                className="flex w-full items-center justify-between px-4 py-3.5 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
              >
                <span className="text-[16px] font-semibold text-ink">Thông tin kỹ thuật</span>
                <ChevronDown className={cn("h-4 w-4 text-muted transition-transform", techOpen && "rotate-180")} aria-hidden />
              </button>
              {techOpen && (
                <CardBody className="space-y-2.5 border-t border-line text-sm">
                  <DetailRow label="Mã chặng">
                    <span className="font-mono text-[12.5px] text-ink">
                      {segments.find((s) => s.segment_id === selected.segmentId)?.from.station_id ?? "—"}-
                      {segments.find((s) => s.segment_id === selected.segmentId)?.to.station_id ?? "—"}
                    </span>
                  </DetailRow>
                  <DetailRow label="Mã chuyến">
                    <span className="font-mono text-[12px] text-ink">{serviceRunId}</span>
                  </DetailRow>
                </CardBody>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted">{label}</span>
      {children}
    </div>
  );
}
