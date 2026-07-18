"use client";

import { FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, EyeOff, LockKeyhole, Mail, UserRound } from "lucide-react";
import { AuthVisual } from "@/components/auth-visual";

export default function RegisterPage() {
  const router = useRouter();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    router.push("/booking");
  };

  return (
    <main className="min-h-dvh bg-[#f4f8fe] p-4 md:p-[30px]">
      <div className="mx-auto grid min-h-[calc(100dvh-60px)] max-w-[1612px] overflow-hidden rounded-[28px] bg-[#dceeff] shadow-[0_12px_36px_rgba(16,42,86,0.10)] lg:grid-cols-[3fr_2fr]">
        <AuthVisual mode="register" />
        <section className="m-4 flex items-center rounded-[26px] bg-white px-7 py-8 md:m-6 md:px-16 lg:m-[30px_38px_30px_0]">
          <form onSubmit={submit} className="mx-auto w-full max-w-[496px]">
            <h1 className="text-[40px] font-bold leading-tight text-ink">Tạo tài khoản</h1>
            <p className="mt-2 text-[16px] text-muted">Tạo tài khoản Âu Lạc Railway để bắt đầu đặt vé.</p>
            <AuthField id="username" label="Tên đăng nhập" placeholder="Nhập tên đăng nhập" icon={<UserRound className="h-5 w-5" />} />
            <AuthField id="email" label="Email" type="email" placeholder="Nhập email của bạn" icon={<Mail className="h-5 w-5" />} />
            <AuthField id="password" label="Mật khẩu" type="password" placeholder="Nhập mật khẩu" icon={<LockKeyhole className="h-5 w-5" />} trailing />
            <AuthField id="confirm" label="Xác nhận mật khẩu" type="password" placeholder="Nhập lại mật khẩu" icon={<LockKeyhole className="h-5 w-5" />} trailing />
            <button type="submit" className="mt-7 min-h-[58px] w-full rounded-lg bg-primary text-[18px] font-semibold text-white hover:bg-primary-dark">Tạo tài khoản</button>
            <p className="mt-4 text-center text-[15px] text-muted">Đã có tài khoản? <Link href="/login" className="font-medium text-primary hover:underline">Đăng nhập</Link></p>
            <div className="my-6 h-px bg-line" />
            <Link href="/" className="flex min-h-[58px] items-center justify-center gap-3 rounded-lg border border-primary/50 text-[17px] font-medium text-primary hover:bg-primary-soft"><ArrowLeft className="h-5 w-5" /> Quay lại Trang chủ</Link>
          </form>
        </section>
      </div>
    </main>
  );
}

function AuthField({ id, label, type = "text", placeholder, icon, trailing = false }: { id: string; label: string; type?: string; placeholder: string; icon: React.ReactNode; trailing?: boolean }) {
  return (
    <div className="mt-5">
      <label htmlFor={id} className="block text-[15px] font-semibold text-ink">{label}</label>
      <div className="mt-2 flex min-h-[54px] items-center rounded-lg border border-[#c9d5e6] px-4 text-muted focus-within:ring-2 focus-within:ring-primary">
        {icon}
        <input id={id} required type={type} placeholder={placeholder} className="h-12 flex-1 bg-transparent px-3 text-[16px] text-ink outline-none placeholder:text-[#9aa7ba]" />
        {trailing && <EyeOff className="h-5 w-5" aria-hidden />}
      </div>
    </div>
  );
}
