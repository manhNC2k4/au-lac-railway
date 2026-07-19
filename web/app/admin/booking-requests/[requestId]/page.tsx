"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Armchair, Check, ShieldCheck, Sparkles, X } from "lucide-react";
import { getApi, qk, type BookingCandidateData } from "@/api";
import { ErrorState } from "@/components/error-state";
import { Money } from "@/components/money";
import { PageHeader } from "@/components/page-header";
import { formatDemoTime } from "@/lib/format";
import { BOOKING_STATUS_LABEL, SEAT_CLASS_LABEL, seatDisplayName } from "@/lib/constants";

export default function BookingRequestReviewPage() {
  const api = getApi();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useParams<{ requestId: string }>();
  const requestId = decodeURIComponent(params.requestId);
  const [selected, setSelected] = useState<string[]>([]);
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const query = useQuery({ queryKey: qk.adminBookingRequest(requestId), queryFn: () => api.getAdminBookingRequest(requestId) });
  const suggestedId = useMemo(() => query.data?.candidates.find((candidate) => candidate.ai_recommended)?.candidate_id, [query.data]);
  const effectiveSelected = selected.length ? selected : suggestedId ? [suggestedId] : [];

  const approve = useMutation({
    mutationFn: () => api.approveBookingRequest(requestId, {
      decided_by: "revenue_manager",
      approved_candidates: effectiveSelected.map((candidateId) => ({
        candidate_id: candidateId,
        ...(prices[candidateId] ? { override_price_vnd: Number(prices[candidateId]) } : {}),
        ...(note.trim() ? { reason: note.trim() } : {}),
      })),
      ...(note.trim() ? { note: note.trim() } : {}),
    }),
    onSuccess: (data) => {
      queryClient.setQueryData(qk.adminBookingRequest(requestId), data);
      queryClient.invalidateQueries({ queryKey: ["bookingQueue"] });
    },
  });
  const reject = useMutation({
    mutationFn: () => api.rejectBookingRequest(requestId, rejectReason.trim(), "revenue_manager"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bookingQueue"] });
      router.push("/admin/booking-requests");
    },
  });

  if (query.isPending) return <div className="py-16 text-center text-muted">Đang tải yêu cầu…</div>;
  if (query.isError || !query.data) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  const request = query.data;
  const canReview = request.status === "PENDING_ADMIN";

  const toggle = (candidate: BookingCandidateData) => {
    setSelected((current) => {
      const base = current.length ? current : suggestedId ? [suggestedId] : [];
      return base.includes(candidate.candidate_id) ? base.filter((id) => id !== candidate.candidate_id) : [...base, candidate.candidate_id];
    });
  };

  return (
    <div>
      <Link href="/admin/booking-requests" className="mb-4 inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-primary"><ArrowLeft className="h-4 w-4" />Hàng đợi duyệt</Link>
      <PageHeader title={`${request.origin_station_id} → ${request.dest_station_id}`} description={`${request.request_id} · ${request.service_run_id} · gửi lúc ${formatDemoTime(request.submitted_at)}`} />
      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <section>
          <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold text-ink">Phương án AI đề xuất</h2><span className="rounded-lg bg-primary-soft px-3 py-1.5 text-xs font-semibold text-primary">{request.candidates.length} phương án</span></div>
          <div className="grid gap-3 lg:grid-cols-2">
            {request.candidates.map((candidate) => {
              const checked = effectiveSelected.includes(candidate.candidate_id);
              return <article key={candidate.candidate_id} className={`rounded-lg border bg-white p-4 shadow-card ${checked ? "border-primary ring-2 ring-primary/15" : "border-line"}`}>
                <div className="flex items-center justify-between gap-3"><label className="flex items-center gap-2 font-semibold text-ink"><input type="checkbox" disabled={!canReview} checked={checked} onChange={() => toggle(candidate)} className="h-4 w-4 accent-primary" />Phương án {candidate.rank}</label>{candidate.ai_recommended && <span className="inline-flex items-center gap-1 rounded-lg bg-primary-soft px-2 py-1 text-xs font-semibold text-primary"><Sparkles className="h-3.5 w-3.5" />AI ưu tiên</span>}</div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">{candidate.seat_plan.map((seat) => <div key={seat.seat_id} className="flex items-center gap-2 rounded-lg bg-surface px-3 py-2"><Armchair className="h-4 w-4 shrink-0 text-primary" /><span className="min-w-0"><strong className="block text-xs text-ink">{seatDisplayName(seat.seat_id, request.seat_class)}</strong><span className="block truncate font-mono text-[11px] text-muted">{seat.seat_id}</span></span></div>)}</div>
                <div className="mt-4 grid grid-cols-3 gap-2 border-t border-line pt-3">
                  <AdminPrice label="Giá cơ sở" amount={candidate.pricing.gia_goc_vnd} />
                  <AdminPrice label="AI đề xuất" amount={candidate.pricing.gia_niem_yet_vnd} />
                  <AdminPrice label={canReview ? "Dự kiến duyệt" : "Đã duyệt"} amount={prices[candidate.candidate_id] ? Number(prices[candidate.candidate_id]) : candidate.approved_price_vnd ?? candidate.pricing.gia_cuoi_vnd} approved />
                </div>
                {canReview && checked && <label className="mt-3 block text-xs font-semibold text-muted">Giá admin duyệt<input type="number" min={1} step={1000} value={prices[candidate.candidate_id] ?? ""} onChange={(event) => setPrices((current) => ({ ...current, [candidate.candidate_id]: event.target.value }))} placeholder={String(candidate.pricing.gia_cuoi_vnd)} className="mt-1 min-h-11 w-full rounded-lg border border-line px-3 text-sm text-ink outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" /><span className="mt-1 block font-normal">Để trống để giữ mức hệ thống đang đề nghị duyệt.</span></label>}
              </article>;
            })}
          </div>
        </section>

        <aside className="h-fit rounded-lg border border-line bg-white p-5 shadow-card xl:sticky xl:top-[110px]">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-ink"><ShieldCheck className="h-5 w-5 text-primary" />Quyết định duyệt</h2>
          <dl className="mt-4 space-y-3 text-sm"><div className="flex justify-between gap-3"><dt className="text-muted">Hạng ghế</dt><dd className="text-right font-semibold text-ink">{SEAT_CLASS_LABEL[request.seat_class] ?? request.seat_class}</dd></div><div className="flex justify-between gap-3"><dt className="text-muted">Hành khách</dt><dd className="font-semibold text-ink">{request.quantity}</dd></div><div className="flex justify-between gap-3"><dt className="text-muted">Trạng thái</dt><dd className="text-right font-semibold text-primary">{BOOKING_STATUS_LABEL[request.status] ?? request.status}</dd></div></dl>
          {canReview ? <>
            <label className="mt-5 block text-sm font-semibold text-ink">Ghi chú quyết định<textarea value={note} onChange={(event) => setNote(event.target.value)} rows={3} className="mt-1 w-full resize-none rounded-lg border border-line p-3 text-sm font-normal outline-none focus:border-primary focus:ring-2 focus:ring-primary/15" /></label>
            <button type="button" disabled={!effectiveSelected.length || approve.isPending} onClick={() => approve.mutate()} className="mt-4 flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary font-semibold text-white hover:bg-primary-dark disabled:opacity-50"><Check className="h-4 w-4" />{approve.isPending ? "Đang duyệt…" : `Duyệt ${effectiveSelected.length} phương án`}</button>
            <div className="my-5 border-t border-line" />
            <label className="block text-sm font-semibold text-ink">Lý do từ chối<input value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} className="mt-1 min-h-11 w-full rounded-lg border border-line px-3 font-normal outline-none focus:border-danger" /></label>
            <button type="button" disabled={rejectReason.trim().length < 3 || reject.isPending} onClick={() => reject.mutate()} className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-danger/50 font-semibold text-danger hover:bg-danger-soft disabled:opacity-50"><X className="h-4 w-4" />Từ chối yêu cầu</button>
          </> : <p className="mt-5 rounded-lg bg-surface p-4 text-sm text-muted">Yêu cầu này đã được xử lý và không thể quyết định lại.</p>}
          {(approve.isError || reject.isError) && <div className="mt-4"><ErrorState compact error={approve.error ?? reject.error} onRetry={() => { approve.reset(); reject.reset(); }} /></div>}
        </aside>
      </div>
    </div>
  );
}

function AdminPrice({ label, amount, approved = false }: { label: string; amount: number; approved?: boolean }) {
  return <div className={approved ? "rounded-lg bg-success-soft p-2" : "rounded-lg bg-surface p-2"}><span className="block text-[11px] leading-4 text-muted">{label}</span><strong className="mt-1 block text-xs tabular-nums text-ink"><Money amount={amount} /></strong></div>;
}
