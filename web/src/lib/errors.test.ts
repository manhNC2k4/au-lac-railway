import { describe, expect, it } from "vitest";
import { ApiError, ERROR_DISPLAY, errorDisplay, toApiError, type ApiErrorCode } from "./errors";

const ALL_CODES: ApiErrorCode[] = [
  "NO_SAME_SEAT_OPTION",
  "SOLD_OUT_TRUE",
  "ALLOCATION_REJECTED",
  "STALE_SNAPSHOT",
  "SEAT_CONFLICT",
  "OFFER_EXPIRED",
  "HOLD_EXPIRED",
  "POLICY_UNAVAILABLE",
  "NETWORK_ERROR",
  "UNKNOWN",
];

describe("bảng lỗi tiếng Việt", () => {
  it("mọi mã lỗi đều có tiêu đề, mô tả và hành động tiếp theo", () => {
    for (const code of ALL_CODES) {
      const d = ERROR_DISPLAY[code];
      expect(d.title.length, code).toBeGreaterThan(0);
      expect(d.description.length, code).toBeGreaterThan(0);
      expect(d.actionLabel.length, code).toBeGreaterThan(0);
      expect(d.actionKind, code).toBeTruthy();
    }
  });

  it("errorDisplay đọc đúng mã từ ApiError", () => {
    const err = new ApiError("SEAT_CONFLICT", "conflict", 409);
    expect(errorDisplay(err).title).toBe("Chỗ vừa được người khác giữ");
  });

  it("toApiError coi TypeError của fetch là lỗi mạng", () => {
    expect(toApiError(new TypeError("Failed to fetch")).code).toBe("NETWORK_ERROR");
  });

  it("lỗi lạ rơi về UNKNOWN", () => {
    expect(toApiError("boom").code).toBe("UNKNOWN");
  });
});
