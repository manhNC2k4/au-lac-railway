import { ApiError, type ApiErrorCode } from "@/lib/errors";
import type {
  AnalyticsData, BacktestReportData, BacktestRequest, ConfirmData, DecisionDetailData,
  GroupQuoteData, GroupQuoteRequest, HoldData, HoldRequest, OfferData, OfferRequest,
  OverrideData, OverrideRequest, OverviewData, QuotaVersionData, ResetData, SeatmapData,
  WaitlistAddData, WaitlistAddRequest, WaitlistEntry, WaitlistMatchData,
} from "./types";

export interface AuLacApi {
  readonly mode: "http";
  resetScenario(scenarioId: string, body?: { reset_clock?: boolean; apply_golden_gap?: boolean }): Promise<ResetData>;
  refreshForecast(serviceRunId: string): Promise<{ forecast_version: number }>;
  getOverview(serviceRunId: string): Promise<OverviewData>;
  getSeatmap(serviceRunId: string): Promise<SeatmapData>;
  getAnalytics(serviceRunId: string): Promise<AnalyticsData>;
  getDecision(decisionId: string): Promise<DecisionDetailData>;
  createOffer(req: OfferRequest): Promise<OfferData>;
  createHold(req: HoldRequest, idempotencyKey: string): Promise<HoldData>;
  confirmBooking(holdId: string, idempotencyKey: string): Promise<ConfirmData>;
  createBacktest(req: BacktestRequest): Promise<{ report_id: string }>;
  getBacktest(reportId: string): Promise<BacktestReportData>;
  // P7 ops — client wired, no UI yet
  overrideOfferPrice(offerId: string, req: OverrideRequest, actorRole: string): Promise<OverrideData>;
  refreshAllocation(serviceRunId: string): Promise<QuotaVersionData>;
  getAllocationVersion(version: number, serviceRunId: string): Promise<QuotaVersionData>;
  approveAllocation(version: number, serviceRunId: string, decidedBy: string, actorRole: string): Promise<QuotaVersionData>;
  rejectAllocation(version: number, serviceRunId: string, decidedBy: string, actorRole: string): Promise<QuotaVersionData>;
  rollbackAllocation(version: number, serviceRunId: string, decidedBy: string, actorRole: string): Promise<QuotaVersionData>;
  addWaitlist(req: WaitlistAddRequest): Promise<WaitlistAddData>;
  listWaitlist(serviceRunId: string): Promise<{ pending: WaitlistEntry[] }>;
  matchWaitlist(serviceRunId: string): Promise<WaitlistMatchData>;
  quoteGroup(req: GroupQuoteRequest): Promise<GroupQuoteData>;
}

const KNOWN_CODES: ApiErrorCode[] = [
  "NO_SAME_SEAT_OPTION", "SOLD_OUT_TRUE", "ALLOCATION_REJECTED", "CONSENT_REQUIRED",
  "STALE_SNAPSHOT", "SEAT_CONFLICT", "OFFER_EXPIRED", "HOLD_EXPIRED",
  "POLICY_UNAVAILABLE", "RESOURCE_NOT_FOUND", "FORBIDDEN", "GUARDRAIL_VIOLATION",
];

async function parseError(res: Response): Promise<never> {
  let code: ApiErrorCode = "UNKNOWN";
  let message = `HTTP ${res.status}`;
  let details: Record<string, unknown> | undefined;
  try {
    const body = (await res.json()) as { error_code?: string; message?: string; details?: Record<string, unknown> };
    if (body.error_code && KNOWN_CODES.includes(body.error_code as ApiErrorCode)) code = body.error_code as ApiErrorCode;
    if (body.message) message = body.message;
    details = body.details;
  } catch {}
  throw new ApiError(code, message, res.status, details);
}

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) await parseError(res);
  const body = (await res.json()) as { data?: T };
  return (body.data ?? body) as T;
}

export function createHttpClient(baseUrl = ""): AuLacApi {
  const root = `${baseUrl.replace(/\/$/, "")}/api/v1`;
  const get = async <T>(path: string, params?: Record<string, string>) => {
    const qs = params ? `?${new URLSearchParams(params)}` : "";
    return unwrap<T>(await fetch(`${root}${path}${qs}`, { cache: "no-store" }));
  };
  const post = async <T>(path: string, body?: unknown, key?: string, actorRole?: string, params?: Record<string, string>) => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (key) headers["Idempotency-Key"] = key;
    if (actorRole) headers["X-Actor-Role"] = actorRole;
    const qs = params ? `?${new URLSearchParams(params)}` : "";
    return unwrap<T>(await fetch(`${root}${path}${qs}`, { method: "POST", headers, body: JSON.stringify(body ?? {}) }));
  };
  return {
    mode: "http",
    resetScenario: (id, body) => post(`/demo/scenarios/${encodeURIComponent(id)}/reset`, body),
    refreshForecast: (service_run_id) => post("/demo/forecasts/refresh", { service_run_id }),
    getOverview: (service_run_id) => get("/demo/overview", { service_run_id }),
    getSeatmap: (service_run_id) => get("/demo/seatmap", { service_run_id }),
    getAnalytics: (service_run_id) => get("/demo/analytics", { service_run_id }),
    getDecision: (id) => get(`/decisions/${encodeURIComponent(id)}`),
    createOffer: (req) => post("/offers", req),
    createHold: (req, key) => post("/holds", req, key),
    confirmBooking: (id, key) => post(`/bookings/${encodeURIComponent(id)}/confirm`, {}, key),
    createBacktest: (req) => post("/backtests", req),
    getBacktest: (id) => get(`/backtests/${encodeURIComponent(id)}`),
    overrideOfferPrice: (offerId, req, actorRole) =>
      post(`/offers/${encodeURIComponent(offerId)}/override`, req, undefined, actorRole),
    refreshAllocation: (service_run_id) => post("/allocation/refresh", {}, undefined, undefined, { service_run_id }),
    getAllocationVersion: (version, service_run_id) => get(`/allocation/${version}`, { service_run_id }),
    approveAllocation: (version, service_run_id, decided_by, actorRole) =>
      post(`/allocation/${version}/approve`, { decided_by }, undefined, actorRole, { service_run_id }),
    rejectAllocation: (version, service_run_id, decided_by, actorRole) =>
      post(`/allocation/${version}/reject`, { decided_by }, undefined, actorRole, { service_run_id }),
    rollbackAllocation: (version, service_run_id, decided_by, actorRole) =>
      post(`/allocation/${version}/rollback`, { decided_by }, undefined, actorRole, { service_run_id }),
    addWaitlist: (req) => post("/waitlist", req),
    listWaitlist: (service_run_id) => get("/waitlist", { service_run_id }),
    matchWaitlist: (service_run_id) => post("/waitlist/match", {}, undefined, undefined, { service_run_id }),
    quoteGroup: (req) => post("/group/quote", req),
  };
}
