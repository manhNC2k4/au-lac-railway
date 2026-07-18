import { Check, Clock, XCircle, CircleDot, RefreshCcw, Sparkles, ShieldAlert } from "lucide-react";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import type { ReactNode } from "react";

/**
 * Nhãn trạng thái nghiệp vụ — ngôn ngữ nhân viên, kèm icon (màu không là tín hiệu duy nhất).
 */
export type StatusKind =
  | "FREE"
  | "HELD"
  | "SOLD"
  | "REUSED_GAP"
  | "ACCEPT"
  | "REJECT"
  | "ACTIVE"
  | "CONFIRMED"
  | "EXPIRED"
  | "CANCELLED"
  | "CLAMPED"
  | "PASS"
  | "FAIL"
  | "OK"
  | "FAILED"
  | "COMPLETED"
  | "RUNNING";

const CONFIG: Record<StatusKind, { label: string; tone: BadgeTone; icon: ReactNode }> = {
  FREE: { label: "Còn trống", tone: "neutral", icon: <CircleDot className="h-3.5 w-3.5" aria-hidden /> },
  HELD: { label: "Đang giữ", tone: "warning", icon: <Clock className="h-3.5 w-3.5" aria-hidden /> },
  SOLD: { label: "Đã bán", tone: "info", icon: <Check className="h-3.5 w-3.5" aria-hidden /> },
  REUSED_GAP: { label: "Khoảng có thể tái sử dụng", tone: "success", icon: <RefreshCcw className="h-3.5 w-3.5" aria-hidden /> },
  ACCEPT: { label: "Chấp nhận mở bán", tone: "success", icon: <Check className="h-3.5 w-3.5" aria-hidden /> },
  REJECT: { label: "Từ chối", tone: "danger", icon: <XCircle className="h-3.5 w-3.5" aria-hidden /> },
  ACTIVE: { label: "Đang giữ chỗ", tone: "warning", icon: <Clock className="h-3.5 w-3.5" aria-hidden /> },
  CONFIRMED: { label: "Đã xác nhận", tone: "success", icon: <Check className="h-3.5 w-3.5" aria-hidden /> },
  EXPIRED: { label: "Hết hạn", tone: "danger", icon: <XCircle className="h-3.5 w-3.5" aria-hidden /> },
  CANCELLED: { label: "Đã hủy", tone: "neutral", icon: <XCircle className="h-3.5 w-3.5" aria-hidden /> },
  CLAMPED: { label: "Đã kẹp theo chính sách", tone: "warning", icon: <ShieldAlert className="h-3.5 w-3.5" aria-hidden /> },
  PASS: { label: "Đạt", tone: "success", icon: <Check className="h-3.5 w-3.5" aria-hidden /> },
  FAIL: { label: "Vi phạm", tone: "danger", icon: <XCircle className="h-3.5 w-3.5" aria-hidden /> },
  OK: { label: "Hoàn thành", tone: "success", icon: <Check className="h-3.5 w-3.5" aria-hidden /> },
  FAILED: { label: "Thất bại", tone: "danger", icon: <XCircle className="h-3.5 w-3.5" aria-hidden /> },
  COMPLETED: { label: "Hoàn thành", tone: "success", icon: <Check className="h-3.5 w-3.5" aria-hidden /> },
  RUNNING: { label: "Đang chạy", tone: "info", icon: <Sparkles className="h-3.5 w-3.5" aria-hidden /> },
};

export function StatusBadge({ status, label }: { status: StatusKind | string; label?: string }) {
  const cfg = CONFIG[status as StatusKind];
  if (!cfg) return <Badge tone="neutral">{label ?? status}</Badge>;
  return (
    <Badge tone={cfg.tone} icon={cfg.icon}>
      {label ?? cfg.label}
    </Badge>
  );
}
