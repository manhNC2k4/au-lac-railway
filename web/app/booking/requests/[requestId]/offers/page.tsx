"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Armchair, Check, Loader2, Sparkles, TrainFront, X } from "lucide-react";
import {
  getApi, qk, type BookingCandidateData, type BookingRequestData,
  type OfferData, type OfferRequest, type TrainCoachLayout, type TrainSeatLayoutItem,
} from "@/api";
import { BookingHeader, BookingSteps, JourneyBanner, PassengerPage } from "@/components/passenger-layout";
import { ErrorState } from "@/components/error-state";
import { Money } from "@/components/money";
import { PriceBreakdown } from "@/components/price-breakdown";
import { apiDeadline, clearApprovalSession, loadApprovalSession, saveBookingSession } from "@/lib/booking-session";
import { SEAT_CLASS_LABEL } from "@/lib/constants";
import { cn } from "@/lib/utils";

export default function ApprovedSeatMapPage() {
  const api = getApi();
  const router = useRouter();
  const params = useParams<{ requestId: string }>();
  const requestId = decodeURIComponent(params.requestId);
  const initialized = useRef(false);
  const [activeCoach, setActiveCoach] = useState<number | null>(null);
  const [selectedSeatIds, setSelectedSeatIds] = useState<string[]>([]);
  const [selectionError, setSelectionError] = useState("");

  const requestQuery = useQuery({
    queryKey: qk.bookingRequest(requestId),
    queryFn: () => api.getBookingRequest(requestId),
    refetchInterval: 5_000,
  });
  const request = requestQuery.data;
  const candidates = useMemo(() => request?.candidates.filter((candidate) =>
    ["APPROVED", "PRICE_OVERRIDDEN", "SELECTED"].includes(candidate.status)) ?? [], [request]);
  const candidate = candidates.find((item) => item.ai_recommended) ?? candidates[0];
  const isSeatChangePlan = Boolean(candidate?.requires_customer_consent);
  const layoutQuery = useQuery({
    queryKey: qk.bookingSeatLayout(requestId),
    queryFn: () => api.getBookingSeatLayout(requestId),
    enabled: request?.status === "APPROVED" && !isSeatChangePlan,
    refetchInterval: 5_000,
  });

  useEffect(() => {
    if (requestQuery.data && ["SUBMITTED", "AI_PROCESSING", "PENDING_ADMIN"].includes(requestQuery.data.status)) {
      router.replace(`/booking/requests/${encodeURIComponent(requestId)}/waiting`);
    }
  }, [requestQuery.data, requestId, router]);

  useEffect(() => {
    if (request?.status === "APPROVED" && candidate?.requires_customer_consent) {
      continueWithCandidate(request, candidate, router);
    }
  }, [candidate, request, router]);

  useEffect(() => {
    if (initialized.current || !candidate || !layoutQuery.data) return;
    const availableIds = new Set(layoutQuery.data.coaches.flatMap((item) =>
      item.seats.filter((seat) => seat.state === "AVAILABLE" && item.seat_class === layoutQuery.data?.seat_class).map((seat) => seat.seat_id)));
    const initialIds = candidate.seat_plan.map((seat) => seat.seat_id).filter((seatId) => availableIds.has(seatId));
    const coach = layoutQuery.data.coaches.find((item) =>
      item.seats.some((seat) => initialIds.includes(seat.seat_id)));
    setSelectedSeatIds(initialIds);
    if (initialIds.length !== layoutQuery.data.quantity) setSelectionError("Chỗ AI gợi ý vừa thay đổi trạng thái. Vui lòng chọn lại chỗ còn trống.");
    setActiveCoach(coach?.coach_number ?? layoutQuery.data.coaches.find((item) => item.seat_class === layoutQuery.data?.seat_class)?.coach_number ?? 1);
    initialized.current = true;
  }, [candidate, layoutQuery.data]);

  const selectMutation = useMutation({
    mutationFn: () => api.selectBookingSeats(requestId, candidate!.candidate_id, selectedSeatIds),
    onSuccess: (updated) => {
      const selectedCandidate = updated.candidates.find((item) => item.candidate_id === candidate!.candidate_id);
      if (!selectedCandidate) return;
      continueWithCandidate(updated, selectedCandidate, router);
    },
  });

  if (requestQuery.isPending || isSeatChangePlan || (request?.status === "APPROVED" && layoutQuery.isPending)) {
    return <PassengerPage><div className="flex min-h-[70vh] items-center justify-center"><Loader2 className="h-9 w-9 animate-spin text-primary" aria-label="Đang tải sơ đồ tàu" /></div></PassengerPage>;
  }
  if (requestQuery.isError || !request || layoutQuery.isError) {
    return <PassengerPage><div className="mx-auto max-w-xl pt-16"><ErrorState error={requestQuery.error ?? layoutQuery.error} onRetry={() => { requestQuery.refetch(); layoutQuery.refetch(); }} /></div></PassengerPage>;
  }
  if (!candidate || !layoutQuery.data) {
    return <PassengerPage><div className="mx-auto max-w-xl pt-16"><ErrorState error={new Error("Không còn phương án ghế đang hiệu lực.")} onRetry={() => requestQuery.refetch()} /></div></PassengerPage>;
  }

  const layout = layoutQuery.data;
  const coach = layout.coaches.find((item) => item.coach_number === activeCoach) ?? layout.coaches[0];
  const selectedDetails = layout.coaches.flatMap((item) => item.seats.map((seat) => ({ ...seat, coach: item })))
    .filter((seat) => selectedSeatIds.includes(seat.seat_id));

  const toggleSeat = (seat: TrainSeatLayoutItem, seatCoach: TrainCoachLayout) => {
    setSelectionError("");
    setSelectedSeatIds((current) => {
      if (current.includes(seat.seat_id)) return current.filter((id) => id !== seat.seat_id);
      if (seatCoach.seat_class !== request.seat_class || seat.state !== "AVAILABLE") return current;
      if (current.length >= request.quantity) {
        setSelectionError(`Bạn chỉ cần chọn ${request.quantity} chỗ cho hành trình này.`);
        return current;
      }
      return [...current, seat.seat_id];
    });
  };

  return (
    <PassengerPage>
      <div className="space-y-3">
        <BookingHeader />
        <JourneyBanner request={request} />
        <BookingSteps current={2} />
        <main className="mx-auto max-w-[1380px]">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div><h1 className="text-2xl font-bold text-ink">Chọn vị trí trên tàu</h1><p className="mt-1 text-sm text-muted">AI đã chọn sẵn phương án phù hợp. Bạn có thể giữ nguyên hoặc đổi sang chỗ còn trống cùng hạng.</p></div>
            <span className="inline-flex items-center gap-2 rounded-lg bg-success-soft px-3 py-2 text-sm font-semibold text-success"><Check className="h-4 w-4" />Giá đã được duyệt</span>
          </div>

          <section className="rounded-lg border border-line bg-white p-4 shadow-card">
            <div className="flex flex-wrap items-center gap-2" aria-label="Sơ đồ các toa tàu">
              <span className="flex h-[58px] w-[72px] shrink-0 items-center justify-center rounded-l-full rounded-r-lg bg-primary text-white"><TrainFront className="h-7 w-7" /><span className="sr-only">Đầu máy</span></span>
              {layout.coaches.map((item) => {
                const available = item.seats.filter((seat) => seat.state === "AVAILABLE" && item.seat_class === request.seat_class).length;
                const active = item.coach_number === coach.coach_number;
                return <button key={item.coach_number} type="button" onClick={() => setActiveCoach(item.coach_number)} className={cn("min-h-[58px] min-w-[92px] flex-1 rounded-lg border px-2 py-1.5 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary", active ? "border-primary bg-primary text-white" : item.seat_class === request.seat_class ? "border-primary/30 bg-primary-soft text-ink hover:border-primary" : "border-line bg-surface text-muted")}>
                  <strong className="block text-xs">Toa {item.coach_number}</strong><span className="block truncate text-[10px]">{shortClass(item.seat_class)}</span><span className="block text-[10px]">{item.seat_class === request.seat_class ? `${available} chỗ trống` : "Hạng khác"}</span>
                </button>;
              })}
            </div>
            <p className="mt-3 text-xs text-muted">Sơ đồ vị trí đang dùng bố trí mô phỏng theo sức chứa dataset; mã ghế và trạng thái bán vẫn lấy trực tiếp từ hệ thống.</p>
          </section>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
            <section className="rounded-lg border border-line bg-white p-4 shadow-card sm:p-5">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
                <div><h2 className="text-lg font-semibold text-ink">Toa {coach.coach_number} · {SEAT_CLASS_LABEL[coach.seat_class] ?? coach.seat_class}</h2><p className="mt-1 text-sm text-muted">{coach.layout_type === "SEATED_2X2" ? "Bố trí 2 ghế · lối đi · 2 ghế" : `${coach.capacity / 7} chỗ mỗi khoang`}</p></div>
                <Legend />
              </div>
              <CoachInterior coach={coach} selectedSeatIds={selectedSeatIds} approvedIds={new Set(candidate.seat_plan.map((seat) => seat.seat_id))} onToggle={toggleSeat} />
            </section>

            <aside className="space-y-4">
              <section className="rounded-lg border border-line bg-white p-5 shadow-card">
                <h2 className="font-semibold text-ink">Chỗ đang chọn ({selectedSeatIds.length}/{request.quantity})</h2>
                <div className="mt-3 space-y-2">
                  {selectedDetails.map((seat) => <div key={seat.seat_id} className="flex items-center justify-between gap-3 rounded-lg bg-primary-soft px-3 py-2.5"><div><strong className="text-sm text-ink">Toa {seat.coach.coach_number} · Chỗ {seat.seat_number}</strong><p className="text-xs text-muted">{positionLabel(seat)}</p></div><button type="button" onClick={() => toggleSeat(seat, seat.coach)} aria-label={`Bỏ chọn chỗ ${seat.seat_number}`} className="flex h-10 w-10 items-center justify-center rounded-lg text-primary hover:bg-white"><X className="h-4 w-4" /></button></div>)}
                  {!selectedDetails.length && <p className="rounded-lg bg-surface p-3 text-sm text-muted">Chọn chỗ còn trống trên sơ đồ.</p>}
                </div>
                {(selectionError || selectMutation.isError) && <div className="mt-3">{selectionError ? <p className="rounded-lg bg-danger-soft p-3 text-sm text-danger">{selectionError}</p> : <ErrorState compact error={selectMutation.error} onRetry={() => selectMutation.reset()} />}</div>}
                <button type="button" disabled={selectedSeatIds.length !== request.quantity || selectMutation.isPending} onClick={() => selectMutation.mutate()} className="mt-4 flex min-h-[50px] w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 font-semibold text-white hover:bg-primary-dark disabled:opacity-50"><Check className="h-5 w-5" />{selectMutation.isPending ? "Đang kiểm tra chỗ…" : "Xác nhận chỗ đã chọn"}</button>
              </section>
              <PriceBreakdown pricing={candidate.pricing} compact />
              <div className="rounded-lg border border-line bg-white p-4 text-sm text-muted shadow-card"><span className="font-semibold text-ink">Tổng giá: </span><Money amount={candidate.approved_price_vnd ?? candidate.pricing.gia_cuoi_vnd} emphasis /></div>
            </aside>
          </div>
        </main>
      </div>
    </PassengerPage>
  );
}

function CoachInterior({ coach, selectedSeatIds, approvedIds, onToggle }: { coach: TrainCoachLayout; selectedSeatIds: string[]; approvedIds: Set<string>; onToggle: (seat: TrainSeatLayoutItem, coach: TrainCoachLayout) => void }) {
  const rows = Array.from(new Set(coach.seats.map((seat) => seat.row_number))).map((row) => ({ row, seats: coach.seats.filter((seat) => seat.row_number === row) }));
  return <div className="mx-auto mt-5 max-w-[760px] rounded-lg border-2 border-line bg-surface p-3 sm:p-5">
    <div className="mb-4 flex items-center justify-between text-xs text-muted"><span>Đầu toa</span><span>{coach.layout_type === "SEATED_2X2" ? "Lối đi giữa" : "Hành lang toa"}</span><span>Cuối toa</span></div>
    <div className="space-y-3">{rows.map(({ row, seats }) => <div key={row} className={coach.layout_type === "SEATED_2X2" ? "grid grid-cols-[1fr_1fr_28px_1fr_1fr] gap-2" : "rounded-lg border border-line bg-white p-3"}>
      {coach.layout_type === "SEATED_2X2" ? <>
        {seats.slice(0, 2).map((seat) => <SeatButton key={seat.seat_id} seat={seat} coach={coach} selected={selectedSeatIds.includes(seat.seat_id)} approved={approvedIds.has(seat.seat_id)} onToggle={onToggle} />)}
        <span className="flex items-center justify-center text-[10px] text-muted">{row}</span>
        {seats.slice(2, 4).map((seat) => <SeatButton key={seat.seat_id} seat={seat} coach={coach} selected={selectedSeatIds.includes(seat.seat_id)} approved={approvedIds.has(seat.seat_id)} onToggle={onToggle} />)}
      </> : <><p className="mb-2 text-xs font-semibold text-muted">Khoang {row}</p><div className="grid grid-cols-2 gap-2">{seats.map((seat) => <SeatButton key={seat.seat_id} seat={seat} coach={coach} selected={selectedSeatIds.includes(seat.seat_id)} approved={approvedIds.has(seat.seat_id)} onToggle={onToggle} />)}</div></>}
    </div>)}</div>
  </div>;
}

function SeatButton({ seat, coach, selected, approved, onToggle }: { seat: TrainSeatLayoutItem; coach: TrainCoachLayout; selected: boolean; approved: boolean; onToggle: (seat: TrainSeatLayoutItem, coach: TrainCoachLayout) => void }) {
  const selectable = seat.state === "AVAILABLE" && coach.seat_class === seat.seat_id.split(":")[0];
  return <button type="button" disabled={!selectable} onClick={() => onToggle(seat, coach)} title={`Chỗ ${seat.seat_number} · ${positionLabel(seat)}`} aria-pressed={selected} className={cn("relative min-h-[52px] rounded-lg border px-1.5 py-1 text-center text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary", selected && "border-primary bg-primary text-white", !selected && approved && seat.state === "AVAILABLE" && "border-primary bg-primary-soft text-primary", !selected && !approved && seat.state === "AVAILABLE" && "border-line bg-white text-ink hover:border-primary hover:bg-primary-soft", seat.state === "BOOKED" && "cursor-not-allowed border-line bg-[#dfe5ec] text-[#6b7787] line-through", seat.state === "UNAVAILABLE" && "cursor-not-allowed border-dashed border-line bg-[#f1f3f6] text-[#9aa5b3]")}>
    <span className="block">{seat.seat_number}</span><span className="block text-[9px] font-normal opacity-80">{seat.berth_level ? berthLabel(seat.berth_level) : seat.column_code}</span>{approved && !selected && seat.state === "AVAILABLE" && <Sparkles className="absolute right-1 top-1 h-3 w-3" />}
  </button>;
}

function Legend() {
  const items = [["bg-white border-line", "Còn trống"], ["bg-primary-soft border-primary", "AI chọn sẵn"], ["bg-primary border-primary", "Đang chọn"], ["bg-[#dfe5ec] border-line", "Đã đặt"], ["bg-[#f1f3f6] border-dashed border-line", "Không khả dụng"]];
  return <div className="flex flex-wrap gap-x-3 gap-y-2">{items.map(([style, label]) => <span key={label} className="inline-flex items-center gap-1.5 text-[11px] text-muted"><span className={cn("h-3.5 w-3.5 rounded-[3px] border", style)} />{label}</span>)}</div>;
}

function continueWithCandidate(request: BookingRequestData, candidate: BookingCandidateData, router: ReturnType<typeof useRouter>) {
  const approvalSession = loadApprovalSession();
  const offerRequest: OfferRequest = { service_run_id: request.service_run_id, origin_station_id: request.origin_station_id, dest_station_id: request.dest_station_id, seat_class: request.seat_class, quantity: request.quantity, priority_passenger: request.priority_passenger };
  const offer: OfferData = { offer_id: candidate.offer_id, service_run_id: request.service_run_id, matrix_version: candidate.matrix_version, forecast_version: candidate.forecast_version, policy_version: candidate.policy_version, decision: candidate.decision, seat_plan: candidate.seat_plan, requires_customer_consent: candidate.requires_customer_consent, change_station_ids: candidate.change_station_ids, so_lan_doi_cho: candidate.so_lan_doi_cho, pricing: candidate.pricing, bid: { total_vnd: 0, by_segment: {} }, decision_record_id: candidate.decision_record_id, explanation: candidate.explanation, expires_at: candidate.expires_at };
  saveBookingSession({ request: offerRequest, passengerName: request.passenger_name ?? "", offer, offerDeadline: apiDeadline(candidate.expires_at, 900), returnJourney: approvalSession?.returnJourney });
  clearApprovalSession();
  router.push("/booking/offer");
}

function shortClass(seatClass: string) { return seatClass === "NGOI_MEM_DH" ? "Ngồi mềm" : seatClass === "NAM_K6" ? "Khoang 6" : "Khoang 4"; }
function berthLabel(level: TrainSeatLayoutItem["berth_level"]) { return level === "LOWER" ? "Tầng dưới" : level === "MIDDLE" ? "Tầng giữa" : "Tầng trên"; }
function positionLabel(seat: TrainSeatLayoutItem) { if (seat.berth_level) return `${berthLabel(seat.berth_level)} · bên ${seat.column_code === "L" ? "trái" : "phải"}`; return seat.position_code.includes("WINDOW") ? "Cạnh cửa sổ" : "Cạnh lối đi"; }
