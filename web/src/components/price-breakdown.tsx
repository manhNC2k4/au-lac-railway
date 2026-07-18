import { ArrowRight } from "lucide-react";
import { Money } from "@/components/money";
import { StatusBadge } from "@/components/status-badge";
import type { PricingBlock } from "@/api/types";

/**
 * Diễn biến giá 3 mức: giá gốc → giá niêm yết → giá cuối.
 * Backend đã tính xong — chỉ hiển thị, kèm cờ "kẹp theo chính sách" nếu có.
 */
export function PriceBreakdown({ pricing }: { pricing: PricingBlock }) {
  const steps = [
    { key: "gia_goc_vnd", label: "Giá gốc", value: pricing.gia_goc_vnd },
    { key: "gia_niem_yet_vnd", label: "Giá niêm yết", value: pricing.gia_niem_yet_vnd },
    { key: "gia_cuoi_vnd", label: "Giá cuối", value: pricing.gia_cuoi_vnd, final: true },
  ];
  return (
    <div>
      <ol className="flex flex-wrap items-stretch gap-2">
        {steps.map((s, i) => (
          <li key={s.key} className="flex items-center gap-2">
            <div
              className={
                s.final
                  ? "rounded-xl border-2 border-success bg-success-soft px-4 py-2.5"
                  : "rounded-xl border border-line bg-white px-4 py-2.5"
              }
            >
              <div className="text-[12px] text-muted">{s.label}</div>
              <div className="text-lg font-semibold tabular-nums text-ink">
                <Money amount={s.value} />
              </div>
            </div>
            {i < steps.length - 1 && <ArrowRight className="h-4 w-4 shrink-0 text-muted" aria-hidden />}
          </li>
        ))}
      </ol>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[13px] text-muted">
        {pricing.che_do_gia && <span>Chế độ giá: <b className="text-ink">{pricing.che_do_gia}</b></span>}
        {pricing.clamped && <StatusBadge status="CLAMPED" />}
      </div>
    </div>
  );
}
