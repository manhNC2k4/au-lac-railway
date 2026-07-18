import type { ConfirmData, HoldData, OfferData, OfferRequest } from "@/api";

export interface BookingSession {
  request: OfferRequest;
  passengerName: string;
  offer: OfferData;
  offerDeadline: string;
  hold?: HoldData;
  holdDeadline?: string;
  confirmation?: ConfirmData;
  returnJourney?: ReturnJourneyDraft;
}

export interface ReturnJourneyDraft {
  originStationName: string;
  destinationStationName: string;
  departureDate: string;
  quantity: number;
}

const KEY = "aulac.booking.v1";
const RETURN_KEY = "aulac.booking.return.v1";

export function apiDeadline(value: string, fallbackSeconds: number): string {
  const parsed = Date.parse(value);
  return new Date(Number.isFinite(parsed) && parsed > Date.now() ? parsed : Date.now() + fallbackSeconds * 1000).toISOString();
}

export function saveBookingSession(value: BookingSession): void {
  sessionStorage.setItem(KEY, JSON.stringify(value));
}

export function loadBookingSession(): BookingSession | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as BookingSession) : null;
  } catch {
    return null;
  }
}

export function clearBookingSession(): void {
  sessionStorage.removeItem(KEY);
}

export function savePendingReturnJourney(value: ReturnJourneyDraft): void {
  sessionStorage.setItem(RETURN_KEY, JSON.stringify(value));
}

export function loadPendingReturnJourney(): ReturnJourneyDraft | null {
  try {
    const raw = sessionStorage.getItem(RETURN_KEY);
    return raw ? (JSON.parse(raw) as ReturnJourneyDraft) : null;
  } catch {
    return null;
  }
}

export function clearPendingReturnJourney(): void {
  sessionStorage.removeItem(RETURN_KEY);
}
