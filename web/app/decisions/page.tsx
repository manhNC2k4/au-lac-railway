"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, ChevronRight } from "lucide-react";
import { getApi, qk } from "@/api";
import { useCurrentRun } from "@/lib/current-run";
import { formatDemoTime } from "@/lib/format";
import { ErrorState } from "@/components/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

/** Danh sách quyết định AI — cổng vào màn Chi tiết quyết định (S05). */
export default function DecisionsIndexPage() {
  const api = getApi();
  const { serviceRunId } = useCurrentRun();
  const overview = useQuery({
    queryKey: qk.overview(serviceRunId),
    queryFn: () => api.getOverview(serviceRunId),
  });

  if (overview.isPending) return <PageSkeleton />;
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />;

  const decisions = overview.data.recent_decisions ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[26px] font-bold text-ink">Quyết định AI</h1>
        <p className="mt-1 text-sm text-muted">
          Nhật ký quyết định mở bán của chuyến — mỗi quyết định có vết luật đầy đủ để giải thích và kiểm toán.
        </p>
      </div>

      <Card>
        <CardHeader title="Quyết định gần đây" subtitle={`Chuyến ${serviceRunId}`} />
        <CardBody className="p-0">
          {decisions.length === 0 ? (
            <div className="flex flex-col items-center gap-3 px-5 py-14 text-center">
              <BrainCircuit className="h-10 w-10 text-muted/50" aria-hidden />
              <p className="max-w-md text-sm text-muted">
                Chưa có quyết định nào. Tạo một đề nghị trong Booking Lab — mỗi đề nghị sinh một quyết định
                kèm vết luật xem được tại đây.
              </p>
              <Link href="/booking">
                <Button size="sm" variant="secondary">Mở Booking Lab</Button>
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b border-line bg-surface/70 text-left text-[13px] text-muted">
                    <th className="px-5 py-2.5 font-medium">Mã quyết định</th>
                    <th className="px-3 py-2.5 font-medium">Kết quả</th>
                    <th className="px-3 py-2.5 font-medium">Thời gian</th>
                    <th className="px-5 py-2.5 text-right font-medium" aria-label="Hành động" />
                  </tr>
                </thead>
                <tbody>
                  {decisions.map((r) => (
                    <tr key={r.decision_id} className="border-b border-line last:border-0">
                      <td className="px-5 py-3 font-mono text-[13px] text-ink">{r.decision_id}</td>
                      <td className="px-3 py-3">
                        <Badge tone={r.result === "ACCEPT" ? "success" : "danger"}>{r.result}</Badge>
                      </td>
                      <td className="px-3 py-3 tabular-nums text-muted">{formatDemoTime(r.created_at)}</td>
                      <td className="px-5 py-3 text-right">
                        <Link
                          href={`/decisions/${r.decision_id}`}
                          className="inline-flex min-h-[36px] items-center gap-1 rounded-lg border border-primary/30 px-3 text-[13px] font-medium text-primary hover:bg-primary-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                        >
                          Xem chi tiết <ChevronRight className="h-4 w-4" aria-hidden />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
