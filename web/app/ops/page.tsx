"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";
import Image from "next/image";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Armchair, ArrowRight, Ban, CheckCircle2, ChevronRight, CircleDollarSign, Info, Route, Users } from "lucide-react";
import { getApi, qk } from "@/api";
import { segmentLabel, useCurrentRun, type RunSegment } from "@/lib/current-run";
import { formatDemoTime, formatNumber, formatPercent } from "@/lib/format";
import { Money } from "@/components/money";
import { ErrorState } from "@/components/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogTrigger, DialogContent } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { StopRecord, SegmentLoad } from "@/api";

function loadColor(occ:number){
 if(occ>=.8)return{bar:"bg-danger",text:"text-danger",soft:"bg-danger-soft",border:"border-danger/25",label:"Gần đầy"};
 if(occ>=.6)return{bar:"bg-warning",text:"text-warning",soft:"bg-warning-soft",border:"border-warning/25",label:"Cần theo dõi"};
 return{bar:"bg-success",text:"text-success",soft:"bg-success-soft",border:"border-success/25",label:"Còn nhiều chỗ"};
}

export default function OpsOverviewPage(){
 const api=getApi(); const {serviceRunId,stops,segments}=useCurrentRun(); const overview=useQuery({queryKey:qk.overview(serviceRunId),queryFn:()=>api.getOverview(serviceRunId)}); const analytics=useQuery({queryKey:qk.analytics(serviceRunId),queryFn:()=>api.getAnalytics(serviceRunId)});
 if(overview.isPending)return <PageSkeleton/>; if(overview.isError)return <ErrorState error={overview.error} onRetry={()=>overview.refetch()}/>; const data=overview.data; const loads=analytics.data?.segment_loads??[]; const forecasts=analytics.data?.forecasts??[]; const allocations=analytics.data?.allocations??[];
 const routeLabel=stops.length>1?`${stops[0].station_name} → ${stops[stops.length-1].station_name}`:"—";
 return <div className="space-y-4">
  <section className="relative isolate min-h-[210px] overflow-hidden rounded-2xl border border-[#c7dcf3] bg-primary-soft shadow-[0_12px_30px_rgba(8,43,92,0.14)] sm:min-h-[226px]">
   <Image
    src="/images/booking-hero.png"
    alt="Tàu Âu Lạc Railway trên hành trình"
    fill
    priority
    sizes="(min-width: 1024px) 1400px, 100vw"
    className="object-cover object-[68%_54%] sm:object-[64%_54%]"
   />
   <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-[#f8fbff] via-[#f8fbff]/95 to-[#f8fbff]/5 sm:via-[#f8fbff]/90 sm:to-transparent"/>
   <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-navy/20 via-transparent to-white/10"/>
   <div className="relative flex min-h-[210px] items-center p-5 sm:min-h-[226px] sm:p-7 lg:px-8">
    <div className="relative z-10 min-w-0 max-w-[620px]">
     <div className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-white/90 px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.08em] text-primary shadow-sm">
      <span className="relative flex h-2 w-2">
       <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-40"/>
       <span className="relative inline-flex h-2 w-2 rounded-full bg-primary"/>
      </span>
      Chuyến đang theo dõi
     </div>
     <h1 className="mt-4 text-[27px] font-bold leading-tight text-ink drop-shadow-[0_1px_0_rgba(255,255,255,0.7)] sm:text-[32px]">{routeLabel}</h1>
     <div className="mt-4 flex flex-wrap gap-2 text-[12px]">
      <span className="rounded-lg border border-white bg-white/80 px-3 py-2 font-mono font-semibold text-ink shadow-sm">{serviceRunId}</span>
      <span className="rounded-lg border border-white bg-white/80 px-3 py-2 font-semibold text-muted shadow-sm">
       {stops.length > 1 ? `${stops.length} ga · ${segments.length} chặng` : "Đang đồng bộ lộ trình"}
      </span>
     </div>
    </div>
   </div>
  </section>
  <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5"><Kpi icon={<Users/>} label="Tỷ lệ lấp đầy" value={formatPercent(data.overall_occupancy)}/><Kpi icon={<CircleDollarSign/>} label="Tổng doanh thu" value={<Money amount={data.total_revenue_vnd} emphasis/>}/><Kpi icon={<Armchair/>} label="Ghế-km còn trống" value={formatNumber(data.empty_seat_km)}/><Kpi icon={<Route/>} label="Hành khách-km" value={formatNumber(data.passenger_km)}/><Kpi icon={<Ban/>} label="Tỷ lệ hết chỗ giả" value={formatPercent(data.false_sold_out_rate)}/></div>
  <Card className="min-w-0 overflow-hidden"><CardHeader title="Tải theo từng chặng" subtitle="Mỗi thẻ thể hiện mức sử dụng ghế giữa hai ga liên tiếp. Đọc theo thứ tự từ trái sang phải, xuống dòng." className="bg-gradient-to-r from-white to-primary-soft/40"/><CardBody className="min-w-0 p-4 sm:p-5">{analytics.isPending?<p className="rounded-xl bg-surface p-5 text-sm text-muted">Đang tải dữ liệu hành trình...</p>:analytics.isError?<ErrorState compact error={analytics.error} onRetry={()=>analytics.refetch()}/>:<RouteLoadMap stops={stops} loads={loads}/>}</CardBody></Card>
  <Card><CardHeader title="Cảnh báo vận hành" subtitle="Đoạn sắp hết chỗ hoặc còn ế khách. Bấm vào để xem số liệu chứng minh."/><CardBody className="grid gap-2 sm:grid-cols-2">{data.bottlenecks.map(x=>{const load=byId(loads,x.segment_id),forecast=byId(forecasts,x.segment_id),bid=byId(allocations,x.segment_id),label=segmentLabel(segments,x.segment_id);return <SegmentProofDialog key={`b${x.segment_id}`} label={label} occupancy={x.occupancy} remaining={load?.remaining_capacity??0} forecastRemaining={forecast?.forecast_remaining} confidence={forecast?.confidence} bidVnd={bid?.bid_price_vnd} trigger={<AlertRow danger icon={<AlertTriangle/>} title={`Đoạn ${label} sắp hết chỗ`} detail={`Đã bán ${formatPercent(x.occupancy)} số ghế — khách đặt mới dễ bị từ chối.`} tag="Sắp đầy"/>}/>})}{data.underused.map(x=>{const load=byId(loads,x.segment_id),forecast=byId(forecasts,x.segment_id),bid=byId(allocations,x.segment_id),label=segmentLabel(segments,x.segment_id);return <SegmentProofDialog key={`u${x.segment_id}`} label={label} occupancy={x.occupancy} remaining={load?.remaining_capacity??0} forecastRemaining={forecast?.forecast_remaining} confidence={forecast?.confidence} bidVnd={bid?.bid_price_vnd} trigger={<AlertRow icon={<CheckCircle2/>} title={`Đoạn ${label} còn nhiều chỗ trống`} detail={`Mới bán ${formatPercent(x.occupancy)} số ghế — có thể cần ưu đãi giá để bán thêm.`} tag="Còn chỗ"/>}/>})}{!data.bottlenecks.length&&!data.underused.length&&<p className="text-sm text-muted">Không có cảnh báo từ API.</p>}</CardBody></Card>
  <Card><CardHeader title="Quyết định gần đây"/><CardBody className="p-0"><div className="overflow-x-auto"><table className="w-full min-w-[620px] text-sm"><thead><tr className="border-b border-line bg-surface text-left text-muted"><th className="px-5 py-3">Mã quyết định</th><th className="px-3">Kết quả</th><th className="px-3">Giá cuối</th><th className="px-3">Thời gian</th><th/></tr></thead><tbody>{data.recent_decisions.map(r=><tr key={r.decision_id} className="border-b border-line"><td className="px-5 py-3 font-mono text-xs">{r.decision_id}</td><td className="px-3"><Badge tone={r.result==="ACCEPT"?"success":"danger"}>{r.result}</Badge></td><td className="px-3"><Money amount={r.final_price_vnd}/></td><td className="px-3 text-muted">{formatDemoTime(r.created_at)}</td><td className="px-5 text-right"><Link href={`/admin/decisions/${r.decision_id}`} className="inline-flex items-center gap-1 text-primary">Chi tiết<ChevronRight className="h-4 w-4"/></Link></td></tr>)}{!data.recent_decisions.length&&<tr><td colSpan={5} className="px-5 py-8 text-center text-muted">Chưa có quyết định nào.</td></tr>}</tbody></table></div></CardBody></Card>
 </div>;
}
function Kpi({icon,label,value}:{icon:React.ReactNode;label:string;value:React.ReactNode}){return <Card className="p-4"><div className="flex items-center gap-2 text-sm text-muted"><span className="text-primary">{icon}</span>{label}</div><div className="mt-2 text-[22px] font-bold text-ink">{value}</div></Card>}
const AlertRow=forwardRef<HTMLButtonElement,ButtonHTMLAttributes<HTMLButtonElement>&{danger?:boolean;icon:React.ReactNode;title:string;detail:string;tag:string}>(function AlertRow({danger=false,icon,title,detail,tag,className,...rest},ref){return <button ref={ref} type="button" className={cn("flex w-full items-start gap-3 rounded-lg border p-3 text-left transition hover:brightness-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary",danger?"border-danger/30 bg-danger-soft":"border-success/30 bg-success-soft",className)} {...rest}><span className={cn("mt-0.5",danger?"text-danger":"text-success")}>{icon}</span><span className="flex-1"><span className="block text-sm font-medium text-ink">{title}</span><span className="mt-0.5 block text-xs text-muted">{detail}</span></span><Badge tone={danger?"danger":"success"} icon={<Info className="h-3 w-3"/>}>{tag}</Badge></button>});

function byId<T extends {segment_id:number}>(arr:T[],id:number):T|undefined{return arr.find(x=>x.segment_id===id)}

/** Đoạn tuyến từ Ga → Ga kèm chỉ số + dự báo + giá sàn, mở khi bấm vào một đoạn. */
function SegmentProofDialog({trigger,label,occupancy,remaining,forecastRemaining,confidence,bidVnd}:{trigger:React.ReactNode;label:string;occupancy:number;remaining:number;forecastRemaining?:number;confidence?:number|null;bidVnd?:number}){
 return <Dialog><DialogTrigger asChild>{trigger}</DialogTrigger><DialogContent title={`Đoạn ${label}`} description="Số liệu trực tiếp từ hệ thống — dùng để kiểm chứng cảnh báo bên cạnh.">
  <dl className="grid grid-cols-2 gap-3 text-sm">
   <ProofRow label="Ghế đã bán" value={formatPercent(occupancy)}/>
   <ProofRow label="Ghế còn trống" value={`${remaining} ghế`}/>
   <ProofRow label="Nhu cầu dự báo còn lại" value={forecastRemaining!=null?`~${Math.round(forecastRemaining)} khách`:"— (chưa có dự báo)"}/>
   <ProofRow label="Độ tin cậy dự báo" value={confidence!=null?formatPercent(confidence):"—"}/>
   <ProofRow label="Giá sàn tối thiểu (bid)" value={<Money amount={bidVnd}/>}/>
  </dl>
 </DialogContent></Dialog>;
}
function ProofRow({label,value}:{label:string;value:React.ReactNode}){return <div className="rounded-lg bg-surface p-3"><dt className="text-xs text-muted">{label}</dt><dd className="mt-1 font-semibold text-ink">{value}</dd></div>}

/** Mỗi thẻ là một chặng Ga đi → Ga đến, tránh nhầm tải thuộc về một ga đơn lẻ. */
function RouteLoadMap({stops,loads}:{stops:StopRecord[];loads:SegmentLoad[]}){
 if(stops.length<2)return <p className="rounded-xl bg-surface p-5 text-sm text-muted">Chưa có dữ liệu tuyến.</p>;
 const segments=stops.slice(0,-1).map((from,index)=>({
  segmentId:index+1,
  from,
  to:stops[index+1],
  load:byId(loads,index+1),
 }));
 const known=segments.flatMap(segment=>segment.load?[segment.load]:[]);
 const average=known.length?known.reduce((sum,load)=>sum+load.occupancy,0)/known.length:null;
 const busiest=known.reduce<SegmentLoad|undefined>((current,load)=>!current||load.occupancy>current.occupancy?load:current,undefined);
 const busiestSegment=busiest?segments.find(segment=>segment.segmentId===busiest.segment_id):undefined;
 return <div className="space-y-4">
  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface/70 px-4 py-3">
   <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
    <span className="text-muted">Tải trung bình <strong className="ml-1 text-ink">{average==null?"—":formatPercent(average)}</strong></span>
    <span className="text-muted">Chặng đông nhất <strong className="ml-1 text-ink">{busiestSegment?`${busiestSegment.from.station_name} → ${busiestSegment.to.station_name}`:"—"}</strong></span>
   </div>
   <div className="flex flex-wrap gap-3 text-[11px] text-muted" aria-label="Chú thích mức tải">
    <LoadLegend color="bg-success" label="Dưới 60%"/>
    <LoadLegend color="bg-warning" label="60–79%"/>
    <LoadLegend color="bg-danger" label="Từ 80%"/>
   </div>
  </div>
  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
   {segments.map(({segmentId,from,to,load})=>{
    const pct=load?Math.round(load.occupancy*100):null;
    const tone=load?loadColor(load.occupancy):null;
    return <article key={segmentId} className={cn("rounded-xl border bg-white p-4 transition hover:-translate-y-0.5 hover:shadow-md",tone?.border??"border-line")}>
     <div className="flex items-center justify-between gap-3">
      <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-muted">Chặng {String(segmentId).padStart(2,"0")}</span>
      <span className={cn("rounded-full px-2.5 py-1 text-[11px] font-semibold",tone?`${tone.soft} ${tone.text}`:"bg-surface text-muted")}>{tone?.label??"Chưa có dữ liệu"}</span>
     </div>
     <div className="mt-3 flex min-w-0 items-center gap-2 text-[15px] font-semibold text-ink">
      <span className="min-w-0 truncate" title={from.station_name}>{from.station_name}</span>
      <ArrowRight className="h-4 w-4 shrink-0 text-primary" aria-hidden/>
      <span className="min-w-0 truncate" title={to.station_name}>{to.station_name}</span>
     </div>
     <div className="mt-4 flex items-center gap-3">
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-line">
       <div className={cn("h-full rounded-full transition-[width] duration-500",tone?.bar??"bg-line")} style={{width:`${Math.min(100,Math.max(0,pct??0))}%`}}/>
      </div>
      <strong className={cn("w-11 text-right text-sm tabular-nums",tone?.text??"text-muted")}>{pct==null?"—":`${pct}%`}</strong>
     </div>
     <div className="mt-3 flex items-center justify-between border-t border-line/80 pt-3 text-xs text-muted">
      <span className="inline-flex items-center gap-1.5"><Armchair className="h-3.5 w-3.5" aria-hidden/>Ghế còn lại</span>
      <strong className="text-[13px] tabular-nums text-ink">{load?`${formatNumber(load.remaining_capacity)} ghế`:"—"}</strong>
     </div>
    </article>;
   })}
  </div>
 </div>;
}

function LoadLegend({color,label}:{color:string;label:string}){
 return <span className="inline-flex items-center gap-1.5"><span className={cn("h-2 w-2 rounded-full",color)}/>{label}</span>;
}
