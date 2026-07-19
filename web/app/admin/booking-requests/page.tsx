"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock3, RefreshCw, Sparkles } from "lucide-react";
import { getApi, qk, type BookingRequestStatus } from "@/api";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { formatDemoTime, formatVnd } from "@/lib/format";
import { SEAT_CLASS_LABEL } from "@/lib/constants";

const FILTERS: { value: BookingRequestStatus; label: string }[] = [
  { value: "PENDING_ADMIN", label: "Chờ duyệt" },
  { value: "APPROVED", label: "Đã duyệt" },
  { value: "SELECTED", label: "Đã chọn ghế" },
  { value: "CONFIRMED", label: "Đã thanh toán" },
  { value: "REJECTED", label: "Từ chối" },
];

export default function BookingRequestQueuePage() {
  const api = getApi();
  const [status, setStatus] = useState<BookingRequestStatus>("PENDING_ADMIN");
  const query = useQuery({
    queryKey: qk.bookingQueue(status),
    queryFn: () => api.listAdminBookingRequests(status),
    refetchInterval: status === "PENDING_ADMIN" ? 3_000 : false,
  });

  return (
    <div>
      <PageHeader
        title="Yêu cầu đặt vé"
        description="Duyệt ghế và giá do AI đề xuất trước khi phương án được gửi tới hành khách."
        actions={<button type="button" onClick={() => query.refetch()} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-primary px-4 text-sm font-semibold text-primary hover:bg-primary-soft"><RefreshCw className="h-4 w-4" />Làm mới</button>}
      />
      <div className="mb-4 flex gap-1 overflow-x-auto border-b border-line" role="tablist" aria-label="Lọc trạng thái yêu cầu">
        {FILTERS.map((filter) => <button key={filter.value} type="button" role="tab" aria-selected={status === filter.value} onClick={() => setStatus(filter.value)} className={`min-h-11 shrink-0 border-b-2 px-4 text-sm font-semibold ${status === filter.value ? "border-primary text-primary" : "border-transparent text-muted hover:text-ink"}`}>{filter.label}</button>)}
      </div>

      {query.isError ? <ErrorState error={query.error} onRetry={() => query.refetch()} /> : (
        <section className="overflow-hidden rounded-lg border border-line bg-white shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-surface text-xs font-semibold uppercase text-muted"><tr><th className="px-4 py-3">Yêu cầu</th><th className="px-4 py-3">Hành trình</th><th className="px-4 py-3">Hạng / khách</th><th className="px-4 py-3">Giá AI</th><th className="px-4 py-3">Thời điểm</th><th className="w-16 px-4 py-3"><span className="sr-only">Thao tác</span></th></tr></thead>
              <tbody className="divide-y divide-line">
                {query.isPending && <tr><td colSpan={6} className="px-4 py-10 text-center text-muted">Đang tải hàng đợi…</td></tr>}
                {query.data?.requests.map((request) => {
                  const ai = request.candidates.find((candidate) => candidate.ai_recommended) ?? request.candidates[0];
                  return <tr key={request.request_id} className="hover:bg-primary-soft/40">
                    <td className="px-4 py-4"><strong className="block font-mono text-xs text-ink">{request.request_id}</strong><span className="mt-1 inline-flex items-center gap-1 text-xs text-primary"><Sparkles className="h-3.5 w-3.5" />{request.candidates.length} phương án</span></td>
                    <td className="px-4 py-4"><strong className="text-ink">{request.origin_station_id} → {request.dest_station_id}</strong><span className="block text-xs text-muted">{request.service_run_id}</span></td>
                    <td className="px-4 py-4"><span className="block text-ink">{SEAT_CLASS_LABEL[request.seat_class] ?? request.seat_class}</span><span className="text-xs text-muted">{request.quantity} khách</span></td>
                    <td className="px-4 py-4 font-semibold text-ink">{ai ? formatVnd(ai.pricing.gia_cuoi_vnd) : "-"}</td>
                    <td className="px-4 py-4"><span className="inline-flex items-center gap-1.5 text-muted"><Clock3 className="h-4 w-4" />{formatDemoTime(request.submitted_at)}</span></td>
                    <td className="px-4 py-4"><Link href={`/admin/booking-requests/${encodeURIComponent(request.request_id)}`} aria-label={`Mở ${request.request_id}`} className="flex h-10 w-10 items-center justify-center rounded-lg border border-primary text-primary hover:bg-primary-soft"><ArrowRight className="h-4 w-4" /></Link></td>
                  </tr>;
                })}
                {!query.isPending && query.data?.requests.length === 0 && <tr><td colSpan={6} className="px-4 py-12 text-center text-muted">Không có yêu cầu ở trạng thái này.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
