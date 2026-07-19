"use client";

import { forwardRef, useEffect, useRef, useState, type ButtonHTMLAttributes } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Armchair, Ban, CheckCircle2, ChevronRight, CircleDollarSign, Info, Route, Users } from "lucide-react";
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
import { TrainArt } from "@/components/train-art";
import type { StopRecord, SegmentLoad } from "@/api";

function loadColor(occ:number){if(occ>=.8)return{bar:"bg-danger",text:"text-danger"};if(occ>=.6)return{bar:"bg-warning",text:"text-warning"};return{bar:"bg-success",text:"text-success"}}

export default function OpsOverviewPage(){
 const api=getApi(); const {serviceRunId,stops,segments}=useCurrentRun(); const overview=useQuery({queryKey:qk.overview(serviceRunId),queryFn:()=>api.getOverview(serviceRunId)}); const analytics=useQuery({queryKey:qk.analytics(serviceRunId),queryFn:()=>api.getAnalytics(serviceRunId)});
 if(overview.isPending)return <PageSkeleton/>; if(overview.isError)return <ErrorState error={overview.error} onRetry={()=>overview.refetch()}/>; const data=overview.data; const loads=analytics.data?.segment_loads??[]; const forecasts=analytics.data?.forecasts??[]; const allocations=analytics.data?.allocations??[];
 const routeLabel=stops.length>1?`${stops[0].station_name} → ${stops[stops.length-1].station_name}`:"—";
 return <div className="space-y-4">
  <section className="relative min-h-[176px] overflow-hidden rounded-lg border border-line bg-[#dceeff] shadow-card"><div className="relative z-10 max-w-[760px] p-6"><span className="rounded-lg bg-primary px-3 py-1.5 text-sm font-bold text-white">{serviceRunId}</span><h1 className="mt-4 text-[25px] font-bold text-ink">{routeLabel}</h1><p className="mt-2 text-sm text-muted">Ngồi mềm điều hòa</p></div><TrainArt className="absolute -bottom-1 right-3 hidden w-[430px] md:block"/></section>
  <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5"><Kpi icon={<Users/>} label="Tỷ lệ lấp đầy" value={formatPercent(data.overall_occupancy)}/><Kpi icon={<CircleDollarSign/>} label="Tổng doanh thu" value={<Money amount={data.total_revenue_vnd} emphasis/>}/><Kpi icon={<Armchair/>} label="Ghế-km còn trống" value={formatNumber(data.empty_seat_km)}/><Kpi icon={<Route/>} label="Hành khách-km" value={formatNumber(data.passenger_km)}/><Kpi icon={<Ban/>} label="Tỷ lệ hết chỗ giả" value={formatPercent(data.false_sold_out_rate)}/></div>
  <Card className="min-w-0"><CardHeader title="Tải theo chặng" subtitle="Chuỗi ga từ Bắc → Nam, cuộn xuống dòng khi hết bề ngang."/><CardBody className="min-w-0">{analytics.isPending?<p className="text-sm text-muted">Đang tải...</p>:analytics.isError?<ErrorState compact error={analytics.error} onRetry={()=>analytics.refetch()}/>:<RouteLoadMap stops={stops} loads={loads}/>}</CardBody></Card>
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

const ROUTE_NODE_PITCH=60; // px/node ước lượng (cột + khoảng cách) — dùng để tính số node vừa 1 hàng theo bề rộng khung thật

function chunk<T>(arr:T[],size:number):T[][]{const out:T[][]=[];for(let i=0;i<arr.length;i+=size)out.push(arr.slice(i,i+size));return out;}

/** Chuỗi cột ga theo tuyến Bắc→Nam, tự xuống hàng và đảo chiều (kiểu rắn bò / chữ C ngược) khi hết bề ngang khung. */
function RouteLoadMap({stops,loads}:{stops:StopRecord[];loads:SegmentLoad[]}){
 const containerRef=useRef<HTMLDivElement>(null);
 const [perRow,setPerRow]=useState(8);
 useEffect(()=>{
  const el=containerRef.current; if(!el)return;
  const measure=()=>setPerRow(Math.max(3,Math.floor(el.clientWidth/ROUTE_NODE_PITCH)));
  measure();
  const ro=new ResizeObserver(measure); ro.observe(el);
  return ()=>ro.disconnect();
 },[]);
 if(stops.length<2)return <p className="text-sm text-muted">Chưa có dữ liệu tuyến.</p>;
 const n=stops.length;
 const rows=chunk(stops.map((s,j)=>({s,j})),perRow);
 return <div ref={containerRef} className="w-full">
  {rows.map((row,ri)=>{
   const reversed=ri%2===1;
   return <div key={ri}>
    <div className={cn("flex items-end gap-3",reversed&&"flex-row-reverse")}>
     {row.map(({s,j})=>{
      const segId=j<n-1?j+1:j; const load=byId(loads,segId); const color=load?loadColor(load.occupancy):null;
      const pct=load?Math.round(load.occupancy*100):null;
      return <div key={s.station_id} className="flex w-12 shrink-0 flex-col items-center gap-1">
       <span className={cn("text-[10px] font-semibold tabular-nums",color?color.text:"text-muted")}>{pct!=null?`${pct}%`:"—"}</span>
       <div className="flex h-14 w-4 items-end overflow-hidden rounded-full bg-line/60">
        <div className={cn("w-full rounded-full",color?color.bar:"bg-primary")} style={{height:`${Math.max(pct??100,6)}%`}}/>
       </div>
       <span className="line-clamp-2 max-w-[48px] text-center text-[10px] leading-tight text-ink">{s.station_name}</span>
      </div>;
     })}
    </div>
    {ri<rows.length-1&&<RouteRowConnector side={reversed?"left":"right"}/>}
   </div>;
  })}
 </div>;
}
function RouteRowConnector({side}:{side:"left"|"right"}){
 return <div className={cn("flex",side==="right"?"justify-end pr-4":"justify-start pl-4")}>
  <div className={cn("h-8 w-8 border-primary/40",side==="right"?"rounded-br-3xl border-b-[3px] border-r-[3px]":"rounded-bl-3xl border-b-[3px] border-l-[3px]")}/>
 </div>;
}
