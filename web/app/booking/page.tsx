"use client";

import Image from "next/image";
import { FormEvent, type KeyboardEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeftRight, CalendarDays, ChevronDown, Loader2, Search } from "lucide-react";
import {
  getApi,
  qk,
  type AuLacApi,
  type OfferRequest,
  type RunSummary,
  type StationRecord,
  type StopRecord,
} from "@/api";
import { BookingHeader, BookingSteps, PassengerPage } from "@/components/passenger-layout";
import { ErrorState } from "@/components/error-state";
import { Tooltip } from "@/components/ui/tooltip";
import {
  apiDeadline,
  clearPendingReturnJourney,
  loadPendingReturnJourney,
  saveBookingSession,
  type ReturnJourneyDraft,
} from "@/lib/booking-session";

const QUANTITIES = [1, 2, 3, 4];
type TripType = "ONE_WAY" | "ROUND_TRIP";

interface SearchCriteria {
  origin: StationRecord;
  destination: StationRecord;
  departureDate: string;
  returnDate: string;
  tripType: TripType;
  quantity: number;
}

interface SearchResult {
  request: OfferRequest;
  offer: Awaited<ReturnType<AuLacApi["createOffer"]>>;
  returnJourney?: ReturnJourneyDraft;
}

export default function BookingPage() {
  const router = useRouter();
  const api = getApi();
  const [originText, setOriginText] = useState("");
  const [destinationText, setDestinationText] = useState("");
  const [tripType, setTripType] = useState<TripType>("ONE_WAY");
  const [departureDate, setDepartureDate] = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [formError, setFormError] = useState("");

  const stationsQuery = useQuery({
    queryKey: qk.stations(),
    queryFn: () => api.listStations(),
  });
  const stations = useMemo(() => stationsQuery.data?.stations ?? [], [stationsQuery.data]);

  useEffect(() => {
    const pending = loadPendingReturnJourney();
    if (!pending) return;
    setOriginText(pending.originStationName);
    setDestinationText(pending.destinationStationName);
    setDepartureDate(pending.departureDate);
    setQuantity(pending.quantity);
    setTripType("ONE_WAY");
    clearPendingReturnJourney();
  }, []);

  const search = useMutation({
    mutationFn: async (criteria: SearchCriteria): Promise<SearchResult> => {
      const runData = await api.listRuns();
      const outbound = await findMatchingRun(
        api,
        runData.runs,
        criteria.departureDate,
        criteria.origin.station_id,
        criteria.destination.station_id,
      );

      let returnJourney: ReturnJourneyDraft | undefined;
      if (criteria.tripType === "ROUND_TRIP") {
        await findMatchingRun(
          api,
          runData.runs,
          criteria.returnDate,
          criteria.destination.station_id,
          criteria.origin.station_id,
        );
        returnJourney = {
          originStationName: criteria.destination.station_name,
          destinationStationName: criteria.origin.station_name,
          departureDate: criteria.returnDate,
          quantity: criteria.quantity,
        };
      }

      const seatmap = await api.getSeatmap(outbound.run.service_run_id);
      const seatClass = seatmap.seats.find((seat) => Boolean(seat.seat_class))?.seat_class;
      if (!seatClass) throw new JourneySearchError("Chuyến phù hợp hiện chưa có hạng ghế mở bán.");

      const request: OfferRequest = {
        service_run_id: outbound.run.service_run_id,
        origin_station_id: criteria.origin.station_id,
        dest_station_id: criteria.destination.station_id,
        seat_class: seatClass,
        quantity: criteria.quantity,
        priority_passenger: false,
      };
      const offer = await api.createOffer(request);
      return { request, offer, returnJourney };
    },
    onSuccess: ({ offer, request, returnJourney }) => {
      saveBookingSession({
        request,
        passengerName: "",
        offer,
        offerDeadline: apiDeadline(offer.expires_at, 300),
        returnJourney,
      });
      router.push("/booking/offer");
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setFormError("");
    search.reset();

    const origin = resolveStation(originText, stations);
    const destination = resolveStation(destinationText, stations);
    if (!origin) return setFormError("Vui lòng chọn ga đi từ danh sách gợi ý.");
    if (!destination) return setFormError("Vui lòng chọn ga đến từ danh sách gợi ý.");
    if (origin.station_id === destination.station_id) return setFormError("Ga đi và ga đến phải khác nhau.");
    if (!departureDate) return setFormError("Vui lòng chọn ngày đi.");
    if (tripType === "ROUND_TRIP" && !returnDate) return setFormError("Vui lòng chọn ngày về.");
    if (tripType === "ROUND_TRIP" && returnDate < departureDate) {
      return setFormError("Ngày về không được sớm hơn ngày đi.");
    }
    search.mutate({ origin, destination, departureDate, returnDate, tripType, quantity });
  };

  const swap = () => {
    setOriginText(destinationText);
    setDestinationText(originText);
  };

  const searchError = search.error instanceof JourneySearchError ? search.error.message : "";

  return (
    <PassengerPage>
      <div className="space-y-2.5">
        <BookingHeader />
        <BookingSteps current={1} />

        <section className="relative mx-auto max-w-[1640px]">
          <div className="relative h-[285px] overflow-hidden rounded-[22px] shadow-[0_14px_36px_rgba(16,42,86,0.10)] md:h-[365px]">
            <Image
              src="/images/booking-hero.png"
              alt=""
              fill
              priority
              sizes="(max-width: 768px) 100vw, 1640px"
              className="object-cover object-center"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-white/95 via-white/45 to-transparent md:via-white/20" aria-hidden />
            <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-white/25 to-transparent" aria-hidden />
            <div className="absolute left-5 top-7 max-w-[560px] md:left-[52px] md:top-[44px]">
              <h1 className="max-w-[540px] text-[28px] font-bold leading-[1.12] tracking-[-0.02em] text-ink sm:text-[36px] md:text-[41px]">
                Tìm phương án phù hợp cho hành trình của bạn
              </h1>
              <p className="mt-3 max-w-[520px] text-[14px] leading-5 text-[#42526b] md:text-[16px] md:leading-6">
                Nhập ga và ngày đi, hệ thống sẽ tìm chuyến cùng phương án ghế đang khả dụng.
              </p>
            </div>
          </div>

          <form
            onSubmit={submit}
            className="relative z-10 mx-0 -mt-10 rounded-[18px] border border-white/90 bg-white/95 p-3 shadow-[0_14px_32px_rgba(16,42,86,0.16)] ring-1 ring-white/80 backdrop-blur-xl md:-mt-[58px] md:p-3"
          >
            <div className="grid gap-2.5 xl:grid-cols-[1.05fr_1fr] xl:gap-3">
              <div className="grid grid-cols-[minmax(0,1fr)_44px_minmax(0,1fr)] items-end gap-2">
                <StationInput
                  id="origin-station"
                  label="Ga đi"
                  value={originText}
                  onChange={setOriginText}
                  stations={stations}
                  disabled={stationsQuery.isPending}
                />
                <Tooltip label="Đổi ga đi và ga đến">
                  <button
                    type="button"
                    onClick={swap}
                    disabled={!originText && !destinationText}
                    aria-label="Đổi ga đi và ga đến"
                    className="flex min-h-[46px] items-center justify-center rounded-xl border border-primary/25 bg-white px-2 text-primary transition hover:-translate-y-0.5 hover:border-primary hover:bg-primary-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 xl:min-h-[52px]"
                  >
                    <ArrowLeftRight className="h-5 w-5" aria-hidden />
                  </button>
                </Tooltip>
                <StationInput
                  id="destination-station"
                  label="Ga đến"
                  value={destinationText}
                  onChange={setDestinationText}
                  stations={stations}
                  disabled={stationsQuery.isPending}
                />
              </div>

              <div className="grid grid-cols-2 items-end gap-2 sm:grid-cols-[1.1fr_1fr_1fr_.72fr]">
                <TripTypeField value={tripType} onChange={(value) => {
                  setTripType(value);
                  if (value === "ONE_WAY") setReturnDate("");
                }} />
                <DateField label="Ngày đi" value={departureDate} onChange={setDepartureDate} />
                <DateField
                  label="Ngày về"
                  value={returnDate}
                  onChange={setReturnDate}
                  disabled={tripType === "ONE_WAY"}
                  min={departureDate || undefined}
                />
                <SelectField
                  label="Số lượng"
                  value={String(quantity)}
                  onChange={(value) => setQuantity(Number(value))}
                  options={QUANTITIES.map((value) => ({ value: String(value), label: `${value} khách` }))}
                />
              </div>
            </div>

            {tripType === "ROUND_TRIP" && (
              <p className="mt-1.5 text-[11.5px] text-muted">
                Vé khứ hồi được xử lý thành hai lượt; sau khi hoàn tất lượt đi, hệ thống sẽ mở sẵn hành trình lượt về.
              </p>
            )}
            {(formError || searchError) && (
              <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-sm font-medium text-danger" role="alert">
                {formError || searchError}
              </p>
            )}

            <button
              disabled={search.isPending || stationsQuery.isPending || !stations.length}
              type="submit"
              className="mt-2.5 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-[10px] bg-primary px-6 text-[14.5px] font-semibold text-white shadow-[0_7px_16px_rgba(18,97,201,0.22)] transition hover:-translate-y-0.5 hover:bg-primary-dark hover:shadow-[0_10px_20px_rgba(18,97,201,0.28)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary active:translate-y-0 disabled:cursor-not-allowed disabled:bg-primary/45 disabled:shadow-none"
            >
              {search.isPending || stationsQuery.isPending ? (
                <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
              ) : (
                <Search className="h-5 w-5" aria-hidden />
              )}
              {search.isPending ? "Đang tìm chuyến phù hợp…" : stationsQuery.isPending ? "Đang tải danh mục ga…" : "Tìm phương án"}
            </button>

            {stationsQuery.isError && (
              <div className="mt-4">
                <ErrorState compact error={stationsQuery.error} onRetry={() => stationsQuery.refetch()} />
              </div>
            )}
            {search.isError && !searchError && (
              <div className="mt-4">
                <ErrorState compact error={search.error} onRetry={() => search.reset()} />
              </div>
            )}
          </form>
        </section>
      </div>
    </PassengerPage>
  );
}

function StationInput({
  id,
  label,
  value,
  onChange,
  stations,
  disabled,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  stations: StationRecord[];
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const filteredStations = useMemo(() => {
    const query = normalizeSearch(value);
    if (!query) return stations;
    return stations.filter((station) =>
      normalizeSearch(station.station_name).includes(query)
      || normalizeSearch(station.station_id).includes(query)
    );
  }, [stations, value]);

  const selectStation = (station: StationRecord) => {
    onChange(station.station_name);
    setOpen(false);
    setActiveIndex(-1);
  };

  useEffect(() => {
    if (!open || activeIndex < 0) return;
    document.getElementById(`${id}-option-${activeIndex}`)?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, id, open]);

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) => Math.min(current + 1, filteredStations.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!filteredStations.length) return;
      setActiveIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter" && open && activeIndex >= 0 && filteredStations[activeIndex]) {
      event.preventDefault();
      selectStation(filteredStations[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  return (
    <label className="relative block min-w-0">
      <span className="mb-1 block text-[12.5px] font-medium text-[#42526b]">{label}</span>
      <input
        aria-label={label}
        role="combobox"
        aria-expanded={open}
        aria-controls={`${id}-options`}
        aria-autocomplete="list"
        aria-activedescendant={activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
          setActiveIndex(-1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 100)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        autoComplete="off"
        placeholder={disabled ? "Đang tải…" : label}
        className="min-h-[46px] w-full rounded-[10px] border border-[#cbd8e8] bg-white px-3 text-[14px] font-semibold text-ink outline-none transition placeholder:font-normal placeholder:text-muted focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:bg-surface xl:min-h-[52px] xl:text-[14.5px]"
      />
      {open && !disabled && (
        <div
          id={`${id}-options`}
          role="listbox"
          className={`scrollbar-hidden absolute bottom-[calc(100%+6px)] z-[70] max-h-[210px] w-[min(300px,calc(100vw-32px))] overflow-x-hidden overflow-y-auto overscroll-contain rounded-xl border border-[#cbd8e8] bg-white p-1.5 shadow-[0_12px_30px_rgba(16,42,86,0.18)] sm:w-full ${id === "destination-station" ? "right-0" : "left-0"}`}
        >
          {filteredStations.length ? filteredStations.map((station, index) => (
            <button
              id={`${id}-option-${index}`}
              key={station.station_id}
              type="button"
              role="option"
              aria-selected={index === activeIndex}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => selectStation(station)}
              className={`flex min-h-9 w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-[13.5px] transition ${index === activeIndex ? "bg-primary-soft text-primary" : "text-ink hover:bg-surface"}`}
            >
              <span className="truncate font-medium">{station.station_name}</span>
              <span className="shrink-0 text-[11px] font-semibold text-muted">{station.station_id}</span>
            </button>
          )) : (
            <p className="px-3 py-4 text-center text-sm text-muted">Không tìm thấy ga phù hợp</p>
          )}
        </div>
      )}
    </label>
  );
}

function DateField({
  label,
  value,
  onChange,
  disabled = false,
  min,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  min?: string;
}) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-[12.5px] font-medium text-[#42526b]">{label}</span>
      <span className="relative flex min-h-[46px] items-center rounded-[10px] border border-[#cbd8e8] bg-white focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 xl:min-h-[52px]">
        <input
          type="date"
          aria-label={label}
          value={value}
          min={min}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-[46px] w-full rounded-[10px] bg-transparent px-3 text-[13px] font-semibold text-ink outline-none disabled:cursor-not-allowed disabled:bg-surface disabled:text-muted xl:min-h-[52px] xl:text-[13.5px]"
        />
        <CalendarDays className="pointer-events-none absolute right-3 hidden h-4 w-4 text-muted xl:block" aria-hidden />
      </span>
    </label>
  );
}

function TripTypeField({ value, onChange }: { value: TripType; onChange: (value: TripType) => void }) {
  return (
    <fieldset className="col-span-2 min-w-0 sm:col-span-1">
      <legend className="mb-1 text-[12.5px] font-medium text-[#42526b]">Loại hành trình</legend>
      <div className="flex min-h-[46px] items-center gap-3 rounded-[10px] border border-[#cbd8e8] bg-white px-3 text-[12.5px] text-ink xl:min-h-[52px]">
        <label className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap">
          <input type="radio" name="trip-type" checked={value === "ONE_WAY"} onChange={() => onChange("ONE_WAY")} className="h-4 w-4 accent-primary" />
          Một chiều
        </label>
        <label className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap">
          <input type="radio" name="trip-type" checked={value === "ROUND_TRIP"} onChange={() => onChange("ROUND_TRIP")} className="h-4 w-4 accent-primary" />
          Khứ hồi
        </label>
      </div>
    </fieldset>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  icon,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  icon?: ReactNode;
}) {
  return (
    <label className="relative block min-w-0">
      <span className="mb-1 block text-[12.5px] font-medium text-[#42526b]">{label}</span>
      <span className="relative flex min-h-[46px] items-center rounded-[10px] border border-[#cbd8e8] bg-white transition focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 xl:min-h-[52px]">
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-label={label}
          className="peer h-full min-h-[46px] w-full appearance-none truncate rounded-[10px] bg-transparent px-3 pr-9 text-[14px] font-semibold text-ink outline-none xl:min-h-[52px] xl:text-[14.5px]"
        >
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <span className="pointer-events-none absolute right-3 flex items-center gap-1.5 text-muted">
          {icon}
          <ChevronDown className="h-4 w-4" aria-hidden />
        </span>
      </span>
    </label>
  );
}

async function findMatchingRun(
  api: AuLacApi,
  runs: RunSummary[],
  date: string,
  originId: string,
  destinationId: string,
): Promise<{ run: RunSummary; stops: StopRecord[] }> {
  const candidates = runs.filter((run) => run.service_date === date && run.status !== "CANCELLED");
  if (!candidates.length) throw new JourneySearchError(`Không có chuyến mở bán trong ngày ${formatDate(date)}.`);

  const checked = await Promise.all(candidates.map(async (run) => ({
    run,
    stops: (await api.getRunStops(run.service_run_id)).stops,
  })));
  const match = checked.find(({ stops }) => {
    const originIndex = stops.findIndex((stop) => stop.station_id === originId);
    const destinationIndex = stops.findIndex((stop) => stop.station_id === destinationId);
    return originIndex >= 0 && destinationIndex > originIndex;
  });
  if (!match) throw new JourneySearchError(`Không có chuyến phù hợp với ga đi, ga đến trong ngày ${formatDate(date)}.`);
  return match;
}

function resolveStation(value: string, stations: StationRecord[]): StationRecord | undefined {
  const normalized = value.trim().toLocaleLowerCase("vi-VN");
  return stations.find((station) =>
    station.station_name.trim().toLocaleLowerCase("vi-VN") === normalized
    || station.station_id.toLocaleLowerCase("vi-VN") === normalized
  );
}

function normalizeSearch(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .trim()
    .toLocaleLowerCase("vi-VN");
}

function formatDate(value: string): string {
  const [year, month, day] = value.split("-");
  return year && month && day ? `${day}/${month}/${year}` : value;
}

class JourneySearchError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "JourneySearchError";
  }
}
