import { redirect } from "next/navigation";

// Trang "Đề xuất giá vé" đã gỡ: dynamic pricing áp dụng lúc bán (offer) hợp lý hơn
// đề xuất tĩnh theo chặng. Giữ route để URL cũ không 404 — chuyển thẳng về tổng quan.
export default function DecisionsPage() {
  redirect("/admin/overview");
}
