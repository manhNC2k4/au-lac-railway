import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeftRight,
  ArrowRight,
  Armchair,
  BarChart3,
  BrainCircuit,
  CalendarDays,
  CheckCircle2,
  CircleDollarSign,
  FlaskConical,
  LayoutDashboard,
  LineChart,
  MonitorPlay,
  Route,
  ShieldCheck,
  TicketCheck,
  TrainFront,
  TrendingUp,
  UserRound,
  Users,
} from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";

const CAPABILITIES = [
  {
    title: "Ma trận Ghế × Chặng",
    description: "Theo dõi trạng thái từng ghế trên từng chặng hành trình.",
    icon: Armchair,
  },
  {
    title: "Dự báo nhu cầu",
    description: "Ước lượng nhu cầu theo cặp ga để hỗ trợ phân bổ chỗ.",
    icon: TrendingUp,
  },
  {
    title: "Quyết định AI",
    description: "Giải thích giá áp dụng, giá trị bảo vệ và quy tắc kiểm soát.",
    icon: BrainCircuit,
  },
  {
    title: "Booking Lab",
    description: "Kiểm chứng quyết định tối ưu qua luồng đặt vé trực quan.",
    icon: FlaskConical,
  },
] as const;

const SYSTEM_AREAS = [
  {
    title: "Passenger Booking Flow",
    description: "Luồng đặt vé mượt mà, rõ từng bước và thân thiện trên mọi thiết bị.",
    icon: TicketCheck,
    href: "/booking",
  },
  {
    title: "Dashboard Revenue Manager",
    description: "Theo dõi hiệu suất, tải theo chặng và chỉ số doanh thu theo thời gian thực.",
    icon: LayoutDashboard,
    href: "/login",
  },
  {
    title: "Mô phỏng & so sánh chiến lược",
    description: "So sánh kịch bản, đánh giá tác động và chọn chiến lược tối ưu.",
    icon: BarChart3,
    href: "/login",
  },
] as const;

const TEAM = [
  ["Nguyễn Công Mạnh", "API · Tích hợp hệ thống"],
  ["Phan Đức Anh", "Backend · Web Development"],
  ["Phạm Văn Lợi", "AI/ML · Backend · DevOps"],
  ["Lê Xuân Tiến Đạt", "Chiến lược · UI/UX"],
  ["Tiến Bùi", "AI/ML · Python"],
  ["Nguyễn Khánh Bảo Châu", "AI/ML · Nghiên cứu"],
] as const;

export default function LandingPage() {
  return (
    <main className="min-h-dvh overflow-x-hidden bg-white text-ink">
      <LandingHeader />

      <section className="relative isolate overflow-hidden border-b border-line bg-[#eef7ff]">
        <Image
          src="/images/booking-hero.png"
          alt="Đoàn tàu Âu Lạc chạy qua hồ và núi"
          fill
          priority
          sizes="100vw"
          className="-z-20 object-cover object-[68%_center]"
        />
        <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,#ffffff_0%,rgba(255,255,255,.97)_35%,rgba(245,250,255,.84)_58%,rgba(234,246,255,.18)_100%)]" />
        <div className="absolute inset-x-0 bottom-0 -z-10 h-44 bg-gradient-to-t from-white/95 to-transparent" />

        <div className="mx-auto grid min-h-[570px] max-w-[1480px] items-center gap-8 px-5 py-12 sm:px-8 lg:grid-cols-[.9fr_1.1fr] lg:px-10 lg:py-16 xl:gap-14">
          <div className="max-w-[650px]">
            <p className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-white/90 px-4 py-2 text-[13px] font-semibold text-primary shadow-card backdrop-blur">
              <ShieldCheck className="h-4 w-4" aria-hidden />
              Nền tảng tối ưu doanh thu đường sắt
            </p>
            <h1 className="mt-5 text-[36px] font-bold leading-[1.1] tracking-[-0.035em] text-ink sm:text-[44px] lg:text-[52px]">
              Tối ưu tồn kho ghế theo từng chặng với Âu Lạc Railway
            </h1>
            <p className="mt-5 max-w-[620px] text-[16px] leading-7 text-[#42526b] sm:text-[17px]">
              Hỗ trợ Revenue Manager theo dõi tải theo chặng, dự báo nhu cầu, điều phối ghế và kiểm chứng quyết định tối ưu qua một luồng booking thống nhất.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                href="/login"
                className="inline-flex min-h-[50px] items-center justify-center gap-2 rounded-[10px] bg-primary px-6 font-semibold text-white shadow-[0_10px_24px_rgba(18,97,201,.24)] transition hover:-translate-y-0.5 hover:bg-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                Đăng nhập quản lý <ArrowRight className="h-5 w-5" aria-hidden />
              </Link>
              <Link
                href="/booking"
                className="inline-flex min-h-[50px] items-center justify-center gap-2 rounded-[10px] border border-primary bg-white/90 px-6 font-semibold text-primary transition hover:-translate-y-0.5 hover:bg-primary-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                Xem màn hình đặt vé <MonitorPlay className="h-5 w-5" aria-hidden />
              </Link>
            </div>
          </div>

          <SystemPreview />
        </div>
      </section>

      <section id="giai-phap" className="mx-auto grid max-w-[1480px] gap-8 px-5 py-14 sm:px-8 lg:grid-cols-[.8fr_1.2fr] lg:px-10 lg:py-16">
        <div>
          <SectionHeading eyebrow="Năng lực cốt lõi" title="Những gì hệ thống làm được" />
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {CAPABILITIES.map(({ title, description, icon: Icon }) => (
              <article key={title} className="group rounded-2xl border border-[#dbe7f5] bg-white p-5 shadow-card transition hover:-translate-y-1 hover:border-primary/30 hover:shadow-[0_14px_30px_rgba(16,42,86,.10)]">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-soft text-primary transition group-hover:bg-primary group-hover:text-white">
                  <Icon className="h-5 w-5" aria-hidden />
                </span>
                <h3 className="mt-4 text-[16px] font-bold text-ink">{title}</h3>
                <p className="mt-1.5 text-[13.5px] leading-5 text-muted">{description}</p>
              </article>
            ))}
          </div>
        </div>

        <div id="san-pham">
          <SectionHeading eyebrow="Một nền tảng thống nhất" title="Đi đến đúng không gian làm việc" />
          <div className="mt-6 grid overflow-hidden rounded-2xl border border-[#dbe7f5] bg-white shadow-card md:grid-cols-3">
            {SYSTEM_AREAS.map(({ title, description, icon: Icon, href }, index) => (
              <Link
                key={title}
                href={href}
                className={`group flex min-h-[240px] flex-col items-center justify-center p-7 text-center transition hover:bg-primary-soft/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-inset focus-visible:outline-primary ${index ? "border-t border-line md:border-l md:border-t-0" : ""}`}
              >
                <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-soft text-primary transition group-hover:scale-105 group-hover:bg-primary group-hover:text-white">
                  <Icon className="h-7 w-7" aria-hidden />
                </span>
                <h3 className="mt-5 text-[16px] font-bold leading-6 text-ink">{title}</h3>
                <p className="mt-2 text-[13.5px] leading-5 text-muted">{description}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-primary">
                  Mở màn hình <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" aria-hidden />
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section id="ve-au-lac" className="border-y border-line bg-[#f6faff]">
        <div className="mx-auto grid max-w-[1480px] gap-10 px-5 py-14 sm:px-8 lg:grid-cols-[.58fr_1.42fr] lg:px-10 lg:py-16">
          <div>
            <SectionHeading eyebrow="Về Âu Lạc Railway" title="Tối ưu vận hành bằng dữ liệu có thể kiểm chứng" />
            <p className="mt-4 text-[14.5px] leading-6 text-[#52637a]">
              Dự án xây dựng nền tảng hỗ trợ quản lý tồn kho ghế theo từng chặng, giảm tình trạng hết chỗ giả và tối ưu doanh thu cho vận hành đường sắt hiện đại.
            </p>
            <div className="mt-6 grid gap-2 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
              <ValueChip icon={TrendingUp} label="Tối ưu doanh thu" tone="green" />
              <ValueChip icon={Armchair} label="Giảm ghế trống" tone="amber" />
              <ValueChip icon={ShieldCheck} label="Quyết định minh bạch" tone="blue" />
            </div>
          </div>

          <div id="doi-ngu">
            <SectionHeading eyebrow="Đội ngũ" title="6 thành viên cùng xây dựng sản phẩm" />
            <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {TEAM.map(([name, role], index) => (
                <article key={name} className="flex items-center gap-3 rounded-2xl border border-[#dbe7f5] bg-white p-4 shadow-card">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#dceaff] to-[#afc9ec] text-primary">
                    <UserRound className="h-6 w-6" aria-hidden />
                  </span>
                  <div className="min-w-0">
                    <h3 className="truncate text-[14px] font-bold text-ink">{name}</h3>
                    <p className="mt-0.5 text-[12px] leading-4 text-muted">{role}</p>
                  </div>
                  <span className="ml-auto self-start text-[11px] font-semibold tabular-nums text-primary/55">0{index + 1}</span>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1480px] px-5 py-10 sm:px-8 lg:px-10">
        <div className="relative overflow-hidden rounded-2xl border border-[#d3e3f5] bg-[linear-gradient(100deg,#f5faff_0%,#e6f2ff_100%)] px-6 py-7 sm:px-9 lg:flex lg:items-center lg:justify-between lg:gap-8">
          <TrainFront className="absolute -bottom-8 left-4 h-28 w-28 text-primary/10" aria-hidden />
          <div className="relative lg:pl-24">
            <h2 className="text-[22px] font-bold text-ink">Sẵn sàng khám phá nền tảng Âu Lạc Railway?</h2>
            <p className="mt-1.5 text-sm text-muted">Kết nối vận hành, dữ liệu và trải nghiệm booking trong một giao diện thống nhất.</p>
          </div>
          <Link href="/login" className="relative mt-5 inline-flex min-h-[48px] items-center gap-2 rounded-[10px] bg-primary px-6 font-semibold text-white shadow-card transition hover:bg-primary-dark lg:mt-0">
            Đăng nhập quản lý <ArrowRight className="h-5 w-5" aria-hidden />
          </Link>
        </div>
      </section>

      <footer className="border-t border-line bg-white">
        <div className="mx-auto flex max-w-[1480px] flex-col items-center gap-5 px-5 py-6 text-sm text-muted sm:px-8 md:flex-row lg:px-10">
          <Link href="/" aria-label="Trang chủ Âu Lạc Railway" className="flex items-center gap-3">
            <BrandLogo className="w-[72px]" />
            <span>Âu Lạc Railway</span>
          </Link>
          <nav className="flex flex-wrap justify-center gap-x-6 gap-y-2 md:ml-auto" aria-label="Điều hướng chân trang">
            <a href="#trang-chu" className="hover:text-primary">Trang chủ</a>
            <a href="#giai-phap" className="hover:text-primary">Giải pháp</a>
            <a href="#doi-ngu" className="hover:text-primary">Đội ngũ</a>
            <Link href="/booking" className="hover:text-primary">Đặt vé</Link>
          </nav>
          <p className="text-center text-xs md:ml-6">© 2026 Âu Lạc Railway.</p>
        </div>
      </footer>
    </main>
  );
}

function LandingHeader() {
  return (
    <header id="trang-chu" className="sticky top-0 z-50 border-b border-line bg-white/95 backdrop-blur-xl">
      <div className="relative mx-auto flex min-h-[74px] max-w-[1480px] items-center gap-7 px-5 sm:px-8 lg:px-10">
        <Link href="/" aria-label="Trang chủ Âu Lạc Railway" className="flex shrink-0 items-center">
          <BrandLogo className="w-[92px] sm:w-[108px]" />
        </Link>
        <nav className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-1 whitespace-nowrap text-[13.5px] font-semibold text-[#263b5c] lg:flex" aria-label="Điều hướng trang chủ">
          <a href="#trang-chu" className="rounded-lg px-3 py-2 text-primary hover:bg-primary-soft">Trang chủ</a>
          <a href="#giai-phap" className="rounded-lg px-3 py-2 hover:bg-primary-soft hover:text-primary">Giải pháp</a>
          <a href="#san-pham" className="rounded-lg px-3 py-2 hover:bg-primary-soft hover:text-primary">Sản phẩm</a>
          <a href="#doi-ngu" className="rounded-lg px-3 py-2 hover:bg-primary-soft hover:text-primary">Đội ngũ</a>
          <a href="#ve-au-lac" className="hidden rounded-lg px-3 py-2 hover:bg-primary-soft hover:text-primary xl:block">Về Âu Lạc Railway</a>
        </nav>
        <div className="ml-auto flex items-center gap-1.5 sm:gap-3">
          <Link href="/login" className="hidden min-h-[42px] items-center rounded-lg px-3.5 text-sm font-semibold text-primary hover:bg-primary-soft sm:inline-flex">Đăng nhập</Link>
          <Link href="/booking" className="inline-flex min-h-[42px] items-center rounded-[9px] bg-primary px-4 text-sm font-semibold text-white shadow-card transition hover:bg-primary-dark sm:px-5">Đặt vé</Link>
        </div>
      </div>
    </header>
  );
}

function SystemPreview() {
  return (
    <div className="relative mx-auto w-full max-w-[650px] self-center lg:translate-y-3">
      <div className="rounded-[20px] border border-white/90 bg-white/95 p-3.5 shadow-[0_24px_70px_rgba(16,42,86,.22)] ring-1 ring-[#dbe7f5] backdrop-blur-xl sm:p-4">
        <div className="flex items-center justify-between gap-4 px-1 pb-3">
          <div>
            <p className="text-[13px] font-bold text-ink">Tổng quan vận hành</p>
            <p className="text-[10.5px] text-muted">Bản xem trước · dữ liệu minh hoạ</p>
          </div>
          <span className="rounded-full bg-success-soft px-2.5 py-1 text-[10px] font-bold text-success">Hệ thống ổn định</span>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <MiniKpi label="Tải trung bình" value="72%" trend="+8,3%" icon={LineChart} />
          <MiniKpi label="Ghế đã bán" value="8.624" trend="+6,1%" icon={Armchair} />
          <MiniKpi label="Doanh thu dự kiến" value="2,18 tỷ" trend="+9,4%" icon={CircleDollarSign} />
          <MiniKpi label="Tuyến đang chạy" value="24" trend="Đang mở" icon={Route} />
        </div>

        <div className="mt-2 grid gap-2 md:grid-cols-[1.4fr_.86fr]">
          <div className="rounded-xl border border-line bg-white p-3.5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[11px] font-bold text-ink">Tải theo chặng</p>
                <p className="text-[9.5px] text-muted">Thực tế và dự báo</p>
              </div>
              <span className="rounded-md bg-primary-soft px-2 py-1 text-[9.5px] font-semibold text-primary">Chặng 3 · 74%</span>
            </div>
            <div className="relative mt-3 h-[132px] overflow-hidden rounded-lg bg-[linear-gradient(to_bottom,transparent_24%,#edf2f8_25%,transparent_26%,transparent_49%,#edf2f8_50%,transparent_51%,transparent_74%,#edf2f8_75%,transparent_76%)]">
              <svg viewBox="0 0 420 130" className="h-full w-full" aria-label="Biểu đồ tải minh hoạ" role="img">
                <defs>
                  <linearGradient id="landing-chart-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor="#1261C9" stopOpacity=".24" />
                    <stop offset="1" stopColor="#1261C9" stopOpacity=".02" />
                  </linearGradient>
                </defs>
                <path d="M22 105 L105 55 L190 82 L275 44 L396 91 L396 124 L22 124 Z" fill="url(#landing-chart-fill)" />
                <path d="M22 105 L105 55 L190 82 L275 44 L396 91" fill="none" stroke="#1261C9" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                {[ [22,105], [105,55], [190,82], [275,44], [396,91] ].map(([cx, cy]) => (
                  <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="5" fill="#fff" stroke="#1261C9" strokeWidth="3" />
                ))}
              </svg>
            </div>
            <div className="grid grid-cols-5 text-center text-[9px] font-medium text-muted">
              {[1, 2, 3, 4, 5].map((leg) => <span key={leg}>Chặng {leg}</span>)}
            </div>
          </div>

          <div className="rounded-xl border border-line bg-white p-3.5">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-bold text-ink">Booking preview</p>
              <TrainFront className="h-4 w-4 text-primary" aria-hidden />
            </div>
            <div className="mt-3 grid grid-cols-[1fr_28px_1fr] items-center gap-1.5">
              <PreviewField label="Từ ga" value="Hà Nội" />
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-soft text-primary"><ArrowLeftRight className="h-3.5 w-3.5" aria-hidden /></span>
              <PreviewField label="Đến ga" value="Đà Nẵng" />
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <PreviewField label="Ngày đi" value="05/06/2026" icon={CalendarDays} />
              <PreviewField label="Hành khách" value="1 khách" icon={Users} />
            </div>
            <Link href="/booking" className="mt-3 flex min-h-[36px] items-center justify-center gap-1.5 rounded-lg bg-primary px-3 text-[11px] font-bold text-white hover:bg-primary-dark">
              Đặt vé ngay <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
            <div className="mt-3 flex items-center gap-1.5 text-[9.5px] font-medium text-success">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> Phương án có thể kiểm chứng
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MiniKpi({ label, value, trend, icon: Icon }: { label: string; value: string; trend: string; icon: typeof LineChart }) {
  return (
    <div className="min-w-0 rounded-xl border border-line bg-white p-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-[9px] font-medium text-muted">{label}</span>
        <Icon className="h-3.5 w-3.5 shrink-0 text-primary/65" aria-hidden />
      </div>
      <div className="mt-1.5 flex flex-wrap items-end gap-x-2 gap-y-0.5">
        <strong className="text-[16px] leading-none text-ink">{value}</strong>
        <span className="text-[8.5px] font-bold text-success">{trend}</span>
      </div>
    </div>
  );
}

function PreviewField({ label, value, icon: Icon }: { label: string; value: string; icon?: typeof CalendarDays }) {
  return (
    <div className="min-w-0 rounded-lg border border-line bg-[#f9fbfe] px-2 py-1.5">
      <span className="block text-[8.5px] text-muted">{label}</span>
      <span className="mt-0.5 flex items-center gap-1 truncate text-[10px] font-bold text-ink">
        {Icon && <Icon className="h-3 w-3 shrink-0 text-primary" aria-hidden />}{value}
      </span>
    </div>
  );
}

function SectionHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div>
      <p className="text-[12px] font-bold uppercase tracking-[0.12em] text-primary">{eyebrow}</p>
      <h2 className="mt-1.5 text-[25px] font-bold leading-tight tracking-[-0.02em] text-ink sm:text-[29px]">{title}</h2>
    </div>
  );
}

function ValueChip({ icon: Icon, label, tone }: { icon: typeof TrendingUp; label: string; tone: "green" | "amber" | "blue" }) {
  const tones = {
    green: "bg-success-soft text-success",
    amber: "bg-warning-soft text-warning",
    blue: "bg-primary-soft text-primary",
  };
  return (
    <div className="flex items-center gap-2 rounded-xl border border-line bg-white p-3 text-[12px] font-bold text-ink shadow-card">
      <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tones[tone]}`}><Icon className="h-4 w-4" aria-hidden /></span>
      {label}
    </div>
  );
}
