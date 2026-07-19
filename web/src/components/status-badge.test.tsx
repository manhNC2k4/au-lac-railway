import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./status-badge";
import { PriceBreakdown } from "./price-breakdown";

describe("StatusBadge", () => {
  it("dùng ngôn ngữ nhân viên cho trạng thái ghế", () => {
    render(<StatusBadge status="FREE" />);
    expect(screen.getByText("Còn trống")).toBeInTheDocument();
  });

  it("khoảng trống bán lại có nhãn riêng", () => {
    render(<StatusBadge status="REUSED_GAP" />);
    expect(screen.getByText("Khoảng có thể tái sử dụng")).toBeInTheDocument();
  });

  it("trạng thái lạ không vỡ — hiển thị nguyên văn", () => {
    render(<StatusBadge status="SOMETHING_NEW" />);
    expect(screen.getByText("SOMETHING_NEW")).toBeInTheDocument();
  });
});

describe("PriceBreakdown", () => {
  it("chỉ hiển thị giá thân thiện với hành khách", () => {
    render(
      <PriceBreakdown
        pricing={{
          gia_goc_vnd: 285000,
          gia_niem_yet_vnd: 314000,
          gia_cuoi_vnd: 330000,
          rules_fired: [],
          violations: [],
          clamped: true,
          csxh_doi_tuong: "KHONG",
          che_do_gia: "AI",
        }}
      />,
    );
    expect(screen.getByText("Giá cơ sở")).toBeInTheDocument();
    expect(screen.getByText("AI đề xuất")).toBeInTheDocument();
    expect(screen.getByText("Giá đã duyệt")).toBeInTheDocument();
    expect(screen.getByText("285.000 ₫")).toBeInTheDocument();
    expect(screen.getByText("314.000 ₫")).toBeInTheDocument();
    expect(screen.getByText("330.000 ₫")).toBeInTheDocument();
    expect(screen.queryByText("Giá niêm yết")).not.toBeInTheDocument();
    expect(screen.queryByText("Đã kẹp theo chính sách")).not.toBeInTheDocument();
  });
});
