"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Armchair, Ban, CheckCircle2, ChevronRight, CircleDollarSign, Info, Route, Users } from "lucide-react";
import { getApi, qk } from "@/api";
import { segmentLabel, useCurrentRun } from "@/lib/current-run";
import { formatDemoTime, formatNumber, formatPercent } from "@/lib/format";
import { Money } from "@/components/money";
import { ErrorState } from "@/components/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { TrainArt } from "@/components/train-art";

function loadColor(occ:number){if(occ>=.8)return{bar:"bg-danger",text:"text-danger"};if(occ>=.6)return{bar:"bg-warning",text:"text-warning"};return{bar:"bg-success",text:"text-success"}}

export default function OpsOverviewPage(){
 const api=getApi(); const {serviceRunId,stops,segments}=useCurrentRun(); const overview=useQuery({queryKey:qk.overview(serviceRunId),queryFn:()=>api.getOverview(serviceRunId)}); const analytics=useQuery({queryKey:qk.analytics(serviceRunId),queryFn:()=>api.getAnalytics(serviceRunId)});
 if(overview.isPending)return <PageSkeleton/>; if(overview.isError)return <ErrorState error={overview.error} onRetry={()=>overview.refetch()}/>; const data=overview.data; const loads=analytics.data?.segment_loads??[];
 const routeLabel=stops.length>1?`${stops[0].station_name} → ${stops[stops.length-1].station_name}`:"—";
 return <div className="space-y-4">
  <section className="relative min-h-[176px] overflow-hidden rounded-lg border border-line bg-[#dceeff] shadow-card"><div className="relative z-10 max-w-[760px] p-6"><span className="rounded-lg bg-primary px-3 py-1.5 text-sm font-bold text-white">{serviceRunId}</span><h1 className="mt-4 text-[25px] font-bold text-ink">{routeLabel}</h1><p className="mt-2 text-sm text-muted">Ngồi mềm điều hòa</p></div><TrainArt className="absolute -bottom-1 right-3 hidden w-[430px] md:block"/></section>
  <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5"><Kpi icon={<Users/>} label="Tỷ lệ lấp đầy" value={formatPercent(data.overall_occupancy)}/><Kpi icon={<CircleDollarSign/>} label="Tổng doanh thu" value={<Money amount={data.total_revenue_vnd} emphasis/>}/><Kpi icon={<Armchair/>} label="Ghế-km còn trống" value={formatNumber(data.empty_seat_km)}/><Kpi icon={<Route/>} label="Hành khách-km" value={formatNumber(data.passenger_km)}/><Kpi icon={<Ban/>} label="Tỷ lệ hết chỗ giả" value={formatPercent(data.false_sold_out_rate)}/></div>
  <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]"><Card><CardHeader title="Tải theo chặng"/><CardBody>{analytics.isPending?<p className="text-sm text-muted">Đang tải...</p>:analytics.isError?<ErrorState compact error={analytics.error} onRetry={()=>analytics.refetch()}/>:<><div className="relative mx-1 flex justify-between" aria-hidden>{stops.map(s=><span key={s.station_id} className="relative flex w-0 flex-col items-center"><span className="h-3 w-3 rounded-full border-2 border-primary bg-white"/><span className="mt-2 hidden whitespace-nowrap text-[11px] sm:block">{s.station_name}</span></span>)}</div><div className="mt-6 flex gap-1">{loads.map(x=>{const color=loadColor(x.occupancy);return <div key={x.segment_id} className="flex-1"><div className="h-3 rounded-full bg-line"><div className={cn("h-full rounded-full",color.bar)} style={{width:`${Math.min(100,x.occupancy*100)}%`}}/></div><p className={cn("mt-2 text-center text-xs font-semibold",color.text)}>{formatPercent(x.occupancy)}</p><p className="text-center text-[10px] text-muted">L{x.segment_id}</p></div>})}</div></>}</CardBody></Card>
  <Card><CardHeader title="Cảnh báo vận hành"/><CardBody className="space-y-2">{data.bottlenecks.map(x=><Alert key={`b${x.segment_id}`} danger icon={<AlertTriangle/>} text={`${segmentLabel(segments,x.segment_id)} · ${formatPercent(x.occupancy)}`}/>) }{data.underused.map(x=><Alert key={`u${x.segment_id}`} icon={<CheckCircle2/>} text={`${segmentLabel(segments,x.segment_id)} · ${formatPercent(x.occupancy)}`}/>) }{!data.bottlenecks.length&&!data.underused.length&&<p className="text-sm text-muted">Không có cảnh báo từ API.</p>}</CardBody></Card></div>
  <Card><CardHeader title="Quyết định gần đây"/><CardBody className="p-0"><div className="overflow-x-auto"><table className="w-full min-w-[620px] text-sm"><thead><tr className="border-b border-line bg-surface text-left text-muted"><th className="px-5 py-3">Mã quyết định</th><th className="px-3">Kết quả</th><th className="px-3">Giá cuối</th><th className="px-3">Thời gian</th><th/></tr></thead><tbody>{data.recent_decisions.map(r=><tr key={r.decision_id} className="border-b border-line"><td className="px-5 py-3 font-mono text-xs">{r.decision_id}</td><td className="px-3"><Badge tone={r.result==="ACCEPT"?"success":"danger"}>{r.result}</Badge></td><td className="px-3"><Money amount={r.final_price_vnd}/></td><td className="px-3 text-muted">{formatDemoTime(r.created_at)}</td><td className="px-5 text-right"><Link href={`/admin/decisions/${r.decision_id}`} className="inline-flex items-center gap-1 text-primary">Chi tiết<ChevronRight className="h-4 w-4"/></Link></td></tr>)}{!data.recent_decisions.length&&<tr><td colSpan={5} className="px-5 py-8 text-center text-muted">Chưa có quyết định nào.</td></tr>}</tbody></table></div></CardBody></Card>
 </div>;
}
function Kpi({icon,label,value}:{icon:React.ReactNode;label:string;value:React.ReactNode}){return <Card className="p-4"><div className="flex items-center gap-2 text-sm text-muted"><span className="text-primary">{icon}</span>{label}</div><div className="mt-2 text-[22px] font-bold text-ink">{value}</div></Card>}
function Alert({danger=false,icon,text}:{danger?:boolean;icon:React.ReactNode;text:string}){return <div className={cn("flex items-center gap-3 rounded-lg border p-3",danger?"border-danger/30 bg-danger-soft":"border-success/30 bg-success-soft")}><span className={danger?"text-danger":"text-success"}>{icon}</span><p className="flex-1 text-sm text-ink">{text}</p><Badge tone={danger?"danger":"success"}>{danger?"Nghẽn":"Còn chỗ"}</Badge></div>}
