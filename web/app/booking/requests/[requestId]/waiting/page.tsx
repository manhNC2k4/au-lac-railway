"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { BrainCircuit, Check, Clock3, Loader2, ShieldCheck, XCircle } from "lucide-react";
import { getApi, qk } from "@/api";
import { BookingHeader, BookingSteps, JourneyBanner, PassengerPage } from "@/components/passenger-layout";
import { ErrorState } from "@/components/error-state";
import { BOOKING_STATUS_LABEL } from "@/lib/constants";
import { cn } from "@/lib/utils";

const PROGRESS = [
  { key: "SUBMITTED", label: "Đã tiếp nhận", icon: Check },
  { key: "AI_PROCESSING", label: "AI phân tích ghế và giá", icon: BrainCircuit },
  { key: "PENDING_ADMIN", label: "Chờ nhân viên duyệt", icon: ShieldCheck },
] as const;

export default function BookingWaitingPage() {
  const api = getApi();
  const router = useRouter();
  const params = useParams<{ requestId: string }>();
  const requestId = decodeURIComponent(params.requestId);
  const query = useQuery({
    queryKey: qk.bookingRequest(requestId),
    queryFn: () => api.getBookingRequest(requestId),
    refetchInterval: 2_000,
  });
  const cancel = useMutation({
    mutationFn: () => api.cancelBookingRequest(requestId),
    onSuccess: () => query.refetch(),
  });

  useEffect(() => {
    if (query.data?.status === "APPROVED") {
      router.replace(`/booking/requests/${encodeURIComponent(requestId)}/offers`);
    }
  }, [query.data?.status, requestId, router]);

  if (query.isPending) {
    return <PassengerPage><div className="mx-auto flex min-h-[70vh] max-w-xl items-center justify-center"><Loader2 className="h-9 w-9 animate-spin text-primary" aria-label="Đang tải yêu cầu" /></div></PassengerPage>;
  }
  if (query.isError || !query.data) {
    return <PassengerPage><div className="mx-auto max-w-xl pt-16"><ErrorState error={query.error} onRetry={() => query.refetch()} /></div></PassengerPage>;
  }

  const request = query.data;
  const rejected = request.status === "REJECTED" || request.status === "EXPIRED";
  const currentIndex = request.status === "SUBMITTED" ? 0 : request.status === "AI_PROCESSING" ? 1 : 2;

  return (
    <PassengerPage>
      <div className="space-y-3">
        <BookingHeader />
        <JourneyBanner request={request} />
        <BookingSteps current={2} />
        <main className="mx-auto grid max-w-[1120px] gap-4 lg:grid-cols-[1fr_320px]">
          <section className="rounded-lg border border-line bg-white p-5 shadow-card sm:p-7">
            {rejected ? (
              <div className="py-5 text-center">
                <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-danger-soft text-danger"><XCircle className="h-7 w-7" /></span>
                <h1 className="mt-4 text-2xl font-bold text-ink">Yêu cầu chưa được chấp thuận</h1>
                <p className="mx-auto mt-2 max-w-lg text-sm text-muted">{request.reject_reason ?? "Yêu cầu đã hết thời gian xử lý."}</p>
                <Link href="/booking" className="mt-6 inline-flex min-h-11 items-center rounded-lg bg-primary px-5 font-semibold text-white">Tìm hành trình khác</Link>
              </div>
            ) : (
              <>
                <div className="flex items-start gap-4 border-b border-line pb-5">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary"><Clock3 className="h-6 w-6" /></span>
                  <div>
                    <h1 className="text-2xl font-bold text-ink">Yêu cầu đang được xử lý</h1>
                    <p className="mt-1 text-sm leading-6 text-muted">Giá và vị trí ghế chỉ hiển thị sau khi nhân viên kiểm tra đề xuất của AI.</p>
                  </div>
                </div>
                <ol className="mt-6 space-y-3">
                  {PROGRESS.map((step, index) => {
                    const Icon = step.icon;
                    const done = index < currentIndex;
                    const active = index === currentIndex;
                    return (
                      <li key={step.key} className={cn("flex min-h-[66px] items-center gap-4 rounded-lg border px-4", done && "border-success/30 bg-success-soft", active && "border-primary/35 bg-primary-soft", !done && !active && "border-line bg-surface")}>
                        <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", done ? "bg-success text-white" : active ? "bg-primary text-white" : "bg-white text-muted")}>
                          {active && step.key !== "PENDING_ADMIN" ? <Loader2 className="h-5 w-5 animate-spin" /> : <Icon className="h-5 w-5" />}
                        </span>
                        <div className="min-w-0 flex-1"><strong className="block text-sm text-ink">{step.label}</strong><span className="text-xs text-muted">{done ? "Hoàn tất" : active ? "Đang xử lý" : "Chưa bắt đầu"}</span></div>
                      </li>
                    );
                  })}
                </ol>
              </>
            )}
          </section>

          <aside className="rounded-lg border border-line bg-white p-5 shadow-card">
            <p className="text-xs font-semibold uppercase text-muted">Mã yêu cầu</p>
            <p className="mt-2 break-all font-mono text-sm font-semibold text-ink">{request.request_id}</p>
            <dl className="mt-5 space-y-3 border-t border-line pt-4 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-muted">Số khách</dt><dd className="font-semibold text-ink">{request.quantity}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">Trạng thái</dt><dd className="text-right font-semibold text-primary">{BOOKING_STATUS_LABEL[request.status] ?? request.status}</dd></div>
            </dl>
            {!rejected && (
              <button type="button" disabled={cancel.isPending} onClick={() => cancel.mutate()} className="mt-6 min-h-11 w-full rounded-lg border border-danger/40 font-semibold text-danger hover:bg-danger-soft disabled:opacity-50">
                {cancel.isPending ? "Đang huỷ…" : "Huỷ yêu cầu"}
              </button>
            )}
            {cancel.isError && <div className="mt-3"><ErrorState compact error={cancel.error} onRetry={() => cancel.reset()} /></div>}
          </aside>
        </main>
      </div>
    </PassengerPage>
  );
}
