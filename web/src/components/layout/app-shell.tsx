"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  Grid3X3,
  TicketCheck,
  BarChart3,
  Menu,
  X,
  Bell,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  LineChart,
  BrainCircuit,
  SlidersHorizontal,
  Layers,
  ClipboardCheck,
} from "lucide-react";
import { getApi, qk } from "@/api";
import { cn } from "@/lib/utils";
import { CurrentRunProvider, useCurrentRun } from "@/lib/current-run";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { ScenarioControlDrawer } from "@/components/layout/scenario-control";
import { BrandLogo } from "@/components/brand-logo";

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  exact?: boolean;
  children?: { href: string; label: string }[];
}

const NAV: NavItem[] = [
  { href: "/admin/overview", label: "Tổng quan", icon: LayoutDashboard, exact: true },
  { href: "/admin/seat-matrix", label: "Ma trận Ghế × Chặng", icon: Grid3X3 },
  {
    href: "/admin/analytics",
    label: "Dự báo & Phân bổ",
    icon: LineChart,
    children: [
      { href: "/admin/analytics?tab=demand", label: "Dự báo nhu cầu" },
      { href: "/admin/analytics?tab=load", label: "Tải theo chặng" },
      { href: "/admin/analytics?tab=allocation", label: "Phân bổ chỗ" },
    ],
  },
  { href: "/admin/decisions", label: "Quyết định AI", icon: BrainCircuit },
  { href: "/admin/booking-requests", label: "Duyệt yêu cầu vé", icon: ClipboardCheck },
  { href: "/admin/backtest", label: "So sánh Backtest", icon: BarChart3 },
  { href: "/admin/booking-lab", label: "Booking Lab", icon: TicketCheck },
];

const BREADCRUMB: [string, string][] = [
  ["/admin/seat-matrix", "Ma trận trạng thái ghế theo chặng"],
  ["/admin/overview", "Tổng quan vận hành"],
  ["/admin/analytics", "Dự báo & Phân bổ"],
  ["/admin/booking-lab", "Booking Lab"],
  ["/admin/booking-requests", "Duyệt yêu cầu đặt vé"],
  ["/admin/backtest", "So sánh chiến lược"],
  ["/admin/decisions", "Chi tiết quyết định AI"],
];

export function Logo({ compact = false }: { compact?: boolean }) {
  return compact ? <BrandLogo compact className="w-12" /> : <BrandLogo className="w-[190px]" />;
}

function MatrixVersionChip() {
  const api = getApi();
  const { serviceRunId } = useCurrentRun();
  const seatmap = useQuery({
    queryKey: qk.seatmap(serviceRunId),
    queryFn: () => api.getSeatmap(serviceRunId),
    staleTime: 5_000,
  });
  return (
    <span className="hidden items-center gap-1.5 rounded-xl border border-primary/25 bg-primary-soft px-3 py-2 text-[13px] font-medium text-primary md:inline-flex">
      <Layers className="h-4 w-4" aria-hidden />
      Ma trận {seatmap.isPending ? "đang tải" : seatmap.data ? `v${seatmap.data.matrix_version}` : "không khả dụng"}
    </span>
  );
}

/** Chọn chuyến thật đang xem — thay badge "Chuyến đang vận hành" cứng theo golden run. */
function RunPicker() {
  const { serviceRunId, setServiceRunId, runs, runsLoading } = useCurrentRun();
  const current = runs.find((r) => r.service_run_id === serviceRunId);
  return (
    <div className="rounded-xl border border-line bg-white px-3.5 py-1.5 shadow-card">
      <label htmlFor="run-picker" className="block text-[11px] text-muted">
        Chuyến đang xem
      </label>
      <select
        id="run-picker"
        value={serviceRunId}
        onChange={(e) => setServiceRunId(e.target.value)}
        disabled={runsLoading || !runs.length}
        className="min-w-0 max-w-[220px] truncate bg-transparent text-[13.5px] font-semibold tabular-nums text-ink focus-visible:outline-none disabled:opacity-60"
      >
        {!runs.length && <option value={serviceRunId}>{serviceRunId}</option>}
        {runs.map((r) => (
          <option key={r.service_run_id} value={r.service_run_id}>
            {r.train_id} · {r.service_date}
          </option>
        ))}
      </select>
      {current && <p className="text-[11px] text-muted">Ngày chạy {current.service_date}</p>}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [forecastOpen, setForecastOpen] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isPublicPage =
    pathname === "/" ||
    pathname === "/login" ||
    pathname === "/register" ||
    pathname === "/booking" ||
    pathname.startsWith("/booking/");

  if (isPublicPage) return <TooltipProvider>{children}</TooltipProvider>;

  const crumb = BREADCRUMB.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? "Tổng quan vận hành";

  const navContent = (compact: boolean) => (
    <nav aria-label="Điều hướng chính" className="flex flex-col gap-1">
      {NAV.map((item) => {
        const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
        const Icon = item.icon;
        const link = (
          <Link
            href={item.children ? item.children[0].href : item.href}
            onClick={(e) => {
              if (item.children && !compact) {
                e.preventDefault();
                setForecastOpen((v) => !v);
              } else {
                setMobileOpen(false);
              }
            }}
            aria-current={active ? "page" : undefined}
            aria-expanded={item.children && !compact ? forecastOpen : undefined}
            className={cn(
              "flex min-h-[44px] items-center gap-3 rounded-xl px-3 text-[14.5px] font-medium transition-colors",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary",
              active ? "bg-primary text-white shadow-card" : "text-ink hover:bg-primary-soft",
              compact && "justify-center px-0",
            )}
          >
            <Icon className="h-5 w-5 shrink-0" aria-hidden />
            {!compact && <span className="flex-1">{item.label}</span>}
            {!compact && item.children && (
              <ChevronDown className={cn("h-4 w-4 transition-transform", forecastOpen && "rotate-180")} aria-hidden />
            )}
          </Link>
        );
        return (
          <div key={item.href}>
            {compact ? <Tooltip label={item.label}>{link}</Tooltip> : link}
            {!compact && item.children && forecastOpen && (
              <div className="ml-6 mt-1 flex flex-col gap-0.5 border-l border-line pl-3">
                {item.children.map((c) => (
                  <Link
                    key={c.href}
                    href={c.href}
                    onClick={() => setMobileOpen(false)}
                    className="rounded-lg px-3 py-2 text-[13.5px] text-muted hover:bg-primary-soft hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                  >
                    {c.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );

  return (
    <TooltipProvider>
      <CurrentRunProvider>
      <div className="min-h-screen bg-surface">
        {/* Sidebar desktop — card trắng bo góc nổi trên nền xanh nhạt */}
        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-line bg-white px-3 py-5 shadow-card lg:flex",
            collapsed ? "w-[76px]" : "w-[256px]",
          )}
        >
          <Link
            href="/admin/overview"
            className="flex min-h-[150px] items-start justify-center overflow-hidden px-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
          >
            <Logo compact={collapsed} />
          </Link>
          {!collapsed && <p className="-mt-6 mb-4 text-center text-[13px] text-muted">Tối ưu vận hành theo từng chặng</p>}
          <div className="mt-2 flex-1 overflow-y-auto">{navContent(collapsed)}</div>
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
            className={cn(
              "flex min-h-[44px] items-center gap-2 rounded-xl border border-line px-3 text-[14px] font-medium text-ink hover:bg-surface",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary",
              collapsed && "justify-center px-0",
            )}
          >
            {collapsed ? <ChevronsRight className="h-4 w-4" aria-hidden /> : <ChevronsLeft className="h-4 w-4" aria-hidden />}
            {!collapsed && "Thu gọn"}
          </button>
        </aside>

        {/* Top bar */}
        <header
          className={cn(
            "sticky top-0 z-20 flex min-h-[90px] flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-white/95 px-4 py-2 backdrop-blur",
            collapsed ? "lg:pl-[100px]" : "lg:pl-[288px]",
            "lg:pr-7",
          )}
        >
          <button
            type="button"
            className="rounded-lg p-2 text-ink hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary lg:hidden"
            aria-label={mobileOpen ? "Đóng menu" : "Mở menu"}
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((v) => !v)}
          >
            {mobileOpen ? <X className="h-5 w-5" aria-hidden /> : <Menu className="h-5 w-5" aria-hidden />}
          </button>

          <nav aria-label="Breadcrumb" className="hidden items-center gap-2 text-[14px] md:flex">
            <Link href="/admin/overview" className="text-muted hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
              Trang chủ
            </Link>
            <span className="text-muted/60" aria-hidden>/</span>
            <span className="font-semibold text-ink">{crumb}</span>
          </nav>

          <div className="ml-auto flex flex-wrap items-center gap-2.5">
            <RunPicker />
            <MatrixVersionChip />
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-primary px-4 text-[14px] font-semibold text-white shadow-card hover:bg-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              <SlidersHorizontal className="h-4 w-4" aria-hidden />
              Điều khiển kịch bản
            </button>
          </div>
        </header>

        {/* Sidebar mobile */}
        {mobileOpen && (
          <div className="fixed inset-0 z-30 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu điều hướng">
            <div className="absolute inset-0 bg-navy/40" onClick={() => setMobileOpen(false)} aria-hidden />
            <div className="absolute inset-y-0 left-0 w-72 overflow-y-auto bg-white px-4 py-5 shadow-xl">
              <div className="mb-5 px-1">
                <Logo />
              </div>
              {navContent(false)}
            </div>
          </div>
        )}

        <main className={cn("px-4 pb-8 pt-5 lg:pr-7", collapsed ? "lg:pl-[100px]" : "lg:pl-[288px]")}>
          <div className="mx-auto max-w-[1400px]">{children}</div>
        </main>

        <ScenarioControlDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      </div>
      </CurrentRunProvider>
    </TooltipProvider>
  );
}
