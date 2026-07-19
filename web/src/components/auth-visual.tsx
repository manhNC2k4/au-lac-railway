import Image from "next/image";
import { BrandLogo } from "@/components/brand-logo";

/** Nhận diện dành riêng cho cổng đăng nhập nhân viên quản lý. */
export function AuthVisual() {
  return (
    <aside className="relative hidden h-full min-h-0 overflow-hidden bg-[#dceeff] lg:block">
      <Image
        src="/images/booking-hero.png"
        alt="Đoàn tàu Âu Lạc trên hành trình qua miền núi"
        fill
        priority
        sizes="(max-width: 1280px) 60vw, 980px"
        className="object-cover object-[62%_center]"
      />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(231,243,255,.98)_0%,rgba(231,243,255,.90)_32%,rgba(231,243,255,.26)_62%,rgba(8,43,92,.08)_100%)]" />
      <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-white/35 to-transparent" />

      <div className="relative z-10 flex h-full flex-col px-10 py-7 xl:px-14 xl:py-9">
        <BrandLogo className="w-[126px] xl:w-[148px]" />
        <div className="mt-7 max-w-[590px] xl:mt-9">
          <h2 className="text-[36px] font-bold leading-[1.1] tracking-[-0.035em] text-ink xl:text-[44px]">
            Kết nối hành trình –<br />Tối ưu vận hành
          </h2>
          <p className="mt-4 max-w-[520px] text-[15px] leading-6 text-[#42526b] xl:text-[17px] xl:leading-7">
            Một nền tảng thống nhất cho trải nghiệm đặt vé và quản lý doanh thu theo từng chặng.
          </p>
        </div>
      </div>
    </aside>
  );
}
