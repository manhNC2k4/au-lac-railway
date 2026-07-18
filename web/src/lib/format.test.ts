import { describe, expect, it } from "vitest";
import { formatCountdown, formatNumber, formatPercent, formatVnd } from "./format";

describe("formatVnd", () => {
  it("nối dấu chấm ngàn kiểu Việt Nam", () => {
    expect(formatVnd(285000)).toBe("285.000 ₫");
    expect(formatVnd(45000000)).toBe("45.000.000 ₫");
    expect(formatVnd(0)).toBe("0 ₫");
    expect(formatVnd(1000)).toBe("1.000 ₫");
  });

  it("chịu được int64 lớn (bigint)", () => {
    expect(formatVnd(9007199254740993n)).toBe("9.007.199.254.740.993 ₫");
  });

  it("xử lý số âm", () => {
    expect(formatVnd(-45000)).toBe("-45.000 ₫");
  });
});

describe("formatPercent", () => {
  it("dùng dấu phẩy thập phân", () => {
    expect(formatPercent(0.393)).toBe("39,3%");
    expect(formatPercent(0.55, 0)).toBe("55%");
  });
});

describe("formatCountdown", () => {
  it("hiển thị mm:ss và không âm", () => {
    expect(formatCountdown(598)).toBe("09:58");
    expect(formatCountdown(0)).toBe("00:00");
    expect(formatCountdown(-5)).toBe("00:00");
  });
});

describe("formatNumber", () => {
  it("đếm số có dấu chấm ngàn, không đơn vị tiền", () => {
    expect(formatNumber(12000)).toBe("12.000");
  });
});
