/**
 * Tiền là int64 đồng (không float). Hiển thị dạng "285.000 ₫".
 * Tự nối dấu chấm ngàn để kết quả ổn định giữa mọi môi trường ICU.
 */
export function formatVnd(amount: number | bigint): string {
  const n = typeof amount === "bigint" ? amount : BigInt(Math.trunc(amount));
  const negative = n < 0n;
  const digits = (negative ? -n : n).toString();
  const parts: string[] = [];
  for (let i = digits.length; i > 0; i -= 3) {
    parts.unshift(digits.slice(Math.max(0, i - 3), i));
  }
  return `${negative ? "-" : ""}${parts.join(".")} ₫`;
}

/** "2026-06-15T09:00:00Z" → "09:00 · 15/06/2026" (giờ UTC — đồng hồ demo của kịch bản) */
export function formatDemoTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} · ${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`;
}

/** 0.393 → "39,3%" */
export function formatPercent(ratio: number, fractionDigits = 1): string {
  return `${(ratio * 100).toFixed(fractionDigits).replace(".", ",")}%`;
}

/** 12345 → "12.345" (đếm số, ghế-km, hành khách-km) */
export function formatNumber(n: number): string {
  return formatVnd(Math.trunc(n)).replace(" ₫", "");
}

/** Giây còn lại → "09:58" */
export function formatCountdown(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}
