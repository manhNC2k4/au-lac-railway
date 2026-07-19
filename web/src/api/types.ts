export type SeatState = "FREE" | "HELD" | "SOLD";
export type OfferDecision = "ACCEPT" | "REJECT";
export type HoldStatus = "ACTIVE" | "CONFIRMED" | "EXPIRED";

export interface ResetData {
  service_run_id: string;
  matrix_version: number;
  forecast_version: number;
  policy_version: number;
  checksum: string;
}

export interface RecentDecision {
  decision_id: string;
  result: string;
  final_price_vnd: number;
  explanation_code: string;
  created_at: string;
}

export interface SegmentLoad {
  segment_id: number;
  occupancy: number;
  remaining_capacity: number;
}

export interface OverviewData {
  overall_occupancy: number;
  total_revenue_vnd: number;
  empty_seat_km: number;
  passenger_km: number;
  false_sold_out_rate: number;
  bottlenecks: Pick<SegmentLoad, "segment_id" | "occupancy">[];
  underused: Pick<SegmentLoad, "segment_id" | "occupancy">[];
  recent_decisions: RecentDecision[];
}

export interface SeatmapSeat {
  seat_id: string;
  seat_class: string;
  states: Record<string, SeatState>;
}

export interface SeatmapData {
  matrix_version: number;
  seats: SeatmapSeat[];
}

export interface AnalyticsData {
  forecast_version: number;
  forecasts: { segment_id: number; forecast_remaining: number; confidence: number | null }[];
  segment_loads: SegmentLoad[];
  allocations: { segment_id: number; bid_price_vnd: number }[];
}

export interface RuleFired {
  rule_id: string;
  he_so: number;
  thu_tu: number;
}

export interface DecisionDetailData {
  decision_id: string;
  input_hash: string;
  // ponytail: quyết định nạp từ mock dataset (đa số) dùng khoá ngắn matrix/forecast/policy,
  // quyết định qua /offers thật dùng *_version — chấp cả hai, xem [decisionId]/page.tsx.
  versions: Record<string, number>;
  action: string;
  base_fare: number;
  ai_suggested_price: number;
  final_price: number;
  bid_price_total: number | null;
  bid_price_breakdown: Record<string, number> | null;
  violations: string[];
  audit_timeline: { explanation: string; rules_fired: RuleFired[] } | null;
  explanation_code: string;
  actor: string;
  created_at: string;
}

export interface OfferRequest {
  service_run_id: string;
  origin_station_id: string;
  dest_station_id: string;
  seat_class: string;
  quantity: number;
  priority_passenger: boolean;
}

export type BookingRequestStatus =
  | "SUBMITTED"
  | "AI_PROCESSING"
  | "PENDING_ADMIN"
  | "APPROVED"
  | "REJECTED"
  | "EXPIRED"
  | "SELECTED"
  | "CONFIRMED";

export type BookingCandidateStatus =
  | "AI_SUGGESTED"
  | "APPROVED"
  | "REJECTED"
  | "PRICE_OVERRIDDEN"
  | "SELECTED";

export interface BookingRequestCreate extends OfferRequest {
  passenger_name?: string;
}

export interface SeatPlanItem {
  seat_id: string;
  segment_from: number;
  segment_to: number;
  reused_gap: boolean;
  requires_seat_change: boolean;
  passenger_no?: number;
}

export interface PricingBlock {
  gia_goc_vnd: number;
  gia_niem_yet_vnd: number;
  gia_cuoi_vnd: number;
  rules_fired: RuleFired[];
  violations: string[];
  clamped: boolean;
  csxh_doi_tuong: string;
  che_do_gia: string;
  unit_price_vnd?: number;
  quantity?: number;
}

export interface BookingCandidateData {
  candidate_id: string;
  offer_id: string;
  decision_record_id: string;
  rank: number;
  ai_recommended: boolean;
  status: BookingCandidateStatus;
  seat_plan: SeatPlanItem[];
  pricing: PricingBlock;
  explanation: string;
  approved_price_vnd: number | null;
  admin_note: string | null;
  approved_by: string | null;
  approved_at: string | null;
  matrix_version: number;
  forecast_version: number;
  policy_version: number;
  decision: OfferDecision;
  expires_at: string;
  requires_customer_consent: boolean;
  change_station_ids: string[];
  so_lan_doi_cho: number;
}

export interface BookingRequestData extends BookingRequestCreate {
  request_id: string;
  status: BookingRequestStatus;
  selected_candidate_id: string | null;
  hold_id: string | null;
  booking_id: string | null;
  reject_code: string | null;
  reject_reason: string | null;
  submitted_at: string;
  processing_started_at: string | null;
  ready_for_review_at: string | null;
  approved_at: string | null;
  decided_by: string | null;
  selected_at: string | null;
  confirmed_at: string | null;
  expires_at: string;
  updated_at: string;
  candidates: BookingCandidateData[];
}

export interface BookingCandidateApproval {
  candidate_id: string;
  override_price_vnd?: number;
  reason?: string;
}

export interface BookingApprovalRequest {
  decided_by: string;
  approved_candidates: BookingCandidateApproval[];
  note?: string;
}

export interface BookingQueueData {
  requests: BookingRequestData[];
  total: number;
}

export type SeatLayoutState = "AVAILABLE" | "BOOKED" | "UNAVAILABLE";

export interface TrainSeatLayoutItem {
  seat_id: string;
  seat_index: number;
  seat_number: number;
  row_number: number;
  column_code: string;
  position_code: string;
  compartment_number: number | null;
  berth_level: "LOWER" | "MIDDLE" | "UPPER" | null;
  is_accessible: boolean;
  state: SeatLayoutState;
  ai_recommended: boolean;
  approved_option: boolean;
}

export interface TrainCoachLayout {
  coach_number: number;
  coach_label: string;
  seat_class: string;
  layout_type: "SEATED_2X2" | "SLEEPER_6" | "SLEEPER_4";
  capacity: number;
  data_source: string;
  seats: TrainSeatLayoutItem[];
}

export interface BookingSeatLayoutData {
  request_id: string;
  train_id: string;
  seat_class: string;
  quantity: number;
  segment_from: number;
  segment_to: number;
  layout_source: string;
  coaches: TrainCoachLayout[];
}

export interface OfferData {
  offer_id: string;
  service_run_id: string;
  matrix_version: number;
  forecast_version: number;
  policy_version: number;
  decision: OfferDecision;
  seat_plan: SeatPlanItem[];
  requires_customer_consent: boolean;
  change_station_ids: string[];
  so_lan_doi_cho: number;
  pricing: PricingBlock;
  bid: { total_vnd: number; by_segment: Record<string, number> };
  decision_record_id: string;
  explanation: string;
  expires_at: string;
}

export interface HoldRequest {
  offer_id: string;
  expected_matrix_version: number;
  passenger_name?: string;
  consent: boolean;
}

export interface HoldData {
  hold_id: string;
  status: HoldStatus;
  expires_at: string;
  new_matrix_version: number;
}

export interface ConfirmData {
  booking_id: string;
  status: string;
  final_price_vnd: number;
  decision_record_id: string | null;
}

export interface BacktestRequest { seeds?: number[] }
export interface BacktestMetrics {
  revenue_median: number;
  revenue_min: number;
  revenue_max: number;
}
export interface BacktestRawResult {
  false_sold_out_rate: number;
  empty_seat_km: number;
  passenger_km: number;
  baseline: { revenue_vnd: number; acceptance_rate: number };
  aulac: { revenue_vnd: number; acceptance_rate: number };
}
export interface BacktestReportData {
  status: string;
  seeds_run: number[];
  failed_seeds: number[];
  baseline_metrics: BacktestMetrics;
  ai_metrics: BacktestMetrics;
  raw: Record<string, BacktestRawResult>;
  checksum: string;
}

export type DecisionDetailExtended = DecisionDetailData;
export type BacktestReportExtended = BacktestReportData;

// --- P7 ops (client wired, no UI yet) ---

export interface QuotaRow {
  khu_gian_id: number;
  loai_hanh_trinh: "ngan" | "trung" | "dai";
  seat_class: string;
  quota: number;
  booking_limit: number;
  bid_price: number;
}

export interface QuotaProposalRow {
  khu_gian_id: number;
  loai_hanh_trinh: string;
  seat_class: string;
  action: "MO_THEM" | "SIET_LAI";
  limit_cu: number;
  limit_moi: number;
}

export interface QuotaVersionData {
  version: number;
  status: "PENDING" | "ACTIVE" | "REJECTED" | "ROLLED_BACK";
  quota: QuotaRow[];
  proposal: QuotaProposalRow[];
  decided_by: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface WaitlistAddRequest {
  service_run_id: string;
  origin_station_id: string;
  dest_station_id: string;
  seat_class: string;
  quantity?: number;
  u?: number;
  priority_passenger?: boolean;
  csxh_doi_tuong?: string;
}

export interface WaitlistAddData {
  waitlist_id: string;
  priority_score: number;
  status: "PENDING";
}

export interface WaitlistEntry {
  waitlist_id: string;
  origin_station_id: string;
  dest_station_id: string;
  seat_class: string;
  priority_score: number;
  priority_passenger: boolean;
  quantity: number;
  created_at: string;
}

export interface WaitlistMatchData {
  matched: { waitlist_id: string; hold_id: string; expires_at: string }[];
  still_pending: number;
}

export interface GroupQuoteRequest {
  service_run_id: string;
  origin_station_id: string;
  dest_station_id: string;
  seat_class: string;
  n_khach: number;
}

export interface GroupQuoteData {
  kha_thi: boolean;
  seat_class: string;
  assignments: { seat_idx: number; seg_from: number; seg_to: number; ga_di: string; ga_den: string; seat_id: string }[];
  toa: number[];
  diem_lien_ke: number;
  so_lan_tach: number;
  ghi_chu: string;
}

export interface OverrideRequest {
  new_price_vnd: number;
  reason: string;
  decided_by?: string;
}

export interface OverrideData {
  offer_id: string;
  old_price_vnd: number;
  new_price_vnd: number;
  expires_at: string;
}

export interface RunSummary {
  service_run_id: string;
  train_id: string;
  service_date: string;
  direction: string;
  status: string;
}

export interface RunsData {
  runs: RunSummary[];
}

export interface StationRecord {
  station_id: string;
  station_name: string;
  ly_trinh_km: number;
}

export interface StationsData {
  stations: StationRecord[];
}

export interface StopRecord {
  stop_sequence: number;
  station_id: string;
  station_name: string;
}

export interface StopsData {
  stops: StopRecord[];
}

export type SuggestionStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface PriceSuggestion {
  segment_id: number;
  label: string;
  seat_class: string;
  occupancy: number;
  remaining_capacity: number;
  forecast_remaining: number;
  confidence: number | null;
  base_vnd: number;
  suggested_vnd: number;
  delta_pct: number;
  expected_gain_vnd: number;
  multiplier: number;
  explanation: string;
  status: SuggestionStatus;
  decided_by: string | null;
  decided_at: string | null;
}

export interface PriceSuggestionsData {
  service_run_id: string;
  seat_class: string;
  days_to_departure?: number;
  suggestions: PriceSuggestion[];
}
