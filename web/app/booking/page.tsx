"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeftRight, ChevronDown, Search } from "lucide-react";
import { getApi, type OfferRequest } from "@/api";
import { BookingHeader, BookingSteps, PassengerPage } from "@/components/passenger-layout";
import { RailwayScene } from "@/components/railway-scene";
import { ErrorState } from "@/components/error-state";
import { GOLDEN, SEAT_CLASS_LABEL, STATIONS } from "@/lib/constants";
import { apiDeadline, saveBookingSession } from "@/lib/booking-session";

export default function BookingPage() {
  const router = useRouter();
  const api = getApi();
  const [origin, setOrigin] = useState<string>(GOLDEN.origin);
  const [dest, setDest] = useState<string>(GOLDEN.dest);
  const [quantity, setQuantity] = useState(1);
  const [passengerName, setPassengerName] = useState("");
  const [priority, setPriority] = useState(false);
  const offer = useMutation({
    mutationFn: (request: OfferRequest) => api.createOffer(request),
    onSuccess: (data, request) => {
      saveBookingSession({ request, passengerName: passengerName.trim(), offer: data, offerDeadline: apiDeadline(data.expires_at, 300) });
      router.push("/booking/offer");
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!passengerName.trim() || origin === dest) return;
    offer.mutate({ service_run_id: GOLDEN.serviceRunId, origin_station_id: origin, dest_station_id: dest, seat_class: GOLDEN.seatClass, quantity, priority_passenger: priority });
  };

  const swap = () => { setOrigin(dest); setDest(origin); };
  return (
    <PassengerPage><div className="space-y-5"><BookingHeader /><BookingSteps current={1} />
      <section className="relative mx-auto max-w-[1640px] overflow-hidden rounded-lg bg-white shadow-card">
        <div className="relative"><RailwayScene compact className="h-[250px] md:h-[350px]" /><div className="absolute left-5 top-7 max-w-[520px] md:left-10 md:top-12"><h1 className="text-[30px] font-bold text-ink md:text-[42px]">Bạn muốn đi đâu?</h1><p className="mt-2 text-sm text-[#42526b] md:text-base">Chọn hành trình để hệ thống tìm phương án ghế và giá đang khả dụng.</p></div></div>
        <form onSubmit={submit} className="relative z-10 mx-2 -mt-6 rounded-[24px] bg-white p-5 shadow-[0_10px_30px_rgba(16,42,86,0.14)] md:mx-9 md:-mt-20 md:p-7">
          <div className="grid items-end gap-4 md:grid-cols-2 xl:grid-cols-[1fr_auto_1fr_1.2fr_.8fr]">
            <SelectField label="Ga đi" value={origin} onChange={setOrigin} options={STATIONS.map(s => ({ value:s.id, label:s.name }))} />
            <button type="button" onClick={swap} aria-label="Đổi ga đi và ga đến" className="hidden h-12 w-12 items-center justify-center rounded-lg border border-line text-primary hover:bg-primary-soft xl:flex"><ArrowLeftRight className="h-5 w-5" /></button>
            <SelectField label="Ga đến" value={dest} onChange={setDest} options={STATIONS.map(s => ({ value:s.id, label:s.name }))} />
            <label><span className="mb-2 block text-sm text-muted">Tên hành khách</span><input required value={passengerName} onChange={e => setPassengerName(e.target.value)} className="min-h-[52px] w-full rounded-lg border border-line px-4 outline-none focus:ring-2 focus:ring-primary" /></label>
            <SelectField label="Số lượng" value={String(quantity)} onChange={v => setQuantity(Number(v))} options={[1,2,3,4].map(n => ({ value:String(n), label:`${n} hành khách` }))} />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-5 text-sm"><span className="rounded-lg bg-surface px-3 py-2 text-ink">{GOLDEN.serviceRunId} · {SEAT_CLASS_LABEL[GOLDEN.seatClass]}</span><label className="flex items-center gap-2 text-ink"><input type="checkbox" checked={priority} onChange={e => setPriority(e.target.checked)} className="h-4 w-4 accent-primary" />Hành khách ưu tiên, không đổi ghế</label>{origin === dest && <span className="text-danger">Ga đi và ga đến phải khác nhau.</span>}</div>
          <button disabled={offer.isPending || !passengerName.trim() || origin === dest} type="submit" className="mt-5 flex min-h-[58px] w-full items-center justify-center gap-3 rounded-lg bg-primary text-[18px] font-semibold text-white hover:bg-primary-dark disabled:opacity-50"><Search className="h-6 w-6" />{offer.isPending ? "Đang tìm phương án..." : "Tìm phương án"}</button>
          {offer.isError && <div className="mt-4"><ErrorState compact error={offer.error} onRetry={() => offer.reset()} /></div>}
        </form><div className="h-7" />
      </section>
    </div></PassengerPage>
  );
}

function SelectField({ label, value, onChange, options }: { label:string; value:string; onChange:(v:string)=>void; options:{value:string;label:string}[] }) {
  return <label className="relative block"><span className="mb-2 block text-sm text-muted">{label}</span><select value={value} onChange={e => onChange(e.target.value)} className="min-h-[52px] w-full appearance-none rounded-lg border border-line bg-white px-4 pr-10 font-semibold text-ink outline-none focus:ring-2 focus:ring-primary">{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select><ChevronDown className="pointer-events-none absolute bottom-[18px] right-4 h-4 w-4 text-muted" /></label>;
}
