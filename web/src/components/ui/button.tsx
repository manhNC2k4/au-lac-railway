import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "md" | "sm";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClass: Record<Variant, string> = {
  primary:
    "bg-primary text-white hover:bg-primary-dark focus-visible:outline-primary disabled:bg-primary/50",
  secondary:
    "border border-primary/40 bg-white text-primary hover:bg-primary-soft focus-visible:outline-primary disabled:text-primary/40",
  danger:
    "border border-danger/40 bg-white text-danger hover:bg-danger-soft focus-visible:outline-danger disabled:text-danger/40",
  ghost: "text-ink hover:bg-surface focus-visible:outline-primary disabled:text-muted",
};

const sizeClass: Record<Size, string> = {
  md: "min-h-[44px] px-4 text-[15px]",
  sm: "min-h-[36px] px-3 text-sm",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", size = "md", loading = false, disabled, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
        "disabled:cursor-not-allowed",
        variantClass[variant],
        sizeClass[size],
        className,
      )}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});
