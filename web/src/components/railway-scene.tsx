import { TrainArt } from "@/components/train-art";
import { cn } from "@/lib/utils";

export function RailwayScene({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <div
      className={cn(
        "relative isolate overflow-hidden bg-[#dceeff]",
        compact ? "min-h-[180px]" : "min-h-[320px]",
        className,
      )}
    >
      <svg viewBox="0 0 1200 420" className="absolute inset-0 h-full w-full" aria-hidden preserveAspectRatio="xMidYMid slice">
        <rect width="1200" height="420" fill="#dceeff" />
        <circle cx="1020" cy="76" r="38" fill="#fff" opacity=".78" />
        <path d="M0 270 190 104l156 150L510 82l220 194 174-144 296 168v120H0Z" fill="#bedaf4" />
        <path d="M0 310 224 170l180 132 202-155 180 151 180-104 234 138v88H0Z" fill="#99c5eb" opacity=".82" />
        <path d="M0 342c190-46 360-41 550 2 200 45 380 26 650-24v100H0Z" fill="#7bb8df" opacity=".58" />
        <path d="M0 368c255-50 489-8 714 2 180 8 329-10 486-38" fill="none" stroke="#082b5c" strokeWidth="5" />
        <path d="M0 390c255-50 489-8 714 2 180 8 329-10 486-38" fill="none" stroke="#5b789c" strokeWidth="4" />
      </svg>
      <TrainArt className={cn("absolute bottom-[8%] right-[2%] w-[72%] max-w-[760px] drop-shadow-xl", compact && "w-[60%]")} />
    </div>
  );
}
