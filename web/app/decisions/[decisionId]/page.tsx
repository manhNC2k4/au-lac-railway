"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { getApi, qk } from "@/api";
import { formatDemoTime } from "@/lib/format";
import { Money } from "@/components/money";
import { ErrorState } from "@/components/error-state";
import { PageSkeleton } from "@/components/ui/skeleton";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/status-badge";

export default function DecisionDetailPage({params}:{params:{decisionId:string}}){
 const api=getApi();const query=useQuery({queryKey:qk.decision(params.decisionId),queryFn:()=>api.getDecision(params.decisionId)});if(query.isPending)return <PageSkeleton/>;if(query.isError)return <ErrorState error={query.error} onRetry={()=>query.refetch()}/>;const d=query.data;const accept=d.action==="ACCEPT";const bids=Object.entries(d.bid_price_breakdown);
 return <div className="space-y-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-[26px] font-bold text-ink">Quyết định {d.decision_id}</h1><p className="mt-1 text-sm text-muted">{d.explanation_code} · {formatDemoTime(d.created_at)} · actor {d.actor}</p></div><Link href="/admin/overview" className="inline-flex items-center gap-2 rounded-lg border border-line px-4 py-2 text-primary"><ArrowLeft className="h-4 w-4"/>Tổng quan</Link></div>
 <div className={`rounded-lg border p-4 ${accept?"border-success/40 bg-success-soft":"border-danger/40 bg-danger-soft"}`}><div className="flex flex-wrap items-center gap-3"><StatusBadge status={d.action}/><p className="flex-1 text-sm text-ink">{d.audit_timeline.explanation}</p><code className="text-xs text-muted">{d.input_hash}</code></div></div>
 <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader title="Diễn biến giá"/><CardBody><div className="grid grid-cols-3 gap-3"><Price label="Giá cơ sở" value={d.base_fare}/><Price label="AI đề xuất" value={d.ai_suggested_price}/><Price label="Giá cuối" value={d.final_price} final/></div></CardBody></Card><Card><CardHeader title="Bid-price theo chặng" subtitle={<>Tổng <Money amount={d.bid_price_total} emphasis/></>}/><CardBody className="space-y-3">{bids.map(([segment,value])=><div key={segment} className="flex justify-between border-b border-line pb-2 text-sm"><span>L{segment}</span><Money amount={value}/></div>)}{!bids.length&&<p className="text-sm text-muted">Không có dữ liệu bid.</p>}</CardBody></Card></div>
 <Card><CardHeader title="Luật giá đã áp dụng"/><CardBody className="p-0"><table className="w-full text-sm"><thead><tr className="border-b border-line bg-surface text-left text-muted"><th className="px-5 py-3">Thứ tự</th><th>Mã luật</th><th className="px-5 text-right">Hệ số</th></tr></thead><tbody>{d.audit_timeline.rules_fired.map(r=><tr key={`${r.thu_tu}-${r.rule_id}`} className="border-b border-line"><td className="px-5 py-3">{r.thu_tu}</td><td className="font-mono text-xs">{r.rule_id}</td><td className="px-5 text-right">×{r.he_so}</td></tr>)}</tbody></table></CardBody></Card>
 <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader title="Ràng buộc & vi phạm"/><CardBody>{d.violations.length?<div className="space-y-2">{d.violations.map(v=><p key={v}><Badge tone="danger">Vi phạm</Badge> <span className="ml-2 text-sm">{v}</span></p>)}</div>:<p className="flex items-center gap-2 text-sm text-ink"><ShieldCheck className="h-5 w-5 text-success"/>Không có vi phạm.</p>}</CardBody></Card><Card><CardHeader title="Phiên bản dữ liệu"/><CardBody className="grid grid-cols-3 gap-3 text-center"><Version label="Ma trận" value={d.versions.matrix_version}/><Version label="Dự báo" value={d.versions.forecast_version}/><Version label="Chính sách" value={d.versions.policy_version}/></CardBody></Card></div></div>;
}
function Price({label,value,final=false}:{label:string;value:number;final?:boolean}){return <div className={`rounded-lg border p-3 ${final?"border-success bg-success-soft":"border-line"}`}><p className="text-xs text-muted">{label}</p><p className="mt-1 font-semibold"><Money amount={value}/></p></div>}
function Version({label,value}:{label:string;value:number}){return <div className="rounded-lg bg-surface p-3"><p className="text-xs text-muted">{label}</p><strong className="text-lg text-ink">v{value}</strong></div>}
