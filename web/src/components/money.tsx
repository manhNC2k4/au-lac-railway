import { formatVnd } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Hiển thị tiền VND (int64 đồng, đã làm tròn nghìn từ backend). */
export function Money({
  amount,
  className,
  emphasis = false,
}: {
  amount: number | null | undefined;
  className?: string;
  emphasis?: boolean;
}) {
  if (amount === null || amount === undefined) return <span className={className}>—</span>;
  return (
    <span className={cn("tabular-nums", emphasis && "font-semibold text-ink", className)}>
      {formatVnd(amount)}
    </span>
  );
}
