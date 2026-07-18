"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, EyeOff, LockKeyhole, UserRound } from "lucide-react";
import { AuthVisual } from "@/components/auth-visual";

export default function LoginPage() {
  const router = useRouter();
  const [identity, setIdentity] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const admin = /admin|manager|quanly/i.test(identity);
    router.push(admin ? "/admin/overview" : "/booking");
  };

  return (
    <main className="min-h-dvh bg-[#f4f8fe] p-4 md:p-[30px]">
      <div className="mx-auto grid min-h-[calc(100dvh-60px)] max-w-[1612px] overflow-hidden rounded-[28px] bg-[#dceeff] shadow-[0_12px_36px_rgba(16,42,86,0.10)] lg:grid-cols-[3fr_2fr]">
        <AuthVisual mode="login" />
        <section className="m-4 flex items-center rounded-[26px] bg-white px-7 py-10 md:m-6 md:px-16 lg:m-[62px_38px_58px_0]">
          <form onSubmit={submit} className="mx-auto w-full max-w-[440px]">
            <h1 className="text-[42px] font-bold leading-tight text-ink">Đăng nhập</h1>
            <p className="mt-2 text-[17px] text-muted">Truy cập tài khoản Âu Lạc Railway của bạn.</p>

            <label className="mt-9 block text-[15px] font-semibold text-ink" htmlFor="identity">Tên đăng nhập hoặc email</label>
            <div className="mt-2 flex min-h-[54px] items-center rounded-lg border border-[#c9d5e6] px-4 focus-within:ring-2 focus-within:ring-primary">
              <UserRound className="h-5 w-5 text-muted" aria-hidden />
              <input id="identity" required value={identity} onChange={(e) => setIdentity(e.target.value)} placeholder="Nhập tên đăng nhập hoặc email" className="h-12 flex-1 bg-transparent px-3 text-[16px] text-ink outline-none placeholder:text-[#9aa7ba]" />
            </div>

            <label className="mt-7 block text-[15px] font-semibold text-ink" htmlFor="password">Mật khẩu</label>
            <div className="mt-2 flex min-h-[54px] items-center rounded-lg border border-[#c9d5e6] px-4 focus-within:ring-2 focus-within:ring-primary">
              <LockKeyhole className="h-5 w-5 text-muted" aria-hidden />
              <input id="password" required type="password" placeholder="Nhập mật khẩu" className="h-12 flex-1 bg-transparent px-3 text-[16px] text-ink outline-none placeholder:text-[#9aa7ba]" />
              <EyeOff className="h-5 w-5 text-muted" aria-hidden />
            </div>

            <label className="mt-6 flex cursor-pointer items-center gap-3 text-[15px] text-ink">
              <input type="checkbox" className="h-5 w-5 rounded border-line accent-primary" />
              Ghi nhớ đăng nhập
            </label>

            <button type="submit" className="mt-7 min-h-[58px] w-full rounded-lg bg-primary text-[18px] font-semibold text-white shadow-card transition-colors hover:bg-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary">Đăng nhập</button>
            <p className="mt-5 text-center text-[15px] text-muted">Chưa có tài khoản? <Link href="/register" className="font-medium text-primary hover:underline">Đăng ký</Link></p>
            <div className="my-7 h-px bg-line" />
            <Link href="/" className="flex min-h-[58px] items-center justify-center gap-3 rounded-lg border border-primary/50 text-[17px] font-medium text-primary hover:bg-primary-soft">
              <ArrowLeft className="h-5 w-5" aria-hidden /> Quay lại Trang chủ
            </Link>
            <p className="mt-4 text-center text-[12px] text-muted">Dùng tên chứa “admin” để vào giao diện quản lý.</p>
          </form>
        </section>
      </div>
    </main>
  );
}
