import { Tooltip } from "@/components/ui/tooltip";

/**
 * 4 định danh nhất quán của một quyết định — bất biến trung tâm.
 * Luôn hiển thị khi có offer/decision; giám khảo hỏi "offer này nhất quán không?"
 * → trả lời bằng dải version này.
 */
export function VersionStrip({
  serviceRunId,
  matrixVersion,
  forecastVersion,
  policyVersion,
  className,
}: {
  serviceRunId?: string;
  matrixVersion?: number;
  forecastVersion?: number;
  policyVersion?: number;
  className?: string;
}) {
  const items: { label: string; hint: string; value: string }[] = [
    { label: "Chuyến", hint: "service_run_id", value: serviceRunId ?? "—" },
    { label: "Ma trận", hint: "matrix_version", value: matrixVersion !== undefined ? `v${matrixVersion}` : "—" },
    { label: "Dự báo", hint: "forecast_version", value: forecastVersion !== undefined ? `v${forecastVersion}` : "—" },
    { label: "Chính sách", hint: "policy_version", value: policyVersion !== undefined ? `v${policyVersion}` : "—" },
  ];
  return (
    <dl className={`flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] ${className ?? ""}`}>
      {items.map((it) => (
        <Tooltip key={it.hint} label={it.hint}>
          <div className="flex cursor-default items-center gap-1.5">
            <dt className="text-muted">{it.label}</dt>
            <dd className="font-medium tabular-nums text-ink">{it.value}</dd>
          </div>
        </Tooltip>
      ))}
    </dl>
  );
}
