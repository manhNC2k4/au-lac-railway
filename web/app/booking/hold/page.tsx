"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Armchair, CheckCircle2, Clock3 } from "lucide-react";
import { getApi, qk } from "@/api";
import { BookingSteps, JourneyBanner, PassengerPage } from "@/components/passenger-layout";
import { Countdown } from "@/components/countdown";
import { ErrorState } from "@/components/error-state";
import { Money } from "@/components/money";
import { seatDisplayName } from "@/lib/constants";
import { loadBookingSession, saveBookingSession, type BookingSession } from "@/lib/booking-session";
import { newIdempotencyKey } from "@/lib/idempotency";

export default function BookingHoldPage() {
  const router = useRouter();
  const api = getApi();
  const queryClient = useQueryClient();
  const [session, setSession] = useState<BookingSession | null>(null);
  const confirmKey = useRef(newIdempotencyKey());

  useEffect(() => setSession(loadBookingSession()), []);
  const confirm = useMutation({
    mutationFn: () => api.confirmBooking(session!.hold!.hold_id, confirmKey.current),
    onSuccess: (data) => {
      const next = { ...session!, confirmation: data };
      saveBookingSession(next);
      queryClient.invalidateQueries({ queryKey: qk.seatmap(session!.request.service_run_id) });
      queryClient.invalidateQueries({ queryKey: qk.overview(session!.request.service_run_id) });
      router.push("/booking/success");
    },
  });

  if (!session?.hold) return <Missing />;

  return (
    <PassengerPage>
      <div className="space-y-5">
        <JourneyBanner request={session.request} />
        <BookingSteps current={3} />
        <div className="mx-auto grid max-w-[1640px] gap-4 xl:grid-cols-[2fr_1fr]">
          <section className="rounded-lg border border-line bg-white p-5 shadow-card sm:p-7">
            <div className="flex items-start gap-3 border-b border-line pb-5"><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-success-soft text-success"><CheckCircle2 className="h-6 w-6" /></span><div><h1 className="text-2xl font-semibold text-ink">Chỗ của bạn đang được giữ</h1><p className="mt-1 text-sm leading-6 text-muted">Thông tin ghế và giá đã được khóa trong thời gian giữ chỗ.</p></div></div>
            <div className="mt-5 space-y-3">
              {session.offer.seat_plan.map((leg, index) => (
                <div key={`${leg.seat_id}-${index}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface p-4">
                  <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-soft text-primary"><Armchair className="h-5 w-5" /></span><div><strong className="text-ink">{seatDisplayName(leg.seat_id, session.request.seat_class)}</strong><p className="text-sm text-muted">Hành khách {leg.passenger_no ?? index + 1}</p></div></div>
                  <span className="inline-flex items-center gap-2 text-sm font-medium text-success"><CheckCircle2 className="h-4 w-4" />Đã giữ</span>
                </div>
              ))}
            </div>
          </section>
          <aside>
            <section className="rounded-lg border border-line bg-white p-6 text-center shadow-card">
              <h2 className="flex items-center gap-3 text-left text-xl font-semibold text-ink"><Clock3 className="h-6 w-6 text-primary" />Hoàn tất đặt vé</h2>
              <p className="mt-2 text-left text-sm leading-6 text-muted">Xác nhận trước khi thời gian giữ chỗ kết thúc.</p>
              <Countdown expiresAt={session.holdDeadline!} className="mt-6 justify-center text-3xl font-semibold" />
              <div className="mt-5 flex items-center justify-between border-y border-line py-4 text-sm"><span className="text-muted">Tổng thanh toán</span><Money amount={session.offer.pricing.gia_cuoi_vnd} emphasis /></div>
              <button disabled={confirm.isPending} onClick={() => confirm.mutate()} className="mt-6 flex min-h-[52px] w-full items-center justify-center rounded-lg bg-primary font-semibold text-white hover:bg-primary-dark disabled:opacity-50">{confirm.isPending ? "Đang xác nhận…" : "Xác nhận đặt vé"}</button>
              <Link href="/booking" className="mt-3 flex min-h-[48px] items-center justify-center rounded-lg border border-primary text-primary hover:bg-primary-soft">Hủy và chọn lại</Link>
              {confirm.isError && <div className="mt-4"><ErrorState compact error={confirm.error} onRetry={() => confirm.reset()} /></div>}
            </section>
          </aside>
        </div>
      </div>
    </PassengerPage>
  );
}

function Missing() {
  return <PassengerPage><div className="mx-auto max-w-xl rounded-lg border border-line bg-white p-8 text-center"><p>Không có chỗ đang được giữ.</p><Link href="/booking" className="mt-4 inline-flex rounded-lg bg-primary px-5 py-3 font-semibold text-white">Tìm hành trình</Link></div></PassengerPage>;
}
