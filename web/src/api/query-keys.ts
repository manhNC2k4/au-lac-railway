/** Query key tập trung — invalidation nhất quán sau reset/hold/confirm. */
export const qk = {
  overview: (serviceRunId: string) => ["overview", serviceRunId] as const,
  seatmap: (serviceRunId: string) => ["seatmap", serviceRunId] as const,
  analytics: (serviceRunId: string) => ["analytics", serviceRunId] as const,
  decision: (decisionId: string) => ["decision", decisionId] as const,
  backtest: (reportId: string) => ["backtest", reportId] as const,
  compliance: (serviceRunId: string) => ["compliance", serviceRunId] as const,
  runs: () => ["runs"] as const,
  runStops: (serviceRunId: string) => ["runStops", serviceRunId] as const,
} as const;

/** Nhóm key bị ảnh hưởng khi ma trận ghế đổi (hold/confirm/reset). */
export const MATRIX_AFFECTED = ["overview", "seatmap", "analytics"] as const;
