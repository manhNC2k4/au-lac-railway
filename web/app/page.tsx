import Link from "next/link";
import { Armchair, ArrowRight, BarChart3, RefreshCcw, Tag } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { RailwayScene } from "@/components/railway-scene";

const LANDING_FEATURES = [
  { key: "seat", title: "Theo dõi ghế theo chặng", description: "Nhìn rõ trạng thái từng ghế trên từng đoạn của hành trình." },
  { key: "reuse", title: "Tận dụng khoảng ghế trống", description: "Đề xuất phương án phù hợp với dải chặng hành khách yêu cầu." },
  { key: "forecast", title: "Dự báo dễ theo dõi", description: "Tải, sức chứa và nhu cầu còn lại được trình bày theo từng đoạn." },
  { key: "price", title: "Giá có giải thích", description: "Giá cuối, bid-price và các luật áp dụng luôn có dấu vết kiểm tra." },
] as const;

const FEATURE_ICONS = {
  seat: Armchair,
  reuse: RefreshCcw,
  forecast: BarChart3,
  price: Tag,
} as const;

export default function LandingPage() {
  return (
    <main className="min-h-dvh overflow-x-hidden bg-white">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex min-h-[76px] max-w-[1440px] items-center gap-8 px-4 md:px-8">
          <Link href="/" aria-label="Trang chủ Âu Lạc Railway"><BrandLogo className="w-[120px] sm:w-[148px]" /></Link>
          <nav className="hidden items-center gap-7 text-sm font-medium text-ink md:flex" aria-label="Điều hướng trang chủ">
            <a href="#dat-ve" className="hover:text-primary">Đặt vé</a>
            <a href="#giai-phap" className="hover:text-primary">Giải pháp</a>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Link href="/login" className="inline-flex min-h-11 items-center whitespace-nowrap rounded-lg px-2.5 text-sm font-semibold text-primary hover:bg-primary-soft sm:px-4">Đăng nhập</Link>
            <Link href="/booking" className="inline-flex min-h-11 items-center whitespace-nowrap rounded-lg bg-primary px-3.5 text-sm font-semibold text-white hover:bg-primary-dark sm:px-5">Đặt vé</Link>
          </div>
        </div>
      </header>

      <section className="relative min-h-[610px] overflow-hidden bg-[#dceeff]">
        <RailwayScene className="absolute inset-0 h-full min-h-0" />
        <div className="relative z-10 mx-auto flex min-h-[610px] max-w-[1440px] items-start px-4 pb-28 pt-14 md:px-8 md:pt-20">
          <div className="max-w-[660px]">
            <p className="mb-4 inline-flex rounded-full border border-primary/20 bg-white/90 px-4 py-2 text-sm font-semibold text-primary">Nền tảng vận hành đường sắt thông minh</p>
            <h1 className="text-[42px] font-bold leading-[1.12] text-ink md:text-[58px]">Tối ưu từng chặng, khai thác tối đa từng chỗ</h1>
            <p className="mt-5 max-w-[590px] text-[17px] leading-7 text-[#42526b] md:text-[19px]">Tìm hành trình thuận tiện cho hành khách và hỗ trợ nhân viên quản lý ghế, nhu cầu, giá vé trên một giao diện rõ ràng.</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/booking" className="inline-flex min-h-12 items-center gap-2 rounded-lg bg-primary px-6 font-semibold text-white hover:bg-primary-dark">Bắt đầu đặt vé <ArrowRight className="h-5 w-5" aria-hidden /></Link>
              <Link href="/login" className="inline-flex min-h-12 items-center rounded-lg border border-primary bg-white/90 px-6 font-semibold text-primary hover:bg-primary-soft">Đăng nhập quản lý</Link>
            </div>
          </div>
        </div>
      </section>

      <section id="dat-ve" className="relative z-20 mx-auto -mt-20 max-w-[1280px] px-4 md:px-8">
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-line bg-white p-6 shadow-[0_18px_44px_rgba(16,42,86,.14)]">
          <div><h2 className="text-xl font-semibold text-ink">Tìm ghế đang khả dụng</h2><p className="mt-1 text-sm text-muted">Chọn ga đi, ga đến và thông tin hành khách ở bước tiếp theo.</p></div>
          <Link href="/booking" className="inline-flex min-h-[52px] items-center justify-center gap-2 rounded-lg bg-primary px-7 text-base font-semibold text-white hover:bg-primary-dark">Bắt đầu đặt vé <ArrowRight className="h-5 w-5" aria-hidden /></Link>
        </div>
      </section>

      <section id="giai-phap" className="mx-auto max-w-[1280px] px-4 py-20 md:px-8">
        <div className="mb-9 max-w-[660px]">
          <p className="text-sm font-semibold uppercase text-primary">Vận hành dễ hiểu</p>
          <h2 className="mt-2 text-[30px] font-bold text-ink md:text-[38px]">Thông tin quan trọng, trình bày đúng lúc</h2>
        </div>
        <div className="grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2 lg:grid-cols-4">
          {LANDING_FEATURES.map((feature) => {
            const Icon = FEATURE_ICONS[feature.key];
            return (
              <article key={feature.key} className="bg-white p-6">
                <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary-soft text-primary"><Icon className="h-5 w-5" aria-hidden /></span>
                <h3 className="mt-5 text-lg font-semibold text-ink">{feature.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{feature.description}</p>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}
