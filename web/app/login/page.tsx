"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Eye, EyeOff, LockKeyhole, UserRound } from "lucide-react";
import { AuthVisual } from "@/components/auth-visual";
import { BrandLogo } from "@/components/brand-logo";

export default function LoginPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    router.push("/admin/overview");
  };

  return (
    <main className="min-h-dvh bg-[#f3f8ff] p-2.5 sm:p-4 lg:h-dvh lg:min-h-[660px] lg:overflow-hidden">
      <div className="mx-auto grid min-h-[calc(100dvh-20px)] max-w-[1612px] overflow-hidden rounded-[22px] bg-[#dceeff] shadow-[0_16px_48px_rgba(16,42,86,0.12)] sm:min-h-[calc(100dvh-32px)] lg:h-[calc(100dvh-32px)] lg:min-h-[628px] lg:grid-cols-[3fr_2fr] lg:rounded-[24px]">
        <AuthVisual />

        <section className="flex items-center bg-[#eef6ff] p-3 sm:p-5 lg:h-full lg:bg-transparent lg:p-0">
          <div className="mx-auto flex w-full max-w-[560px] items-center rounded-[22px] bg-white px-6 py-8 shadow-[0_16px_40px_rgba(16,42,86,0.11)] sm:px-10 sm:py-10 lg:mx-[0_22px_0_0] lg:h-full lg:max-w-none lg:rounded-[22px] lg:px-10 lg:py-7 xl:mx-[0_26px_0_0] xl:px-14">
            <form onSubmit={submit} className="mx-auto w-full max-w-[440px]">
              <Link href="/" aria-label="Quay lại Trang chủ" className="mb-6 inline-flex lg:hidden">
                <BrandLogo className="w-[108px]" />
              </Link>

              <p className="text-[12px] font-bold uppercase tracking-[0.12em] text-primary">Cổng quản trị</p>
              <h1 className="mt-1 text-[32px] font-bold leading-tight tracking-[-0.025em] text-ink sm:text-[36px]">Đăng nhập</h1>
              <p className="mt-1.5 text-[14px] leading-5 text-muted sm:text-[15px]">Truy cập không gian vận hành Âu Lạc Railway.</p>

              <label className="mt-6 block text-[13.5px] font-semibold text-ink" htmlFor="identity">Tên đăng nhập hoặc email</label>
              <div className="mt-1.5 flex min-h-[48px] items-center rounded-[10px] border border-[#c9d5e6] bg-white px-3.5 transition focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
                <UserRound className="h-5 w-5 shrink-0 text-muted" aria-hidden />
                <input
                  id="identity"
                  name="identity"
                  autoComplete="username"
                  required
                  value={identity}
                  onChange={(event) => setIdentity(event.target.value)}
                  placeholder="Nhập tên đăng nhập hoặc email"
                  className="h-11 min-w-0 flex-1 bg-transparent px-3 text-[14px] text-ink outline-none placeholder:text-[#9aa7ba]"
                />
              </div>

              <label className="mt-4 block text-[13.5px] font-semibold text-ink" htmlFor="password">Mật khẩu</label>
              <div className="mt-1.5 flex min-h-[48px] items-center rounded-[10px] border border-[#c9d5e6] bg-white px-3.5 transition focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
                <LockKeyhole className="h-5 w-5 shrink-0 text-muted" aria-hidden />
                <input
                  id="password"
                  name="password"
                  autoComplete="current-password"
                  required
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Nhập mật khẩu"
                  className="h-11 min-w-0 flex-1 bg-transparent px-3 text-[14px] text-ink outline-none placeholder:text-[#9aa7ba]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted transition hover:bg-primary-soft hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                >
                  {showPassword ? <EyeOff className="h-5 w-5" aria-hidden /> : <Eye className="h-5 w-5" aria-hidden />}
                </button>
              </div>

              <label className="mt-4 flex cursor-pointer items-center gap-2.5 text-[13.5px] text-ink">
                <input type="checkbox" name="remember" className="h-[18px] w-[18px] rounded border-line accent-primary" />
                Ghi nhớ đăng nhập
              </label>

              <button type="submit" className="mt-5 min-h-[50px] w-full rounded-[10px] bg-primary text-[15px] font-semibold text-white shadow-[0_9px_20px_rgba(18,97,201,.24)] transition hover:-translate-y-0.5 hover:bg-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary active:translate-y-0">
                Đăng nhập
              </button>

              <div className="my-5 h-px bg-line" />
              <Link href="/" className="flex min-h-[48px] items-center justify-center gap-2.5 rounded-[10px] border border-primary/40 text-[14px] font-semibold text-primary transition hover:bg-primary-soft focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
                <ArrowLeft className="h-5 w-5" aria-hidden /> Quay lại Trang chủ
              </Link>
              <p className="mt-3 text-center text-[11.5px] leading-4 text-muted">Dành cho Admin và Revenue Manager của Âu Lạc Railway.</p>
            </form>
          </div>
        </section>
      </div>
    </main>
  );
}
