"use client";

import { AlertTriangle } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { errorDisplay, toApiError, type ErrorActionKind } from "@/lib/errors";

/**
 * Khối lỗi chuẩn: tiêu đề + mô tả tiếng Việt + MỘT hành động tiếp theo rõ ràng.
 * Mã kỹ thuật để ở dòng phụ (không chen vào nội dung chính).
 */
export function ErrorState({
  error,
  onRetry,
  onNewOffer,
  compact = false,
}: {
  error: unknown;
  /** Hành động "thử lại / tải lại" */
  onRetry?: () => void;
  /** Hành động "tạo đề nghị mới" (Booking Lab) */
  onNewOffer?: () => void;
  compact?: boolean;
}) {
  const router = useRouter();
  const apiErr = toApiError(error);
  const display = errorDisplay(error);

  const act = (kind: ErrorActionKind) => {
    switch (kind) {
      case "retry":
      case "reload":
        onRetry?.();
        break;
      case "new-offer":
        (onNewOffer ?? onRetry)?.();
        break;
      case "back-to-overview":
        router.push("/ops");
        break;
    }
  };

  return (
    <div
      role="alert"
      className={`rounded-2xl border border-danger/30 bg-danger-soft/60 ${compact ? "p-4" : "p-6"}`}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-ink">{display.title}</h3>
          <p className="mt-1 text-sm text-muted">{display.description}</p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button size="sm" variant="secondary" onClick={() => act(display.actionKind)}>
              {display.actionLabel}
            </Button>
            {display.actionKind !== "back-to-overview" && (
              <Button size="sm" variant="ghost" onClick={() => router.push("/ops")}>
                Quay về tổng quan
              </Button>
            )}
          </div>
          <p className="mt-3 text-xs text-muted">
            Mã tham chiếu: <code className="font-mono">{apiErr.code}</code>
            {apiErr.status ? ` · HTTP ${apiErr.status}` : ""}
          </p>
        </div>
      </div>
    </div>
  );
}
