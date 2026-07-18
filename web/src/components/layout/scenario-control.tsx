"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  X,
  FileText,
  TrainFront,
  Grid3X3,
  LineChart,
  RefreshCcw,
  RotateCcw,
  CheckCircle2,
} from "lucide-react";
import { getApi, qk, type ResetData } from "@/api";
import { GOLDEN } from "@/lib/constants";
import { ErrorState } from "@/components/error-state";
import { cn } from "@/lib/utils";

/**
 * Panel "Điều khiển kịch bản" (drawer phải) — theo mockup:
 * thông tin kịch bản, cấu hình mô phỏng (khoảng ghế mẫu), hành động
 * làm mới dự báo / đặt lại kịch bản, thông tin kỹ thuật.
 */
export function ScenarioControlDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const api = getApi();
  const queryClient = useQueryClient();
  const panelRef = useRef<HTMLDivElement>(null);
  const [applyGoldenGap, setApplyGoldenGap] = useState(true);
  const [resetInfo, setResetInfo] = useState<ResetData | null>(null);
  const [forecastVersion, setForecastVersion] = useState<number | null>(null);

  const seatmap = useQuery({
    queryKey: qk.seatmap(GOLDEN.serviceRunId),
    queryFn: () => api.getSeatmap(GOLDEN.serviceRunId),
    enabled: open,
  });

  const resetMutation = useMutation({
    mutationFn: () => api.resetScenario(GOLDEN.scenarioId, { reset_clock: true, apply_golden_gap: applyGoldenGap }),
    onSuccess: (data) => {
      setResetInfo(data);
      setForecastVersion(data.forecast_version);
      queryClient.invalidateQueries();
    },
  });

  const refreshMutation = useMutation({
    mutationFn: () => api.refreshForecast(GOLDEN.serviceRunId),
    onSuccess: (data) => {
      if (data.forecast_version) setForecastVersion(data.forecast_version);
      queryClient.invalidateQueries();
    },
  });

  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label="Điều khiển kịch bản">
      <div className="absolute inset-0 bg-navy/5" onClick={onClose} aria-hidden />
      <div
        ref={panelRef}
        tabIndex={-1}
        onKeyDown={(e) => e.key === "Escape" && onClose()}
        className="absolute inset-y-0 right-0 w-[min(532px,100vw)] overflow-y-auto rounded-l-2xl border-l border-line bg-white p-7 shadow-xl focus:outline-none"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-ink">Điều khiển kịch bản</h2>
            <p className="mt-1 text-[13px] text-muted">
              Thiết lập và làm mới dữ liệu mô phỏng cho chuyến đang vận hành.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng bảng điều khiển"
            className="rounded-lg p-2 text-muted hover:bg-surface hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
          >
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>

        {/* Thông tin kịch bản */}
        <h3 className="mt-5 text-[15px] font-semibold text-ink">Thông tin kịch bản</h3>
        <div className="mt-2.5 grid grid-cols-2 gap-2.5">
          <InfoTile icon={<FileText className="h-4 w-4" aria-hidden />} label="Mã kịch bản" value={GOLDEN.scenarioId} />
          <InfoTile icon={<TrainFront className="h-4 w-4" aria-hidden />} label="Chuyến đang vận hành" value={GOLDEN.serviceRunId} />
          <InfoTile
            icon={<Grid3X3 className="h-4 w-4" aria-hidden />}
            label="Phiên bản ma trận"
            value={seatmap.data ? String(seatmap.data.matrix_version) : "—"}
          />
          <InfoTile
            icon={<LineChart className="h-4 w-4" aria-hidden />}
            label="Phiên bản dự báo"
            value={forecastVersion === null ? "—" : String(forecastVersion)}
          />
        </div>

        {/* Cấu hình mô phỏng */}
        <div className="mt-4 rounded-2xl border border-success/30 bg-success-soft/60 p-4">
          <h3 className="text-[15px] font-semibold text-ink">Cấu hình mô phỏng</h3>
          <div className="mt-2 flex items-start justify-between gap-3">
            <div>
              <p className="text-[14px] font-medium text-ink">Kích hoạt khoảng ghế mẫu</p>
              <p className="mt-0.5 text-[12.5px] text-muted">
                Tạo sẵn một khoảng ghế trống giữa hai lượt đặt vé để kiểm thử chức năng tái sử dụng ghế.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={applyGoldenGap}
              aria-label="Kích hoạt khoảng ghế mẫu"
              onClick={() => setApplyGoldenGap((v) => !v)}
              className={cn(
                "relative h-7 w-12 shrink-0 rounded-full transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                applyGoldenGap ? "bg-primary" : "bg-line",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all",
                  applyGoldenGap ? "left-6" : "left-1",
                )}
              />
            </button>
          </div>
          {applyGoldenGap && (
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-success/40 bg-white px-2.5 py-1 text-[12.5px] font-medium text-success">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> Đã kích hoạt — áp dụng khi đặt lại kịch bản
            </p>
          )}
        </div>

        {/* Hành động */}
        <h3 className="mt-4 text-[15px] font-semibold text-ink">Hành động</h3>
        <div className="mt-2.5 space-y-2.5">
          <button
            type="button"
            disabled={refreshMutation.isPending}
            onClick={() => refreshMutation.mutate()}
            className="flex min-h-[46px] w-full items-center justify-center gap-2 rounded-xl border border-primary/40 bg-white text-[14.5px] font-semibold text-primary hover:bg-primary-soft disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
          >
            <RefreshCcw className={cn("h-4 w-4", refreshMutation.isPending && "animate-spin")} aria-hidden />
            Làm mới dự báo
          </button>
          <button
            type="button"
            disabled={resetMutation.isPending}
            onClick={() => resetMutation.mutate()}
            className="flex min-h-[46px] w-full items-center justify-center gap-2 rounded-xl bg-danger text-[14.5px] font-semibold text-white hover:bg-danger/90 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-danger"
          >
            <RotateCcw className={cn("h-4 w-4", resetMutation.isPending && "animate-spin")} aria-hidden />
            Đặt lại kịch bản
          </button>
        </div>

        {(resetMutation.isError || refreshMutation.isError) && (
          <div className="mt-3">
            <ErrorState
              compact
              error={resetMutation.error ?? refreshMutation.error}
              onRetry={() => (resetMutation.isError ? resetMutation.mutate() : refreshMutation.mutate())}
            />
          </div>
        )}
        {resetInfo && !resetMutation.isError && (
          <p className="mt-3 flex items-center gap-2 rounded-xl border border-success/30 bg-success-soft px-3 py-2 text-[13px] text-ink" role="status">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden />
            Đã đặt lại — ma trận v{resetInfo.matrix_version}, dự báo v{resetInfo.forecast_version}, chính sách v{resetInfo.policy_version}.
          </p>
        )}

        {/* Thông tin kỹ thuật */}
        <div className="mt-4 rounded-2xl border border-line p-4">
          <h3 className="text-[15px] font-semibold text-ink">Thông tin kỹ thuật</h3>
          <dl className="mt-2.5 space-y-2 text-[13px]">
            <TechRow label="Mã chuyến vận hành" value={GOLDEN.serviceRunId} mono />
            <TechRow label="Mã kiểm tra dữ liệu" value={resetInfo?.checksum ?? "—"} mono />
            <TechRow label="Ngày chạy" value={GOLDEN.serviceDate} />
          </dl>
        </div>
      </div>
    </div>
  );
}

function InfoTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line p-3">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-primary">{icon}</span>
      <p className="mt-2 text-[11.5px] text-muted">{label}</p>
      <p className="text-[14px] font-semibold tabular-nums text-ink">{value}</p>
    </div>
  );
}

function TechRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted">{label}</dt>
      <dd className={cn("text-right text-ink", mono && "font-mono text-[12px]")}>{value}</dd>
    </div>
  );
}
