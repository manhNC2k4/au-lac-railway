"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowLeftRight,
  ArrowRight,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  Info,
  Lock,
  MapPin,
  Scale,
  Search,
  Sparkles,
  TrainFront,
} from "lucide-react";
import {
  getApi,
  qk,
  type ConfirmData,
  type HoldData,
  type OfferData,
  type OfferRequest,
  type SeatState,
} from "@/api";
import { GOLDEN, SEAT_CLASS_LABEL, STATIONS, stationName } from "@/lib/constants";
import { useCurrentRun } from "@/lib/current-run";
import { newIdempotencyKey } from "@/lib/idempotency";
import { ApiError } from "@/lib/errors";
import { formatCountdown } from "@/lib/format";
import { Money } from "@/components/money";
import { VersionStrip } from "@/components/version-strip";
import { ErrorState } from "@/components/error-state";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { TrainArt } from "@/components/train-art";
import { cn } from "@/lib/utils";

type FlowStep = 1 | 2 | 3 | 4;
const HOLD_TTL_SECONDS = 600;

export default function BookingLabPage() {
  const api = getApi();
  const queryClient = useQueryClient();
  const { isGolden } = useCurrentRun();

  const [form, setForm] = useState<OfferRequest>({
    service_run_id: GOLDEN.serviceRunId,
    origin_station_id: GOLDEN.origin,
    dest_station_id: GOLDEN.dest,
    seat_class: GOLDEN.seatClass,
    quantity: GOLDEN.quantity,
    priority_passenger: false,
  });

  const [offer, setOffer] = useState<OfferData | null>(null);
  const [hold, setHold] = useState<HoldData | null>(null);
  const [confirmData, setConfirmData] = useState<ConfirmData | null>(null);
  const [offerExpired, setOfferExpired] = useState(false);
  // Idempotency-Key cố định theo từng bước — retry dùng lại đúng key
  const [holdKey, setHoldKey] = useState("");
  const [confirmKey, setConfirmKey] = useState("");

  const step: FlowStep = confirmData ? 4 : hold ? 3 : offer ? 2 : 1;

  const invalidateMatrix = () => {
    queryClient.invalidateQueries({ queryKey: ["seatmap"] });
    queryClient.invalidateQueries({ queryKey: ["overview"] });
    queryClient.invalidateQueries({ queryKey: ["analytics"] });
  };

  const offerMutation = useMutation({
    mutationFn: (req: OfferRequest) => api.createOffer(req),
    onSuccess: (data) => {
      setOffer(data);
      setHold(null);
      setConfirmData(null);
      setOfferExpired(false);
      setHoldKey(newIdempotencyKey());
      invalidateMatrix();
    },
  });

  const holdMutation = useMutation({
    mutationFn: () =>
      api.createHold(
        { offer_id: offer!.offer_id!, expected_matrix_version: offer!.matrix_version!, passenger_name: "Booking Lab", consent: Boolean(offer!.requires_customer_consent) },
        holdKey,
      ),
    onSuccess: (data) => {
      setHold(data);
      setConfirmKey(newIdempotencyKey());
      invalidateMatrix();
    },
  });

  const confirmMutation = useMutation({
    mutationFn: () => api.confirmBooking(hold!.hold_id!, confirmKey),
    onSuccess: (data) => {
      setConfirmData(data);
      invalidateMatrix();
    },
  });

  const resetFlow = () => {
    setOffer(null);
    setHold(null);
    setConfirmData(null);
    setOfferExpired(false);
    offerMutation.reset();
    holdMutation.reset();
    confirmMutation.reset();
  };

  const searchOffer = () => {
    resetFlow();
    offerMutation.mutate(form);
  };

  const activeError =
    (offerExpired && step === 2 ? new ApiError("OFFER_EXPIRED", "Đề nghị đã hết hạn", 410) : null) ??
    (offerMutation.isError ? offerMutation.error : null) ??
    (holdMutation.isError ? holdMutation.error : null) ??
    (confirmMutation.isError ? confirmMutation.error : null);

  if (!isGolden) {
    return (
      <Card>
        <CardBody className="mx-auto max-w-lg space-y-3 py-14 text-center">
          <TrainFront className="mx-auto h-10 w-10 text-muted/50" aria-hidden />
          <h2 className="text-[19px] font-bold text-ink">Chỉ khả dụng với chuyến vàng (golden scenario)</h2>
          <p className="text-sm text-muted">
            Booking Lab minh họa ghép chặng trên bộ dữ liệu mẫu {GOLDEN.serviceRunId} (40 ghế, 8 ga) — không dùng
            được với dữ liệu chuyến thật đang chọn vì khác cấu trúc ghế/ga. Chọn lại chuyến vàng ở góc trên, hoặc bấm
            &quot;Đặt lại kịch bản&quot; trong Điều khiển kịch bản để nạp lại chuyến này.
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Hero chuyến */}
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 p-5">
          <span className="rounded-lg bg-primary px-3 py-1 text-[13px] font-bold text-white">SE1</span>
          <div className="flex items-center gap-4">
            <div>
              <p className="text-[24px] font-extrabold uppercase leading-tight text-ink">
                {stationName(form.origin_station_id)}
              </p>
              <p className="text-[12.5px] text-muted">Ga {stationName(form.origin_station_id)}</p>
            </div>
            <ArrowRight className="h-6 w-6 text-primary" aria-hidden />
            <div>
              <p className="text-[24px] font-extrabold uppercase leading-tight text-ink">
                {stationName(form.dest_station_id)}
              </p>
              <p className="text-[12.5px] text-muted">Ga {stationName(form.dest_station_id)}</p>
            </div>
          </div>
          <p className="flex items-center gap-2 text-[13.5px] text-muted">
            <CalendarDays className="h-4 w-4" aria-hidden /> Ngày chạy: <b className="tabular-nums text-ink">15/06/2026</b>
          </p>
          <div className="ml-auto flex items-center gap-4">
            <TrainArt className="hidden h-[84px] w-auto xl:block" />
            {step > 1 && (
              <Button variant="secondary" size="sm" onClick={resetFlow}>
                <ArrowLeftRight className="h-4 w-4" aria-hidden />
                Đổi chuyến
              </Button>
            )}
          </div>
        </div>
      </Card>

      <StepBar step={step} />

      {activeError && (
        <ErrorState
          error={activeError}
          onRetry={() => {
            if (holdMutation.isError) holdMutation.mutate();
            else if (confirmMutation.isError) confirmMutation.mutate();
            else searchOffer();
          }}
          onNewOffer={searchOffer}
        />
      )}

      {step === 1 && (
        <SearchStep form={form} setForm={setForm} loading={offerMutation.isPending} onSearch={searchOffer} />
      )}

      {step === 2 && offer && (
        <PlanStep
          offer={offer}
          form={form}
          expired={offerExpired}
          onExpire={() => setOfferExpired(true)}
          onHold={() => holdMutation.mutate()}
          holdLoading={holdMutation.isPending}
          onBack={resetFlow}
          onRecreate={searchOffer}
        />
      )}

      {step === 3 && offer && hold && (
        <HoldStep
          offer={offer}
          hold={hold}
          form={form}
          onConfirm={() => confirmMutation.mutate()}
          confirmLoading={confirmMutation.isPending}
          onCancel={resetFlow}
        />
      )}

      {step === 4 && offer && confirmData && (
        <SuccessStep offer={offer} confirmData={confirmData} form={form} onNew={searchOffer} />
      )}
    </div>
  );
}

/* ----------------------------- Thanh 4 bước ----------------------------- */

function StepBar({ step }: { step: FlowStep }) {
  const steps = ["Chọn hành trình", "Xem phương án", "Giữ chỗ", "Xác nhận"];
  return (
    <Card>
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 px-5 py-3.5" aria-label="Các bước của luồng bán">
        {steps.map((label, i) => {
          const n = (i + 1) as FlowStep;
          const done = step > n || step === 4;
          const current = step === n && step !== 4;
          return (
            <li key={label} className="flex min-w-0 flex-1 items-center gap-2">
              <span
                aria-hidden
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[13px] font-bold",
                  done ? "bg-success text-white" : current ? "bg-primary text-white" : "bg-line text-muted",
                )}
              >
                {done ? <Check className="h-4.5 w-4.5" /> : n}
              </span>
              <span className="min-w-0">
                <span
                  aria-current={current ? "step" : undefined}
                  className={cn("block truncate text-[13.5px] font-semibold", current ? "text-primary" : done ? "text-ink" : "text-muted")}
                >
                  {n}. {label}
                </span>
                <span className={cn("block text-[11.5px]", done ? "text-success" : current ? "text-primary" : "text-muted/70")}>
                  {done ? "Hoàn tất" : current ? "Đang thực hiện" : "Chưa thực hiện"}
                </span>
              </span>
              {i < steps.length - 1 && <span aria-hidden className={cn("mx-2 hidden h-0.5 flex-1 rounded md:block", done ? "bg-success/50" : "bg-line")} />}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

/* ----------------------------- Bước 1: Tìm phương án ----------------------------- */

function SearchStep({
  form,
  setForm,
  loading,
  onSearch,
}: {
  form: OfferRequest;
  setForm: React.Dispatch<React.SetStateAction<OfferRequest>>;
  loading: boolean;
  onSearch: () => void;
}) {
  const destOptions = useMemo(
    () => STATIONS.filter((s) => STATIONS.findIndex((x) => x.id === s.id) > STATIONS.findIndex((x) => x.id === form.origin_station_id)),
    [form.origin_station_id],
  );

  const swap = () => {
    // Đổi chiều chỉ hợp lệ nếu ga đến đứng sau ga đi trên tuyến — với tuyến 1 chiều, giữ nguyên và bỏ qua
  };

  return (
    <Card className="overflow-hidden">
      <div className="bg-gradient-to-br from-primary-soft via-white to-primary-soft/60 px-6 pb-2 pt-8 text-center">
        <h2 className="text-[28px] font-extrabold leading-tight text-ink">
          Tìm phương án phù hợp
          <br />
          cho hành trình của bạn
        </h2>
        <p className="mx-auto mt-2 max-w-xl text-[14px] text-muted">
          Hệ thống kiểm tra trạng thái ghế trên từng chặng để tìm phương án liên tục phù hợp.
        </p>
        <TrainArt className="mx-auto mt-4 h-[110px] w-auto max-w-full" />
      </div>
      <CardBody className="px-6 pb-6">
        <div className="grid grid-cols-2 items-end gap-3 lg:grid-cols-[1.2fr_1fr_auto_1fr_1.2fr_0.8fr]">
          <Field label="Chuyến tàu" htmlFor="bk-run">
            <div className="flex min-h-[46px] items-center gap-2 rounded-xl border border-line bg-surface px-3 text-[14px] tabular-nums text-ink">
              <TrainFront className="h-4 w-4 text-primary" aria-hidden />
              SE1 · 15/06/2026
            </div>
          </Field>
          <Field label="Ga đi" htmlFor="bk-origin">
            <select
              id="bk-origin"
              value={form.origin_station_id}
              onChange={(e) => {
                const origin = e.target.value;
                const originIdx = STATIONS.findIndex((s) => s.id === origin);
                const destIdx = STATIONS.findIndex((s) => s.id === form.dest_station_id);
                setForm((f) => ({
                  ...f,
                  origin_station_id: origin,
                  dest_station_id: destIdx > originIdx ? f.dest_station_id : STATIONS[originIdx + 1]?.id ?? f.dest_station_id,
                }));
              }}
              className="min-h-[46px] w-full rounded-xl border border-line bg-white px-3 text-[14.5px] text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            >
              {STATIONS.slice(0, -1).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <button
            type="button"
            onClick={swap}
            aria-label="Đổi chiều ga đi / ga đến (tuyến một chiều — không khả dụng)"
            className="hidden h-[46px] w-[46px] items-center justify-center self-end rounded-xl border border-line bg-white text-primary hover:bg-primary-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary lg:flex"
          >
            <ArrowLeftRight className="h-4.5 w-4.5" aria-hidden />
          </button>
          <Field label="Ga đến" htmlFor="bk-dest">
            <select
              id="bk-dest"
              value={form.dest_station_id}
              onChange={(e) => setForm((f) => ({ ...f, dest_station_id: e.target.value }))}
              className="min-h-[46px] w-full rounded-xl border border-line bg-white px-3 text-[14.5px] text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            >
              {destOptions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Hạng ghế" htmlFor="bk-class">
            <select
              id="bk-class"
              value={form.seat_class}
              onChange={(e) => setForm((f) => ({ ...f, seat_class: e.target.value }))}
              className="min-h-[46px] w-full rounded-xl border border-line bg-white px-3 text-[14.5px] text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            >
              <option value={GOLDEN.seatClass}>{SEAT_CLASS_LABEL[GOLDEN.seatClass]}</option>
            </select>
          </Field>
          <Field label="Số lượng" htmlFor="bk-qty">
            <select
              id="bk-qty"
              value={form.quantity}
              onChange={(e) => setForm((f) => ({ ...f, quantity: Number(e.target.value) }))}
              className="min-h-[46px] w-full rounded-xl border border-line bg-white px-3 text-[14.5px] tabular-nums text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            >
              {[1, 2, 3].map((n) => (
                <option key={n} value={n}>
                  {n} hành khách
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Button className="mt-4 w-full text-[16px]" loading={loading} onClick={onSearch}>
          <Search className="h-4.5 w-4.5" aria-hidden />
          Tìm phương án
        </Button>
      </CardBody>
    </Card>
  );
}

/* ----------------------------- Bước 2: Xem phương án ----------------------------- */

function PlanStep({
  offer,
  form,
  expired,
  onExpire,
  onHold,
  holdLoading,
  onBack,
  onRecreate,
}: {
  offer: OfferData;
  form: OfferRequest;
  expired: boolean;
  onExpire: () => void;
  onHold: () => void;
  holdLoading: boolean;
  onBack: () => void;
  onRecreate: () => void;
}) {
  const api = getApi();
  const plan = offer.seat_plan?.[0];
  const chosenSeats = new Set((offer.seat_plan ?? []).map((p) => p.seat_id));

  const seatmap = useQuery({
    queryKey: qk.seatmap(GOLDEN.serviceRunId),
    queryFn: () => api.getSeatmap(GOLDEN.serviceRunId),
  });

  /** Trạng thái từng ghế trên dải chặng yêu cầu — chỉ để vẽ sơ đồ toa (backend đã chọn ghế). */
  const seatVisual = (seatId: string): "chosen" | "sold" | "held" | "free" => {
    if (chosenSeats.has(seatId)) return "chosen";
    const seat = seatmap.data?.seats?.find((s) => s.seat_id === seatId);
    if (!seat || !plan) return "free";
    let worst: "free" | "held" | "sold" = "free";
    for (let s = plan.segment_from!; s <= plan.segment_to!; s++) {
      const st = (seat.states?.[String(s)] ?? "FREE") as SeatState;
      if (st === "SOLD") worst = "sold";
      else if (st === "HELD" && worst === "free") worst = "held";
    }
    return worst;
  };

  return (
    <div className={cn("grid items-start gap-4 xl:grid-cols-[1fr_330px]", expired && "opacity-70")}>
      <Card>
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="mr-auto text-[19px] font-bold text-ink">Phương án ghế được hệ thống đề xuất</h2>
            <Badge tone="success" icon={<Sparkles className="h-3.5 w-3.5" aria-hidden />}>
              Phương án AI đề xuất
            </Badge>
            {plan?.reused_gap && <Badge tone="info">Tái sử dụng khoảng ghế trống</Badge>}
          </div>
          <p className="text-[13.5px] text-muted">
            Hệ thống đã lựa chọn ghế phù hợp nhằm bảo đảm hành trình liên tục và hạn chế tạo khoảng ghế trống.
          </p>
          <p className="flex items-center gap-2 text-[14px] font-medium text-ink">
            <TrainFront className="h-4.5 w-4.5 text-primary" aria-hidden />
            Toa C01 · {SEAT_CLASS_LABEL[GOLDEN.seatClass]}
          </p>

          {/* Sơ đồ toa C01 */}
          <div>
            <p className="mb-2 text-[13px] font-semibold text-ink">Sơ đồ toa C01</p>
            <div className="overflow-x-auto">
              <div className="min-w-[560px] rounded-[28px] border-[3px] border-navy/70 bg-surface/60 p-4">
                {[0, 1].map((half) => (
                  <div key={half} className={cn("grid grid-cols-10 gap-1.5", half === 1 && "mt-5")}>
                    {Array.from({ length: 20 }).map((_, i) => {
                      const seatNum = half * 20 + i + 1;
                      const seatId = `C01-S${String(seatNum).padStart(3, "0")}`;
                      const v = seatVisual(seatId);
                      return (
                        <span
                          key={seatId}
                          role="img"
                          aria-label={`${seatId}: ${
                            v === "chosen" ? "Phương án đề xuất" : v === "sold" ? "Đã bán" : v === "held" ? "Đang giữ" : "Còn trống"
                          }`}
                          className={cn(
                            "flex h-9 items-center justify-center rounded-lg border text-[11px] font-semibold tabular-nums",
                            v === "chosen" && "border-success bg-success text-white ring-2 ring-success/40",
                            v === "sold" && "border-danger bg-danger text-white",
                            v === "held" && "border-warning bg-warning text-white",
                            v === "free" && "border-line bg-white text-ink",
                          )}
                        >
                          {v === "chosen" ? <Check className="h-4 w-4" aria-hidden /> : `S${String(seatNum).padStart(3, "0")}`}
                        </span>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
            {plan && (
              <p className="mt-1.5 inline-flex items-center gap-1.5 rounded-lg bg-success-soft px-2.5 py-1 text-[12.5px] font-medium text-success">
                <Sparkles className="h-3.5 w-3.5" aria-hidden /> Ghế AI chọn: {plan.seat_id} · chặng L{plan.segment_from}–L{plan.segment_to}
              </p>
            )}
            <ul className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[12.5px] text-ink" aria-label="Chú giải sơ đồ toa">
              {[
                ["border-line bg-white", "Còn trống"],
                ["border-success bg-success", "Phương án đề xuất"],
                ["border-warning bg-warning", "Đang giữ"],
                ["border-danger bg-danger", "Đã bán"],
              ].map(([cls, label]) => (
                <li key={label} className="flex items-center gap-1.5">
                  <span aria-hidden className={cn("h-4 w-5 rounded-md border", cls)} />
                  {label}
                </li>
              ))}
            </ul>
          </div>
        </CardBody>
      </Card>

      {/* Panel phải: Thông tin phương án */}
      <div className="space-y-3">
        <Card>
          <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
            <h3 className="text-[16px] font-semibold text-ink">Thông tin phương án</h3>
            <Badge tone="success" icon={<Sparkles className="h-3.5 w-3.5" aria-hidden />}>AI đề xuất</Badge>
          </div>
          <CardBody className="space-y-2.5 text-[13.5px]">
            <PanelRow label="Chuyến tàu" value="SE1" />
            <PanelRow label="Ga đi" value={stationName(form.origin_station_id)} />
            <PanelRow label="Ga đến" value={stationName(form.dest_station_id)} />
            <PanelRow label="Toa" value="C01" />
            <PanelRow label="Mã ghế" value={<span className="font-bold text-success">{plan?.seat_id}</span>} />
            <PanelRow label="Loại ghế" value={SEAT_CLASS_LABEL[GOLDEN.seatClass]} />
            <div className="flex items-center justify-between border-t border-line pt-2.5">
              <span className="text-muted">Giá áp dụng</span>
              <span className="text-[19px] font-bold text-primary">
                <Money amount={offer.pricing?.gia_cuoi_vnd} />
              </span>
            </div>
            {/* Diễn biến giá 3 mức */}
            <div className="rounded-xl bg-surface/70 px-3 py-2.5 text-[12.5px]">
              <div className="flex items-center justify-between">
                <span className="text-muted">Giá gốc</span>
                <Money amount={offer.pricing?.gia_goc_vnd} />
              </div>
              <div className="mt-1 flex items-center justify-between">
                <span className="text-muted">Giá niêm yết</span>
                <Money amount={offer.pricing?.gia_niem_yet_vnd} />
              </div>
              <div className="mt-1 flex items-center justify-between font-semibold text-ink">
                <span>Giá cuối</span>
                <Money amount={offer.pricing?.gia_cuoi_vnd} />
              </div>
              {offer.pricing?.clamped && (
                <p className="mt-1.5 text-warning">Giá AI đề xuất đã được điều chỉnh theo chính sách.</p>
              )}
            </div>
            {/* Bid theo chặng */}
            <div className="rounded-xl bg-surface/70 px-3 py-2.5 text-[12.5px]">
              <p className="font-medium text-ink">Giá trị bảo vệ chỗ (bid)</p>
              {Object.entries(offer.bid?.by_segment ?? {}).map(([seg, v]) => (
                <div key={seg} className="mt-1 flex items-center justify-between">
                  <span className="text-muted">Chặng L{seg}</span>
                  <Money amount={v as number} />
                </div>
              ))}
              <div className="mt-1 flex items-center justify-between font-semibold text-ink">
                <span>Tổng</span>
                <Money amount={offer.bid?.total_vnd} />
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-line pt-2.5">
              <span className="text-muted">Phương án còn hiệu lực trong</span>
              {offer.expires_at && (
                <CountdownNumber expiresAt={offer.expires_at} totalSeconds={HOLD_TTL_SECONDS} onExpire={onExpire} compact />
              )}
            </div>

            {!expired ? (
              <>
                <Button className="w-full" loading={holdLoading} onClick={onHold}>
                  <CheckCircle2 className="h-4.5 w-4.5" aria-hidden />
                  Xác nhận phương án này
                </Button>
                <div className="flex gap-2">
                  <Button variant="secondary" className="flex-1" onClick={onBack}>
                    <ArrowLeft className="h-4 w-4" aria-hidden />
                    Quay lại
                  </Button>
                  <BaselineDialog offer={offer} />
                </div>
              </>
            ) : (
              <Button className="w-full bg-warning hover:bg-warning/90" onClick={onRecreate}>
                Tạo lại phương án
              </Button>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardBody className="space-y-2 text-[12.5px] text-muted">
            <p className="flex items-center gap-1.5 font-semibold text-ink">
              <Info className="h-4 w-4 text-primary" aria-hidden /> Lưu ý
            </p>
            <ul className="list-disc space-y-1 pl-5">
              <li>Hệ thống đề xuất ghế nhằm tối ưu hành trình và giảm khoảng ghế trống.</li>
              <li>Nếu phương án hết hạn, vui lòng tạo lại đề xuất mới.</li>
            </ul>
          </CardBody>
        </Card>

        <TechInfoCard
          rows={[
            ["Mã đề nghị", offer.offer_id ?? "—"],
            ["Mã quyết định", offer.decision_record_id ?? "—"],
          ]}
          decisionId={offer.decision_record_id}
          offer={offer}
        />
      </div>
    </div>
  );
}

/* ----------------------------- Bước 3: Giữ chỗ ----------------------------- */

function HoldStep({
  offer,
  hold,
  form,
  onConfirm,
  confirmLoading,
  onCancel,
}: {
  offer: OfferData;
  hold: HoldData;
  form: OfferRequest;
  onConfirm: () => void;
  confirmLoading: boolean;
  onCancel: () => void;
}) {
  const plan = offer.seat_plan?.[0];
  const originIdx = STATIONS.findIndex((s) => s.id === form.origin_station_id);
  const destIdx = STATIONS.findIndex((s) => s.id === form.dest_station_id);
  const routeStations = STATIONS.slice(originIdx, destIdx + 1);

  return (
    <div className="grid items-start gap-4 xl:grid-cols-[1fr_330px]">
      <div className="space-y-4">
        <Card>
          <div className="border-b border-line px-5 py-3.5">
            <h2 className="flex items-center gap-2 text-[17px] font-semibold text-ink">
              <TrainFront className="h-5 w-5 text-primary" aria-hidden /> Thông tin hành trình
            </h2>
          </div>
          <CardBody className="p-0">
            <div className="grid grid-cols-3 gap-y-0 border-b border-line text-[13.5px]">
              <InfoCell label="Chuyến" value="SE1" />
              <InfoCell
                label="Hành trình"
                value={`${stationName(form.origin_station_id)} → ${stationName(form.dest_station_id)}`}
              />
              <InfoCell label="Ngày chạy" value="15/06/2026" />
            </div>
            <div className="grid grid-cols-2 gap-y-0 text-[13.5px] md:grid-cols-4">
              <InfoCell label="Toa" value="C01" />
              <InfoCell label="Mã ghế" value={plan?.seat_id ?? "—"} />
              <InfoCell label="Giá áp dụng" value={<Money amount={offer.pricing?.gia_cuoi_vnd} emphasis />} />
              <InfoCell label="Trạng thái" value={<StatusBadge status="HELD" label="Đang giữ" />} />
            </div>
          </CardBody>
        </Card>

        <Card>
          <div className="border-b border-line px-5 py-3.5">
            <h2 className="flex items-center gap-2 text-[17px] font-semibold text-ink">
              <MapPin className="h-5 w-5 text-primary" aria-hidden /> Hành trình
            </h2>
          </div>
          <CardBody>
            <div className="relative mx-2 flex items-start justify-between" aria-hidden>
              <span className="absolute left-2 right-2 top-[7px] h-0.5 bg-primary/60" />
              {routeStations.map((s, i) => (
                <span key={s.id} className="relative flex w-0 flex-col items-center">
                  <span
                    className={cn(
                      "h-4 w-4 rounded-full border-[3px] bg-white",
                      i === routeStations.length - 1 ? "border-success" : "border-primary",
                    )}
                  />
                  <span className="mt-1.5 whitespace-nowrap text-[12px] font-semibold text-ink">{s.name}</span>
                </span>
              ))}
            </div>
            <p className="mt-5 flex items-center gap-2 rounded-xl bg-primary-soft/70 px-3.5 py-2.5 text-[13px] text-ink">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" aria-hidden />
              Ghế được giữ cho toàn bộ hành trình từ {stationName(form.origin_station_id)} đến{" "}
              {stationName(form.dest_station_id)}.
            </p>
          </CardBody>
        </Card>
      </div>

      {/* Panel phải: thời gian giữ chỗ */}
      <div className="space-y-3">
        <Card>
          <CardBody className="text-center">
            <p className="flex items-center justify-center gap-2 text-[15px] font-semibold text-ink">
              <Clock className="h-4.5 w-4.5 text-warning" aria-hidden /> Thời gian giữ chỗ
            </p>
            {hold.expires_at && (
              <CountdownNumber expiresAt={hold.expires_at} totalSeconds={HOLD_TTL_SECONDS} />
            )}
            <p className="mt-2 text-[12.5px] text-muted">
              Giá và phương án ghế được giữ nguyên trong thời gian hiệu lực.
            </p>
            <div className="mt-2 flex items-center justify-center gap-1.5 rounded-xl bg-warning-soft px-3 py-2 text-[13px] font-medium text-ink">
              <Lock className="h-4 w-4 text-warning" aria-hidden />
              Giá đã khóa: <Money amount={offer.pricing?.gia_cuoi_vnd} emphasis />
            </div>
            <Button className="mt-3.5 w-full" loading={confirmLoading} onClick={onConfirm}>
              Xác nhận đặt vé
            </Button>
            <Button variant="secondary" className="mt-2 w-full" onClick={onCancel}>
              Hủy và quay lại
            </Button>
          </CardBody>
        </Card>

        <TechInfoCard
          rows={[
            ["Mã giữ chỗ", hold.hold_id ?? "—"],
            ["Ma trận sau giữ", `v${hold.new_matrix_version ?? "—"}`],
          ]}
          decisionId={offer.decision_record_id}
          offer={offer}
        />
      </div>
    </div>
  );
}

/* ----------------------------- Bước 4: Thành công ----------------------------- */

function SuccessStep({
  offer,
  confirmData,
  form,
  onNew,
}: {
  offer: OfferData;
  confirmData: ConfirmData;
  form: OfferRequest;
  onNew: () => void;
}) {
  const plan = offer.seat_plan?.[0];
  return (
    <Card>
      <CardBody className="mx-auto max-w-2xl py-10 text-center">
        <span className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-success text-white shadow-lg shadow-success/30">
          <Check className="h-10 w-10" aria-hidden strokeWidth={3} />
        </span>
        <h2 className="mt-4 text-[26px] font-extrabold text-ink">Đặt vé thành công</h2>
        <p className="mt-1 text-[14px] text-muted">
          Phương án ghế đã được xác nhận và trạng thái ghế đã được cập nhật.
        </p>

        <div className="mt-6 rounded-2xl border border-line text-left">
          <p className="border-b border-line px-5 py-3 text-[15px] font-semibold text-ink">Thông tin đặt vé</p>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4 px-5 py-4 text-[13.5px] md:grid-cols-3">
            <SuccessItem label="Mã đặt vé" value={<span className="font-mono font-semibold">{confirmData.booking_id}</span>} />
            <SuccessItem label="Chuyến" value="SE1" />
            <SuccessItem
              label="Hành trình"
              value={`${stationName(form.origin_station_id)} → ${stationName(form.dest_station_id)}`}
            />
            <SuccessItem label="Ngày chạy" value="15/06/2026" />
            <SuccessItem label="Ghế" value={plan?.seat_id ?? "—"} />
            <SuccessItem label="Trạng thái" value={<StatusBadge status="CONFIRMED" label="Đã xác nhận" />} />
            <SuccessItem label="Giá áp dụng" value={<Money amount={confirmData.final_price_vnd} emphasis />} />
          </dl>
        </div>

        {/* Bằng chứng khóa giá */}
        <section
          aria-label="Bằng chứng giá không đổi"
          className="mt-4 rounded-2xl border border-success/40 bg-success-soft/60 px-4 py-3 text-left"
        >
          <h3 className="text-sm font-semibold text-ink">Giá không đổi qua toàn bộ luồng</h3>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[13px] tabular-nums">
            <span className="rounded-lg bg-white px-3 py-1.5">Đề nghị: <Money amount={offer.pricing?.gia_cuoi_vnd} /></span>
            <ArrowRight className="h-4 w-4 text-muted" aria-hidden />
            <span className="rounded-lg bg-white px-3 py-1.5">Giữ chỗ (khóa): <Money amount={offer.pricing?.gia_cuoi_vnd} /></span>
            <ArrowRight className="h-4 w-4 text-muted" aria-hidden />
            <span className="rounded-lg bg-white px-3 py-1.5 font-semibold">Vé xuất: <Money amount={confirmData.final_price_vnd} /></span>
          </div>
        </section>

        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button onClick={onNew}>
            <TrainFront className="h-4.5 w-4.5" aria-hidden />
            Đặt hành trình khác
          </Button>
          <Link href="/ops">
            <Button variant="secondary">Về Trang chủ</Button>
          </Link>
        </div>
        <Link
          href={`/decisions/${confirmData.decision_record_id}`}
          className="mt-4 inline-flex items-center gap-1 text-[14px] font-medium text-primary underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
        >
          Xem cách hệ thống đưa ra quyết định <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </CardBody>
    </Card>
  );
}

/* ----------------------------- Thành phần phụ ----------------------------- */

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-[12.5px] font-medium text-muted">
        {label}
      </label>
      {children}
    </div>
  );
}

function PanelRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted">{label}</span>
      <span className="text-right font-medium text-ink">{value}</span>
    </div>
  );
}

function InfoCell({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="px-5 py-3.5">
      <p className="text-[12px] text-muted">{label}</p>
      <p className="mt-0.5 font-semibold text-ink">{value}</p>
    </div>
  );
}

function SuccessItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[12px] text-muted">{label}</dt>
      <dd className="mt-0.5 text-ink">{value}</dd>
    </div>
  );
}

/** Đếm ngược số to màu cam + thanh tiến độ (mockup bước giữ chỗ). */
function CountdownNumber({
  expiresAt,
  totalSeconds,
  onExpire,
  compact = false,
}: {
  expiresAt: string;
  totalSeconds: number;
  onExpire?: () => void;
  compact?: boolean;
}) {
  const [secondsLeft, setSecondsLeft] = useState(() => Math.floor((Date.parse(expiresAt) - Date.now()) / 1000));

  useEffect(() => {
    setSecondsLeft(Math.floor((Date.parse(expiresAt) - Date.now()) / 1000));
    const timer = setInterval(() => {
      setSecondsLeft((prev) => {
        const next = Math.floor((Date.parse(expiresAt) - Date.now()) / 1000);
        if (next <= 0 && prev > 0) onExpire?.();
        return next;
      });
    }, 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiresAt]);

  const expired = secondsLeft <= 0;
  const pct = Math.max(0, Math.min(100, (secondsLeft / totalSeconds) * 100));

  if (compact) {
    return (
      <span className={cn("text-[17px] font-bold tabular-nums", expired ? "text-danger" : "text-warning")} aria-live="polite">
        {expired ? "Hết hạn" : formatCountdown(secondsLeft)}
      </span>
    );
  }
  return (
    <div aria-live="polite">
      <p className={cn("mt-1 text-[44px] font-extrabold leading-tight tabular-nums", expired ? "text-danger" : "text-warning")}>
        {expired ? "Hết hạn" : formatCountdown(secondsLeft)}
      </p>
      <div className="mx-auto mt-1 h-2 w-full overflow-hidden rounded-full bg-line/70" aria-hidden>
        <div className="h-full rounded-full bg-warning transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Thông tin kỹ thuật: 4 versions + mã tham chiếu — bất biến trung tâm luôn hiển thị. */
function TechInfoCard({
  rows,
  decisionId,
  offer,
}: {
  rows: [string, string][];
  decisionId?: string;
  offer: OfferData;
}) {
  const [open, setOpen] = useState(true);
  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-4 py-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
      >
        <span className="text-[15px] font-semibold text-ink">Thông tin kỹ thuật</span>
        <ChevronDown className={cn("h-4 w-4 text-muted transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <CardBody className="space-y-2 border-t border-line text-[13px]">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-3">
              <span className="text-muted">{label}</span>
              <span className="font-mono text-[12px] text-ink">{value}</span>
            </div>
          ))}
          <div className="border-t border-line pt-2">
            <VersionStrip
              serviceRunId={offer.service_run_id}
              matrixVersion={offer.matrix_version}
              forecastVersion={offer.forecast_version}
              policyVersion={offer.policy_version}
            />
          </div>
          {decisionId && (
            <Link
              href={`/decisions/${decisionId}`}
              className="inline-flex items-center gap-1 text-[13px] font-medium text-primary hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            >
              Vì sao có giá này? ({decisionId}) <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
          )}
        </CardBody>
      )}
    </Card>
  );
}

/** So sánh baseline: cùng yêu cầu — cách bán cũ từ chối, Âu Lạc phục vụ trên khoảng ghế trống. */
function BaselineDialog({ offer }: { offer: OfferData }) {
  const plan = offer.seat_plan?.[0];
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="secondary" className="flex-1">
          <Scale className="h-4 w-4" aria-hidden />
          So sánh baseline
        </Button>
      </DialogTrigger>
      <DialogContent
        title="Cùng một yêu cầu — hai kết quả"
        description="Minh họa vì sao quản lý theo từng chặng phục vụ được khách mà cách bán cũ bỏ lỡ."
        className="w-[min(720px,calc(100vw-2rem))]"
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-danger/30 bg-danger-soft/50 p-4">
            <div className="flex items-center justify-between gap-2">
              <h4 className="font-semibold text-ink">Phương án cơ sở</h4>
              <StatusBadge status="REJECT" label="Từ chối" />
            </div>
            <p className="mt-2 text-sm text-muted">
              Bán ghế theo <b className="text-ink">nguyên hành trình tàu</b>: ghế đã có khách ở chặng khác bị coi là
              hết, dù đang trống đúng đoạn khách cần. Yêu cầu này bị trả về{" "}
              <code className="font-mono text-[12px]">ALLOCATION_REJECTED</code> — một lượt &ldquo;hết chỗ giả&rdquo;.
            </p>
            <p className="mt-2 text-sm text-muted">Doanh thu tăng thêm: <b className="text-ink">0 ₫</b></p>
          </div>
          <div className="rounded-xl border border-success/40 bg-success-soft/50 p-4">
            <div className="flex items-center justify-between gap-2">
              <h4 className="font-semibold text-ink">Âu Lạc Railway</h4>
              <StatusBadge status="ACCEPT" label="Chấp nhận mở bán" />
            </div>
            <p className="mt-2 text-sm text-muted">
              Theo dõi ghế <b className="text-ink">theo từng chặng</b> nên thấy ghế{" "}
              <b className="tabular-nums text-ink">{plan?.seat_id}</b> trống đúng dải{" "}
              <b className="tabular-nums text-ink">L{plan?.segment_from}–L{plan?.segment_to}</b>{" "}
              giữa hai lượt khách — bán lại khoảng trống này, không ảnh hưởng ai.
            </p>
            <p className="mt-2 text-sm text-muted">
              Doanh thu tăng thêm: <b className="text-ink"><Money amount={offer.pricing?.gia_cuoi_vnd} /></b>
            </p>
          </div>
        </div>
        <p className="mt-3 text-[12px] text-muted">
          Cả hai kết quả đều do backend quyết định trên cùng một luồng nhu cầu; xem đối chứng thống kê đầy đủ ở màn
          &ldquo;So sánh Backtest&rdquo;.
        </p>
      </DialogContent>
    </Dialog>
  );
}
