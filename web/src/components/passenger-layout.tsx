"use client";

import Link from "next/link";
import { ArrowLeft, CalendarDays, Check, Clock3, Home, MapPin, TrainFront } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { TrainArt } from "@/components/train-art";
import { cn } from "@/lib/utils";
import { SEAT_CLASS_LABEL, stationName, trainDisplayName } from "@/lib/constants";
import type { OfferRequest } from "@/api";

export function BookingHeader() {
  return (
    <header className="mx-auto flex min-h-[62px] max-w-[1640px] items-center rounded-xl border border-line bg-white px-3.5 shadow-card md:min-h-[72px] md:px-5">
      <BrandLogo className="w-[74px] sm:w-[86px] md:w-[100px]" />
      <span aria-hidden className="mx-3.5 h-8 w-px bg-line md:mx-5 md:h-9" />
      <span className="text-[18px] font-semibold text-ink md:text-[21px]">Đặt vé</span>
      <Link
        href="/"
        className="ml-auto inline-flex h-9 w-9 items-center justify-center gap-2 rounded-lg border border-primary/35 text-[14px] font-semibold text-primary transition-colors hover:bg-primary-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary sm:h-auto sm:min-h-[40px] sm:w-auto sm:px-4"
      >
        <Home className="h-5 w-5" aria-hidden />
        <span className="hidden sm:inline">Quay lại Trang chủ</span>
      </Link>
    </header>
  );
}

export function JourneyBanner({ request }: { request: OfferRequest }) {
  return (
    <div className="relative mx-auto grid max-w-[1640px] overflow-hidden rounded-lg border border-line bg-white shadow-card md:grid-cols-[1fr_330px]">
      <div className="p-5 md:p-7">
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-lg bg-primary px-3 py-1.5 text-sm font-bold text-white">{trainDisplayName(request.service_run_id)}</span>
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-muted"><CalendarDays className="h-4 w-4" aria-hidden />{serviceDateFromRunId(request.service_run_id)}</span>
          <span className="rounded-full bg-success-soft px-3 py-1 text-xs font-semibold text-success">Đang mở bán</span>
        </div>
        <div className="mt-5 grid grid-cols-[1fr_auto_1fr] items-center gap-3 md:max-w-[720px]">
          <JourneyStation name={stationName(request.origin_station_id)} code={request.origin_station_id} align="left" />
          <div className="flex min-w-[90px] items-center" aria-hidden><span className="h-2 w-2 rounded-full bg-primary" /><span className="h-px flex-1 bg-primary" /><TrainFront className="mx-2 h-5 w-5 text-primary" /><span className="h-px flex-1 bg-primary" /><span className="h-2 w-2 rounded-full bg-primary" /></div>
          <JourneyStation name={stationName(request.dest_station_id)} code={request.dest_station_id} align="right" />
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-4 text-sm text-muted">
          <span className="inline-flex items-center gap-1.5"><Clock3 className="h-4 w-4" aria-hidden />{request.quantity} hành khách</span>
          <span>{SEAT_CLASS_LABEL[request.seat_class] ?? request.seat_class}</span>
          <Link href="/booking" className="ml-auto inline-flex min-h-11 items-center rounded-lg border border-primary px-5 font-semibold text-primary hover:bg-primary-soft">Đổi chuyến</Link>
        </div>
      </div>
      <div className="relative hidden overflow-hidden bg-[#dceeff] md:block">
        <MapPin className="absolute right-6 top-5 h-6 w-6 text-primary/35" aria-hidden />
        <TrainArt className="absolute bottom-4 right-2 w-[340px]" />
      </div>
    </div>
  );
}

function serviceDateFromRunId(serviceRunId: string): string {
  return serviceRunId.match(/\d{4}-\d{2}-\d{2}/)?.[0] ?? serviceRunId;
}

function JourneyStation({ name, code, align }: { name: string; code: string; align: "left" | "right" }) {
  return <div className={align === "right" ? "text-right" : "text-left"}><strong className="block text-xl text-ink md:text-2xl">{code}</strong><span className="text-sm font-medium text-muted">{name}</span></div>;
}

export function BookingSteps({ current, complete = false }: { current: 1 | 2 | 3 | 4; complete?: boolean }) {
  const labels = ["Chọn hành trình", "Xem phương án", "Giữ chỗ", "Xác nhận"];
  const mobileLabels = ["Hành trình", "Phương án", "Giữ chỗ", "Xác nhận"];
  return (
    <ol className="mx-auto grid min-h-[62px] max-w-[1640px] grid-cols-4 items-center gap-2 rounded-2xl border border-line bg-white px-2.5 py-2 shadow-card sm:gap-4 md:px-6">
      {labels.map((label, index) => {
        const n = (index + 1) as 1 | 2 | 3 | 4;
        const done = n < current || (complete && n === current);
        const active = n === current && !complete;
        return (
          <li key={label} className="relative flex min-w-0 items-center">
            <div
              className={cn(
                "relative flex min-h-[42px] w-full items-center justify-center gap-1.5 rounded-[9px] border px-1.5 pb-1 transition sm:gap-2 sm:px-3",
                done && "border-success bg-success text-white",
                active && "border-primary bg-primary text-white shadow-[0_5px_14px_rgba(18,97,201,0.20)]",
                !done && !active && "border-[#cbd7e7] bg-[#eef3f9] text-muted",
              )}
            >
              <span
                className={cn(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-[5px] border text-[10px] font-bold sm:h-6 sm:w-6 sm:text-xs",
                  done && "border-white/70 bg-white/20 text-white",
                  active && "border-white/70 bg-white/20 text-white",
                  !done && !active && "border-[#d4deeb] bg-white text-muted",
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" aria-hidden /> : n}
              </span>
              <span className={cn(
                "max-w-full truncate text-center text-[9.5px] font-semibold leading-none sm:text-[12px] lg:text-[13px]",
                active || done ? "text-white" : "text-muted",
              )}>
                <span className="sm:hidden">{mobileLabels[index]}</span>
                <span className="hidden sm:inline">{label}</span>
              </span>
              <span className="ml-auto hidden gap-1 lg:flex" aria-hidden>
                {[0, 1, 2].map((window) => (
                  <span
                    key={window}
                    className={cn(
                      "h-2 w-3 rounded-[2px] border",
                      active || done ? "border-white/70 bg-white/25" : "border-[#d4deeb] bg-white",
                    )}
                  />
                ))}
              </span>
              <span aria-hidden className={cn("absolute -bottom-[5px] left-[18%] h-2.5 w-2.5 rounded-full border-2 border-white", active ? "bg-primary-dark" : done ? "bg-success" : "bg-[#77879c]")} />
              <span aria-hidden className={cn("absolute -bottom-[5px] right-[18%] h-2.5 w-2.5 rounded-full border-2 border-white", active ? "bg-primary-dark" : done ? "bg-success" : "bg-[#77879c]")} />
            </div>
            {n < 4 && (
              <span
                aria-hidden
                className="absolute -right-2 top-1/2 z-10 h-1.5 w-2 -translate-y-1/2 rounded-sm border border-[#9aa9ba] bg-white sm:-right-4 sm:w-4"
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function PassengerPage({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("min-h-dvh overflow-x-hidden bg-[#f3f8ff] p-2 sm:p-2.5", className)}>{children}</div>;
}

export function BackButton({ href, label = "Quay lại" }: { href: string; label?: string }) {
  return (
    <Link href={href} className="inline-flex min-h-[46px] items-center justify-center gap-2 rounded-lg border border-primary px-5 font-semibold text-primary hover:bg-primary-soft">
      <ArrowLeft className="h-4 w-4" aria-hidden /> {label}
    </Link>
  );
}

export function JourneySummaryIcon() {
  return (
    <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft text-primary">
      <TrainFront className="h-6 w-6" aria-hidden />
    </span>
  );
}
