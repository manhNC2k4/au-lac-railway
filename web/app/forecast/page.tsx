"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Armchair, Layers, TrendingUp } from "lucide-react";
import { getApi, qk } from "@/api";
import { GOLDEN, segmentStations } from "@/lib/constants";
import { formatNumber, formatPercent } from "@/lib/format";
import { Money } from "@/components/money";
import { ErrorState } from "@/components/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ForecastPage(){return <Suspense fallback={<PageSkeleton/>}><Content/></Suspense>}
function Content(){
 const api=getApi();const router=useRouter();const params=useSearchParams();const tab=params.get("tab")??"demand";const query=useQuery({queryKey:qk.analytics(GOLDEN.serviceRunId),queryFn:()=>api.getAnalytics(GOLDEN.serviceRunId)});
 if(query.isPending)return <PageSkeleton/>;if(query.isError)return <ErrorState error={query.error} onRetry={()=>query.refetch()}/>;const data=query.data;
 return <div className="space-y-4"><div><h1 className="text-[26px] font-bold text-ink">Dự báo nhu cầu &amp; Phân bổ chỗ</h1><p className="mt-1 text-sm text-muted">Dữ liệu backend theo từng chặng L1–L7 · phiên bản dự báo {data.forecast_version}</p></div><Tabs value={tab} onValueChange={v=>router.replace(`/admin/analytics?tab=${v}`)}><TabsList><TabsTrigger value="demand">Nhu cầu còn lại</TabsTrigger><TabsTrigger value="load">Tải theo chặng</TabsTrigger><TabsTrigger value="allocation">Bid-price</TabsTrigger></TabsList>
  <TabsContent value="demand" className="mt-4"><Card><CardHeader title="Dự báo nhu cầu còn lại" subtitle="forecast_remaining và confidence do API trả về"/><CardBody><Table headers={["Chặng","Nhu cầu còn lại","Độ tin cậy"]}>{data.forecasts.map(x=><tr key={x.segment_id} className="border-b border-line"><Cell value={`L${x.segment_id} · ${segmentStations(x.segment_id)}`}/><Cell value={formatNumber(x.forecast_remaining)} strong/><td className="px-4 py-3"><Badge tone={x.confidence>=.8?"success":x.confidence>=.6?"warning":"danger"}>{formatPercent(x.confidence)}</Badge></td></tr>)}</Table></CardBody></Card></TabsContent>
  <TabsContent value="load" className="mt-4"><div className="grid gap-3 md:grid-cols-2">{data.segment_loads.map(x=><Card key={x.segment_id}><CardBody className="p-4"><div className="flex justify-between"><strong className="text-ink">L{x.segment_id} · {segmentStations(x.segment_id)}</strong><span className="font-semibold text-primary">{formatPercent(x.occupancy)}</span></div><div className="mt-3 h-2.5 rounded-full bg-line"><div className="h-full rounded-full bg-primary" style={{width:`${Math.min(100,x.occupancy*100)}%`}}/></div><p className="mt-3 flex items-center gap-2 text-sm text-muted"><Armchair className="h-4 w-4"/>Còn {x.remaining_capacity} chỗ</p></CardBody></Card>)}</div></TabsContent>
  <TabsContent value="allocation" className="mt-4"><Card><CardHeader title="Giá trị bảo vệ chỗ" subtitle="Không tính fallback ở FE; cache miss được hiển thị đúng là 0"/><CardBody><Table headers={["Chặng","Bid-price"]}>{data.allocations.map(x=><tr key={x.segment_id} className="border-b border-line"><Cell value={`L${x.segment_id} · ${segmentStations(x.segment_id)}`}/><td className="px-4 py-3 font-semibold"><Money amount={x.bid_price_vnd}/></td></tr>)}</Table></CardBody></Card></TabsContent>
 </Tabs></div>;
}
function Table({headers,children}:{headers:string[];children:React.ReactNode}){return <div className="overflow-x-auto"><table className="w-full min-w-[520px] text-sm"><thead><tr className="border-b border-line bg-surface text-left text-muted">{headers.map(h=><th key={h} className="px-4 py-3 font-medium">{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>}
function Cell({value,strong=false}:{value:string;strong?:boolean}){return <td className={`px-4 py-3 ${strong?"font-semibold text-ink":"text-ink"}`}>{value}</td>}
