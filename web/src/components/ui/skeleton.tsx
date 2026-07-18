import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-lg bg-line/70", className)} />;
}

/** Skeleton cho dashboard: hàng KPI + block lớn. */
export function PageSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Đang tải dữ liệu">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-64" />
      <Skeleton className="h-40" />
      <span className="sr-only">Đang tải…</span>
    </div>
  );
}
