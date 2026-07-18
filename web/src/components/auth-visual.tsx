import { ShieldCheck, Sparkles } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { RailwayScene } from "@/components/railway-scene";

export function AuthVisual({ mode }: { mode: "login" | "register" }) {
  return (
    <aside className="relative hidden min-h-[720px] overflow-hidden bg-[#dceeff] lg:block">
      <RailwayScene className="absolute inset-0 h-full min-h-0" />
      <div className="relative z-10 flex h-full flex-col p-12">
        <BrandLogo className="w-[180px]" />
        <div className="mt-16 max-w-[530px]">
          <p className="inline-flex items-center gap-2 rounded-full bg-white/90 px-4 py-2 text-sm font-semibold text-primary">
            {mode === "login" ? <ShieldCheck className="h-4 w-4" aria-hidden /> : <Sparkles className="h-4 w-4" aria-hidden />}
            {mode === "login" ? "Không gian làm việc bảo mật" : "Một tài khoản cho mọi hành trình"}
          </p>
          <h2 className="mt-5 text-[42px] font-bold leading-tight text-ink">
            {mode === "login" ? "Chào mừng bạn trở lại" : "Bắt đầu hành trình cùng Âu Lạc"}
          </h2>
          <p className="mt-4 max-w-[470px] text-[17px] leading-7 text-[#42526b]">
            {mode === "login" ? "Đăng nhập để tiếp tục đặt vé hoặc theo dõi hoạt động vận hành." : "Lưu thông tin hành khách và quản lý các chuyến đi thuận tiện hơn."}
          </p>
        </div>
      </div>
    </aside>
  );
}
