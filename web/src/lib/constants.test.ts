import { describe, expect, it } from "vitest";
import { seatDisplayName } from "./constants";

describe("seatDisplayName", () => {
  it("maps zero-based seated indexes to coach and local seat numbers", () => {
    expect(seatDisplayName("NGOI_MEM_DH:0000", "NGOI_MEM_DH")).toBe("Toa 1 · Ghế 1");
    expect(seatDisplayName("NGOI_MEM_DH:0055", "NGOI_MEM_DH")).toBe("Toa 1 · Ghế 56");
    expect(seatDisplayName("NGOI_MEM_DH:0056", "NGOI_MEM_DH")).toBe("Toa 2 · Ghế 1");
  });

  it("maps sleeper indexes to the derived coach layout", () => {
    expect(seatDisplayName("NAM_K6:0081", "NAM_K6")).toBe("Toa 5 · Giường 40");
    expect(seatDisplayName("NAM_K4:0028", "NAM_K4")).toBe("Toa 7 · Giường 1");
  });

  it("keeps legacy seat labels readable", () => {
    expect(seatDisplayName("C01-S017", "NGOI_MEM_DH")).toBe("Ghế 17");
  });
});
