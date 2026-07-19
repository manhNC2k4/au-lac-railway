import Image from "next/image";
import { cn } from "@/lib/utils";

/** Official brand asset shared by the passenger and operations interfaces. */
export function BrandLogo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span
      className={cn(
        "relative inline-block shrink-0 overflow-hidden",
        compact ? "aspect-square" : "aspect-[1.7/1]",
        className,
      )}
      role="img"
      aria-label="Âu Lạc Railway"
    >
      <Image
        src="/images/aulac-logo-transparent.png"
        alt=""
        fill
        sizes={compact ? "52px" : "190px"}
        className={cn(
          "select-none object-cover object-center",
          compact ? "scale-[1.45]" : "scale-[1.12]",
        )}
        quality={100}
        priority
      />
    </span>
  );
}
