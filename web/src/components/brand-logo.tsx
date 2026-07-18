import { cn } from "@/lib/utils";

export function BrandLogo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5 text-[#082b5c]", className)} aria-label="Âu Lạc Railway">
      <svg viewBox="0 0 52 52" className="h-auto w-[42%] max-w-[52px] shrink-0" role="img" aria-hidden>
        <circle cx="26" cy="26" r="24" fill="#082b5c" />
        <path d="M13 31h26l-4-14H17l-4 14Z" fill="#fff" />
        <path d="M18 17h16l-2-5H20l-2 5Z" fill="#e5484d" />
        <rect x="18" y="20" width="7" height="6" rx="2" fill="#79b9ee" />
        <rect x="27" y="20" width="7" height="6" rx="2" fill="#79b9ee" />
        <path d="m18 36-5 5m21-5 5 5M15 35h22" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
      </svg>
      {!compact && (
        <span className="min-w-0 leading-none">
          <strong className="block whitespace-nowrap text-[clamp(14px,1.5vw,24px)] font-bold">ÂU LẠC</strong>
          <span className="mt-1 block whitespace-nowrap text-[clamp(8px,.7vw,11px)] font-semibold text-[#e5484d]">RAILWAY</span>
        </span>
      )}
    </span>
  );
}
