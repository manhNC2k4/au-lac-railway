import { segmentLabel, segmentStations } from "@/lib/constants";
import { Tooltip } from "@/components/ui/tooltip";

/** Nhãn chặng "L3 THO–VIN" kèm tooltip tên ga đầy đủ. */
export function SegmentLabel({ segmentId }: { segmentId: number }) {
  return (
    <Tooltip label={segmentStations(segmentId)}>
      <span className="inline-flex cursor-default items-center rounded-md bg-surface px-1.5 py-0.5 text-[13px] font-medium tabular-nums text-ink">
        {segmentLabel(segmentId)}
      </span>
    </Tooltip>
  );
}

/** Dải chặng inclusive: "L3–L4 · Thanh Hóa → Đồng Hới". */
export function SegmentRange({ from, to }: { from: number; to: number }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="font-semibold tabular-nums text-ink">
        {from === to ? `L${from}` : `L${from}–L${to}`}
      </span>
      <span className="text-sm text-muted">
        {segmentStations(from).split(" → ")[0]} → {segmentStations(to).split(" → ")[1]}
      </span>
    </span>
  );
}
