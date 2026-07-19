"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Armchair, Check, Clock3, ShieldCheck, Sparkles } from "lucide-react";
import { getApi } from "@/api";
import { BookingSteps, JourneyBanner, PassengerPage } from "@/components/passenger-layout";
import { Countdown } from "@/components/countdown";
import { ErrorState } from "@/components/error-state";
import { Money } from "@/components/money";
import { PriceBreakdown } from "@/components/price-breakdown";
import { seatDisplayName, stationName } from "@/lib/constants";
import { apiDeadline, loadBookingSession, saveBookingSession, type BookingSession } from "@/lib/booking-session";
import { newIdempotencyKey } from "@/lib/idempotency";

export default function BookingOfferPage() {
  const router = useRouter();
  const api = getApi();
  const [session, setSession] = useState<BookingSession | null>(null);
  const [consent, setConsent] = useState(false);
  const holdKey = useRef(newIdempotencyKey());

  useEffect(() => setSession(loadBookingSession()), []);

  const hold = useMutation({
    mutationFn: () => {
      const passengerName = session!.passengerName.trim();
      return api.createHold({
        offer_id: session!.offer.offer_id,
        expected_matrix_version: session!.offer.matrix_version,
        ...(passengerName ? { passenger_name: passengerName } : {}),
        consent,
      }, holdKey.current);
    },
    onSuccess: (data) => {
      const next = { ...session!, hold: data, holdDeadline: apiDeadline(data.expires_at, 900) };
      saveBookingSession(next);
      router.push("/booking/hold");
    },
  });

  if (!session) return <Missing />;
  const { offer, request } = session;
  const journey = `${stationName(request.origin_station_id)} → ${stationName(request.dest_station_id)}`;

  return (
    <PassengerPage>
      <div className="space-y-4">
        <JourneyBanner request={request} />
        <BookingSteps current={2} />
        <div className="mx-auto grid max-w-[1640px] gap-4 xl:grid-cols-[1fr_400px]">
          <section className="rounded-lg border border-line bg-white p-5 shadow-card sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
              <div>
                <h1 className="text-2xl font-bold text-ink">Phương án dành cho bạn</h1>
                <p className="mt-1 text-sm leading-6 text-muted">Ghế và giá dưới đây đã được nhân viên kiểm tra trước khi gửi đến bạn.</p>
              </div>
              <span className="inline-flex items-center gap-2 rounded-lg bg-success-soft px-3 py-2 text-sm font-semibold text-success"><Sparkles className="h-4 w-4" />Đã duyệt</span>
            </div>

            <div className="mt-5 space-y-3">
              {offer.seat_plan.map((leg, index) => (
                <div key={`${leg.seat_id}-${index}`} className="grid gap-3 rounded-lg border border-line bg-surface p-4 sm:grid-cols-[auto_1fr_auto] sm:items-center">
                  <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary-soft text-primary"><Armchair className="h-5 w-5" /></span>
                  <div>
                    <strong className="text-lg text-ink">{seatDisplayName(leg.seat_id, request.seat_class)}</strong>
                    <p className="text-sm text-muted">{offer.requires_customer_consent ? `Phần ${index + 1}: chặng ${leg.segment_from}${leg.segment_to > leg.segment_from ? ` đến ${leg.segment_to}` : ""}` : `Hành khách ${leg.passenger_no ?? index + 1}`}</p>
                  </div>
                  <span className="text-sm font-medium text-success">{journey}</span>
                </div>
              ))}
            </div>

            <div className="mt-5"><PriceBreakdown pricing={offer.pricing} /></div>

            {offer.requires_customer_consent && (
              <label className="mt-4 flex items-start gap-3 rounded-lg border border-warning/40 bg-warning-soft p-4">
                <input type="checkbox" className="mt-1 h-4 w-4 accent-primary" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
                <span><strong className="block text-ink">Tôi đồng ý đổi chỗ {offer.so_lan_doi_cho} lần</strong><span className="text-sm leading-6 text-muted">Điểm đổi: {offer.change_station_ids.map(stationName).join(", ")}. Hệ thống chỉ giữ chỗ sau khi bạn xác nhận.</span></span>
              </label>
            )}
          </section>

          <aside className="space-y-4">
            <section className="rounded-lg border border-line bg-white p-6 shadow-card">
              <h2 className="text-xl font-semibold text-ink">Xác nhận phương án</h2>
              <p className="mt-1 text-sm leading-6 text-muted">Giá được giữ trong 15 phút kể từ lúc phương án được duyệt.</p>
              <dl className="mt-4 space-y-3 text-sm">
                <Row label="Tổng thanh toán"><Money amount={offer.pricing.gia_cuoi_vnd} emphasis /></Row>
                <Row label="Số chỗ" value={String(request.quantity)} />
                <Row label="Thời gian còn lại"><Countdown expiresAt={session.offerDeadline} /></Row>
              </dl>
              <button disabled={hold.isPending || (offer.requires_customer_consent && !consent)} onClick={() => hold.mutate()} className="mt-5 flex min-h-[52px] w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 font-semibold text-white hover:bg-primary-dark disabled:opacity-50"><Check className="h-5 w-5" />{hold.isPending ? "Đang giữ chỗ…" : "Giữ chỗ và tiếp tục"}</button>
              <Link href="/booking" className="mt-3 flex min-h-[48px] items-center justify-center rounded-lg border border-primary font-semibold text-primary hover:bg-primary-soft">Chọn lại</Link>
              {hold.isError && <div className="mt-4"><ErrorState compact error={hold.error} onRetry={() => hold.reset()} /></div>}
            </section>
            <section className="flex items-start gap-3 rounded-lg border border-line bg-white p-5 shadow-card">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <div><h2 className="font-semibold text-ink">Giá được đảm bảo</h2><p className="mt-1 text-sm leading-6 text-muted">Sau khi giữ chỗ thành công, mức giá này sẽ không thay đổi trong bước xác nhận.</p></div>
            </section>
          </aside>
        </div>
      </div>
    </PassengerPage>
  );
}

function Missing() {
  return <PassengerPage><div className="mx-auto max-w-xl rounded-lg border border-line bg-white p-8 text-center"><Clock3 className="mx-auto h-8 w-8 text-muted" /><p className="mt-3 text-ink">Phương án đã hết hiệu lực hoặc không còn tồn tại.</p><Link href="/booking" className="mt-4 inline-flex rounded-lg bg-primary px-5 py-3 font-semibold text-white">Tìm hành trình</Link></div></PassengerPage>;
}

function Row({ label, value, children }: { label: string; value?: string; children?: React.ReactNode }) {
  return <div className="flex justify-between gap-4 border-b border-line pb-3"><dt className="text-muted">{label}</dt><dd className="text-right font-semibold text-ink">{children ?? value}</dd></div>;
}
