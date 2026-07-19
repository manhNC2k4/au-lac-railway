import { BadgeCheck, CircleDollarSign, Info, Sparkles } from "lucide-react";
import { Money } from "@/components/money";
import type { PricingBlock } from "@/api/types";
import { cn } from "@/lib/utils";

/**
 * Tóm tắt giá dành cho hành khách. Công thức và guardrail chi tiết chỉ hiện ở
 * màn admin/decision audit, tránh đưa thuật ngữ mô hình vào luồng mua vé.
 */
export function PriceBreakdown({ pricing, compact = false }: { pricing: PricingBlock; compact?: boolean }) {
  return (
    <div className="rounded-lg border border-line bg-white p-4">
      <div className={cn("grid gap-2", !compact && "sm:grid-cols-3")}>
        <PriceStep icon={<CircleDollarSign className="h-4 w-4" />} label="Giá cơ sở" amount={pricing.gia_goc_vnd} />
        <PriceStep icon={<Sparkles className="h-4 w-4" />} label="AI đề xuất" amount={pricing.gia_niem_yet_vnd} />
        <PriceStep icon={<BadgeCheck className="h-4 w-4" />} label="Giá đã duyệt" amount={pricing.gia_cuoi_vnd} approved />
      </div>
      <p className="mt-3 flex items-start gap-2 border-t border-line pt-3 text-sm leading-6 text-muted"><Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" />AI đề xuất giá theo ngày đi, nhu cầu và số chỗ còn lại. Mức cuối cùng đã được nhân viên kiểm tra và phê duyệt.</p>
    </div>
  );
}

function PriceStep({ icon, label, amount, approved = false }: { icon: React.ReactNode; label: string; amount: number; approved?: boolean }) {
  return (
    <div className={approved ? "rounded-lg border border-success/35 bg-success-soft p-3" : "rounded-lg border border-line bg-surface p-3"}>
      <p className={approved ? "flex items-center gap-2 text-xs font-semibold text-success" : "flex items-center gap-2 text-xs font-semibold text-muted"}>{icon}{label}</p>
      <p className="mt-2 text-lg font-bold tabular-nums text-ink"><Money amount={amount} /></p>
    </div>
  );
}
