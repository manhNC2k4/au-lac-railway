"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { formatCountdown } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Đếm ngược hạn offer/hold bằng SỐ đọc được (không chỉ màu).
 * Gọi onExpire đúng một lần khi hết hạn.
 */
export function Countdown({
  expiresAt,
  onExpire,
  className,
}: {
  expiresAt: string;
  onExpire?: () => void;
  className?: string;
}) {
  const [secondsLeft, setSecondsLeft] = useState(() =>
    Math.floor((Date.parse(expiresAt) - Date.now()) / 1000),
  );

  useEffect(() => {
    setSecondsLeft(Math.floor((Date.parse(expiresAt) - Date.now()) / 1000));
    const timer = setInterval(() => {
      setSecondsLeft((prev) => {
        const next = Math.floor((Date.parse(expiresAt) - Date.now()) / 1000);
        if (next <= 0 && prev > 0) onExpire?.();
        return next;
      });
    }, 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiresAt]);

  const expired = secondsLeft <= 0;
  const urgent = !expired && secondsLeft <= 60;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 tabular-nums",
        expired ? "text-danger" : urgent ? "text-warning" : "text-ink",
        className,
      )}
      aria-live="polite"
    >
      <Clock className="h-4 w-4" aria-hidden />
      {expired ? "Hết hạn" : `Còn ${formatCountdown(secondsLeft)}`}
    </span>
  );
}
