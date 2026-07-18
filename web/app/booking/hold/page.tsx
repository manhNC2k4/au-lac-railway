"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock3, TrainFront } from "lucide-react";
import { getApi, qk } from "@/api";
import { BookingSteps, JourneyBanner, PassengerPage } from "@/components/passenger-layout";
import { Countdown } from "@/components/countdown";
import { ErrorState } from "@/components/error-state";
import { Money } from "@/components/money";
import { GOLDEN, segmentStations } from "@/lib/constants";
import { loadBookingSession, saveBookingSession, type BookingSession } from "@/lib/booking-session";
import { newIdempotencyKey } from "@/lib/idempotency";

export default function BookingHoldPage(){
  const router=useRouter(); const api=getApi(); const qc=useQueryClient(); const [session,setSession]=useState<BookingSession|null>(null);
  const confirmKey=useRef(newIdempotencyKey());
  useEffect(()=>setSession(loadBookingSession()),[]);
  const confirm=useMutation({mutationFn:()=>api.confirmBooking(session!.hold!.hold_id,confirmKey.current),onSuccess:data=>{const next={...session!,confirmation:data};saveBookingSession(next);qc.invalidateQueries({queryKey:qk.seatmap(GOLDEN.serviceRunId)});qc.invalidateQueries({queryKey:qk.overview(GOLDEN.serviceRunId)});router.push("/booking/success");}});
  if(!session?.hold) return <Missing />;
  return <PassengerPage><div className="space-y-5"><JourneyBanner request={session.request}/><BookingSteps current={3}/><div className="mx-auto grid max-w-[1640px] gap-4 xl:grid-cols-[2fr_1fr]">
    <section className="rounded-lg border border-line bg-white p-7 shadow-card"><h1 className="flex items-center gap-3 text-[25px] font-semibold text-ink"><span className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary-soft text-primary"><TrainFront className="h-6 w-6"/></span>Chỗ đang được giữ</h1><div className="mt-5 overflow-hidden rounded-lg border border-line"><div className="grid gap-4 p-5 sm:grid-cols-3"><Data label="Mã giữ chỗ" value={session.hold.hold_id}/><Data label="Trạng thái" value={session.hold.status}/><Data label="Phiên bản ma trận" value={String(session.hold.new_matrix_version)}/></div></div>
      <div className="mt-5 space-y-3">{session.offer.seat_plan.map((leg,i)=><div key={`${leg.seat_id}-${i}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line p-4"><div><strong className="text-ink">{leg.seat_id}</strong><p className="text-sm text-muted">L{leg.segment_from} đến L{leg.segment_to} · {segmentStations(leg.segment_from)}</p></div><span className="inline-flex items-center gap-2 text-sm font-medium text-success"><CheckCircle2 className="h-4 w-4"/>Đang giữ</span></div>)}</div>
    </section><aside><section className="rounded-lg border border-line bg-white p-7 text-center shadow-card"><h2 className="flex items-center gap-3 text-left text-xl font-semibold text-ink"><Clock3 className="h-6 w-6 text-primary"/>Thời gian giữ chỗ</h2><Countdown expiresAt={session.holdDeadline!} className="mt-7 justify-center text-3xl font-semibold"/><div className="mt-5 flex items-center justify-between border-y border-line py-4 text-sm"><span className="text-muted">Thanh toán</span><Money amount={session.offer.pricing.gia_cuoi_vnd} emphasis/></div><button disabled={confirm.isPending} onClick={()=>confirm.mutate()} className="mt-6 flex min-h-[52px] w-full items-center justify-center rounded-lg bg-primary font-semibold text-white disabled:opacity-50">{confirm.isPending?"Đang xác nhận...":"Xác nhận đặt vé"}</button><Link href="/booking" className="mt-3 flex min-h-[48px] items-center justify-center rounded-lg border border-primary text-primary">Hủy và chọn lại</Link>{confirm.isError&&<div className="mt-4"><ErrorState compact error={confirm.error} onRetry={()=>confirm.reset()}/></div>}</section></aside>
  </div></div></PassengerPage>;
}
function Missing(){return <PassengerPage><div className="mx-auto max-w-xl rounded-lg border border-line bg-white p-8 text-center"><p>Không có giữ chỗ đang hoạt động.</p><Link href="/booking" className="mt-4 inline-flex rounded-lg bg-primary px-5 py-3 font-semibold text-white">Tìm hành trình</Link></div></PassengerPage>}
function Data({label,value}:{label:string;value:string}){return <div><span className="block text-sm text-muted">{label}</span><strong className="mt-1 block break-all text-ink">{value}</strong></div>}
