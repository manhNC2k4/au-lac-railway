"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Armchair, Check, CheckCircle2, Home, MapPinned, Tag, Ticket } from "lucide-react";
import { BookingSteps, JourneyBanner, PassengerPage } from "@/components/passenger-layout";
import { Money } from "@/components/money";
import { clearBookingSession, loadBookingSession, savePendingReturnJourney, type BookingSession } from "@/lib/booking-session";
import { seatDisplayName, stationName } from "@/lib/constants";

export default function BookingSuccessPage() {
  const [session, setSession] = useState<BookingSession | null>(null);
  useEffect(() => setSession(loadBookingSession()), []);
  if (!session?.confirmation) return <Missing />;
  const confirmation = session.confirmation;
  const bookingCode = confirmation.booking_id.replace(/^bk_/, "").toUpperCase();

  return (
    <PassengerPage>
      <div className="space-y-5">
        <JourneyBanner request={session.request} />
        <BookingSteps current={4} complete />
        <section className="mx-auto flex min-h-[540px] max-w-[1200px] flex-col items-center rounded-lg border border-line bg-white px-5 py-9 shadow-card sm:px-6">
          <span className="flex h-20 w-20 items-center justify-center rounded-full bg-success text-white"><Check className="h-11 w-11" /></span>
          <h1 className="mt-5 text-center text-3xl font-bold text-ink">Đặt vé thành công</h1>
          <p className="mt-2 text-center text-muted">Chỗ của bạn đã được xác nhận. Hãy lưu mã đặt vé để tra cứu khi cần.</p>
          <div className="mt-6 grid w-full max-w-[900px] gap-4 rounded-lg border border-line p-5 md:grid-cols-3">
            <Item icon={<Ticket />} label="Mã đặt vé" value={bookingCode} />
            <Item icon={<MapPinned />} label="Hành trình" value={`${stationName(session.request.origin_station_id)} → ${stationName(session.request.dest_station_id)}`} />
            <Item icon={<CheckCircle2 />} label="Trạng thái" value="Đã xác nhận" />
            <Item icon={<Armchair />} label="Chỗ" value={session.offer.seat_plan.map((seat) => seatDisplayName(seat.seat_id, session.request.seat_class)).join(", ")} />
            <Item icon={<Tag />} label="Tổng thanh toán"><Money amount={confirmation.final_price_vnd} emphasis /></Item>
          </div>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            {session.returnJourney && <Link href="/booking" onClick={() => { savePendingReturnJourney(session.returnJourney!); clearBookingSession(); }} className="inline-flex min-h-[50px] items-center rounded-lg bg-primary px-6 font-semibold text-white">Tiếp tục chọn lượt về</Link>}
            <Link href="/booking" onClick={clearBookingSession} className={`inline-flex min-h-[50px] items-center rounded-lg px-6 font-semibold ${session.returnJourney ? "border border-primary text-primary" : "bg-primary text-white"}`}>Đặt hành trình khác</Link>
            <Link href="/" className="inline-flex min-h-[50px] items-center gap-2 rounded-lg border border-primary px-6 font-semibold text-primary"><Home className="h-5 w-5" />Về trang chủ</Link>
          </div>
        </section>
      </div>
    </PassengerPage>
  );
}

function Missing() {
  return <PassengerPage><div className="mx-auto max-w-xl rounded-lg border border-line bg-white p-8 text-center"><p>Chưa có vé được xác nhận.</p><Link href="/booking" className="mt-4 inline-flex rounded-lg bg-primary px-5 py-3 font-semibold text-white">Đặt vé</Link></div></PassengerPage>;
}

function Item({ icon, label, value, children }: { icon: React.ReactNode; label: string; value?: string; children?: React.ReactNode }) {
  return <div className="flex min-w-0 items-center gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">{icon}</span><span className="min-w-0"><span className="block text-sm text-muted">{label}</span><strong className="block break-words text-ink">{children ?? value}</strong></span></div>;
}
