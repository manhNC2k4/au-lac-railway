"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Check, Info, Sparkles, TrainFront } from "lucide-react";
import { getApi } from "@/api";
import { BookingSteps, JourneyBanner, PassengerPage } from "@/components/passenger-layout";
import { Countdown } from "@/components/countdown";
import { ErrorState } from "@/components/error-state";
import { Money } from "@/components/money";
import { PriceBreakdown } from "@/components/price-breakdown";
import { stationName, segmentStations } from "@/lib/constants";
import { apiDeadline, loadBookingSession, saveBookingSession, type BookingSession } from "@/lib/booking-session";
import { newIdempotencyKey } from "@/lib/idempotency";

export default function BookingOfferPage() {
  const router = useRouter(); const api = getApi();
  const [session, setSession] = useState<BookingSession | null>(null); const [consent, setConsent] = useState(false);
  const holdKey = useRef(newIdempotencyKey());
  useEffect(() => setSession(loadBookingSession()), []);
  const hold = useMutation({ mutationFn: () => {
    const passengerName = session!.passengerName.trim();
    return api.createHold({
      offer_id: session!.offer.offer_id,
      expected_matrix_version: session!.offer.matrix_version,
      ...(passengerName ? { passenger_name: passengerName } : {}),
      consent,
    }, holdKey.current);
  }, onSuccess: data => { const next={...session!, hold:data, holdDeadline:apiDeadline(data.expires_at,600)}; saveBookingSession(next); router.push("/booking/hold"); } });
  if (!session) return <Missing />;
  const { offer, request } = session;
  return <PassengerPage><div className="space-y-4"><JourneyBanner request={request} /><BookingSteps current={2} />
    <div className="mx-auto grid max-w-[1640px] gap-4 xl:grid-cols-[1fr_420px]">
      <section className="rounded-lg border border-line bg-white p-6 shadow-card"><div className="flex flex-wrap justify-between gap-3 border-b border-line pb-4"><div><h1 className="text-[26px] font-bold text-ink">Phương án ghế đang khả dụng</h1><p className="mt-1 text-muted">Dữ liệu được giữ nguyên theo offer {offer.offer_id}.</p></div><span className="inline-flex h-fit items-center gap-2 rounded-lg bg-success-soft px-3 py-2 text-sm text-success"><Sparkles className="h-4 w-4" />{offer.decision}</span></div>
        <div className="mt-5 space-y-3">{offer.seat_plan.map((leg,i)=><div key={`${leg.seat_id}-${i}`} className="grid gap-3 rounded-lg border border-line p-4 sm:grid-cols-[auto_1fr_auto] sm:items-center"><span className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary-soft text-primary"><TrainFront className="h-5 w-5" /></span><div><strong className="text-lg text-ink">{leg.seat_id}</strong><p className="text-sm text-muted">{segmentStations(leg.segment_from)}{leg.segment_to !== leg.segment_from ? ` đến L${leg.segment_to}` : ""}</p></div><span className="text-sm font-medium text-success">{leg.reused_gap ? "Tái sử dụng khoảng trống" : "Ghế khả dụng"}</span></div>)}</div>
        <div className="mt-5"><PriceBreakdown pricing={offer.pricing} /></div><p className="mt-4 rounded-lg bg-surface p-4 text-sm text-ink">{offer.explanation}</p>
        {offer.requires_customer_consent && <label className="mt-4 flex items-start gap-3 rounded-lg border border-warning/40 bg-warning-soft p-4"><input type="checkbox" className="mt-1 h-4 w-4 accent-primary" checked={consent} onChange={e=>setConsent(e.target.checked)} /><span><strong className="block text-ink">Tôi đồng ý đổi ghế {offer.so_lan_doi_cho} lần</strong><span className="text-sm text-muted">Đổi tại: {offer.change_station_ids.map(stationName).join(", ")}. Hệ thống chỉ giữ chỗ sau khi bạn xác nhận.</span></span></label>}
      </section>
      <aside className="space-y-4"><section className="rounded-lg border border-line bg-white p-6 shadow-card"><h2 className="text-xl font-semibold text-ink">Xác nhận phương án</h2><dl className="mt-4 space-y-3 text-sm"><Row label="Giá cuối"><Money amount={offer.pricing.gia_cuoi_vnd} emphasis /></Row><Row label="Số ghế" value={String(offer.seat_plan.length)} /><Row label="Hiệu lực"><Countdown expiresAt={session.offerDeadline} /></Row></dl><button disabled={hold.isPending || (offer.requires_customer_consent && !consent)} onClick={()=>hold.mutate()} className="mt-5 flex min-h-[52px] w-full items-center justify-center gap-2 rounded-lg bg-primary font-semibold text-white disabled:opacity-50"><Check className="h-5 w-5" />{hold.isPending ? "Đang giữ chỗ..." : "Giữ phương án này"}</button><Link href="/booking" className="mt-3 flex min-h-[48px] items-center justify-center rounded-lg border border-primary text-primary">Chọn lại</Link>{hold.isError && <div className="mt-4"><ErrorState compact error={hold.error} onRetry={()=>hold.reset()} /></div>}</section><section className="rounded-lg border border-line bg-white p-5 shadow-card"><h2 className="flex items-center gap-2 font-semibold text-ink"><Info className="h-5 w-5 text-primary" />Mã quyết định</h2><p className="mt-2 break-all font-mono text-xs text-muted">{offer.decision_record_id}</p></section></aside>
    </div></div></PassengerPage>;
}
function Missing(){return <PassengerPage><div className="mx-auto max-w-xl rounded-lg border border-line bg-white p-8 text-center"><p className="text-ink">Không có offer đang hoạt động.</p><Link href="/booking" className="mt-4 inline-flex rounded-lg bg-primary px-5 py-3 font-semibold text-white">Tìm hành trình</Link></div></PassengerPage>}
function Row({label,value,children}:{label:string;value?:string;children?:React.ReactNode}){return <div className="flex justify-between gap-4 border-b border-line pb-3"><dt className="text-muted">{label}</dt><dd className="font-semibold text-ink">{children ?? value}</dd></div>}
