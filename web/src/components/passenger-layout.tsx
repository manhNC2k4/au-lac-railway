"use client";

import Link from "next/link";
import { ArrowLeft, CalendarDays, Check, Clock3, Home, MapPin, TrainFront } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { TrainArt } from "@/components/train-art";
import { cn } from "@/lib/utils";
import { GOLDEN, SEAT_CLASS_LABEL, stationName } from "@/lib/constants";
import type { OfferRequest } from "@/api";

export function BookingHeader() {
  return (
    <header className="mx-auto flex min-h-[88px] max-w-[1640px] items-center rounded-2xl border border-line bg-white px-4 shadow-card md:min-h-[116px] md:px-8">
      <BrandLogo className="w-[76px] sm:w-[120px] md:w-[170px]" />
      <span aria-hidden className="mx-4 h-12 w-px bg-line md:mx-8 md:h-16" />
      <span className="text-[22px] font-semibold text-ink md:text-[28px]">Đặt vé</span>
      <Link
        href="/"
        className="ml-auto inline-flex h-11 w-11 items-center justify-center gap-3 rounded-lg border border-primary/35 text-[17px] font-semibold text-primary transition-colors hover:bg-primary-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary sm:h-auto sm:min-h-[52px] sm:w-auto sm:px-6"
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
          <span className="rounded-lg bg-primary px-3 py-1.5 text-sm font-bold text-white">{request.service_run_id}</span>
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-muted"><CalendarDays className="h-4 w-4" aria-hidden />{GOLDEN.serviceDate}</span>
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

function JourneyStation({ name, code, align }: { name: string; code: string; align: "left" | "right" }) {
  return <div className={align === "right" ? "text-right" : "text-left"}><strong className="block text-xl text-ink md:text-2xl">{code}</strong><span className="text-sm font-medium text-muted">{name}</span></div>;
}

export function BookingSteps({ current, complete = false }: { current: 1 | 2 | 3 | 4; complete?: boolean }) {
  const labels = ["Chọn hành trình", "Xem phương án", "Giữ chỗ", "Xác nhận"];
  return (
    <ol className="mx-auto grid min-h-[78px] max-w-[1640px] grid-cols-4 items-center rounded-2xl border border-line bg-white px-2 shadow-card md:px-8">
      {labels.map((label, index) => {
        const n = (index + 1) as 1 | 2 | 3 | 4;
        const done = n < current || (complete && n === current);
        const active = n === current && !complete;
        return (
          <li key={label} className="relative flex min-w-0 flex-col items-center justify-center gap-1 px-1 md:flex-row md:gap-3 md:px-2">
            <span
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[15px] font-semibold md:h-9 md:w-9 md:text-[18px]",
                done && "bg-success text-white",
                active && "bg-primary text-white",
                !done && !active && "bg-surface text-muted",
              )}
            >
              {done ? <Check className="h-5 w-5" aria-hidden /> : n}
            </span>
            <span className="min-w-0 text-center md:text-left">
              <span className={cn("block text-[10px] font-medium leading-tight sm:text-[12px] md:text-[16px]", active ? "text-primary" : "text-ink")}>{n}. {label}</span>
              <span className={cn("hidden text-[13px] md:block", done ? "text-success" : active ? "text-primary" : "text-muted")}> 
                {done ? "Hoàn tất" : active ? "Đang thực hiện" : "Chưa thực hiện"}
              </span>
            </span>
            {n < 4 && <span aria-hidden className="absolute -right-4 hidden h-px w-8 bg-line xl:block" />}
          </li>
        );
      })}
    </ol>
  );
}

export function PassengerPage({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("min-h-dvh bg-[#f3f8ff] p-4", className)}>{children}</div>;
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
