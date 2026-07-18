import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { Tooltip } from "@/components/ui/tooltip";
import { Info } from "lucide-react";

/** Ô chỉ số dashboard: nhãn ngắn + giá trị to + chú thích đơn vị/mẫu số. */
export function KpiCard({
  label,
  value,
  hint,
  sub,
  icon,
}: {
  label: string;
  value: ReactNode;
  /** Giải thích cách tính / mẫu số — hiện trong tooltip. */
  hint?: string;
  sub?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <Card className="px-4 py-3.5">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[13px] font-medium text-muted">
          {icon}
          {label}
          {hint && (
            <Tooltip label={hint}>
              <button
                type="button"
                aria-label={`Giải thích: ${label}`}
                className="rounded p-1 text-muted/70 hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
              >
                <Info className="h-3.5 w-3.5" aria-hidden />
              </button>
            </Tooltip>
          )}
        </span>
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-[13px] text-muted">{sub}</div>}
    </Card>
  );
}
