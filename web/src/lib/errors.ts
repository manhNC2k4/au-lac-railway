/**
 * Map error code API → thông điệp tiếng Việt + hành động tiếp theo.
 * Bảng dùng chung cho mọi màn hình (một bản duy nhất — DEV4 §H6).
 */
export type ApiErrorCode =
  | "NO_SAME_SEAT_OPTION"
  | "SOLD_OUT_TRUE"
  | "ALLOCATION_REJECTED"
  | "CONSENT_REQUIRED"
  | "STALE_SNAPSHOT"
  | "SEAT_CONFLICT"
  | "OFFER_EXPIRED"
  | "HOLD_EXPIRED"
  | "POLICY_UNAVAILABLE"
  | "RESOURCE_NOT_FOUND"
  | "FORBIDDEN"
  | "GUARDRAIL_VIOLATION"
  | "NETWORK_ERROR"
  | "UNKNOWN";

export type ErrorActionKind = "retry" | "new-offer" | "reload" | "back-to-overview";

export interface ErrorDisplay {
  title: string;
  description: string;
  /** Nhãn nút hành động chính */
  actionLabel: string;
  actionKind: ErrorActionKind;
}

export const ERROR_DISPLAY: Record<ApiErrorCode, ErrorDisplay> = {
  NO_SAME_SEAT_OPTION: {
    title: "Không tìm được chỗ liên tục cho hành trình này",
    description:
      "Hiện không có một ghế trống liên tục trên toàn bộ hành trình. Thử hành trình khác hoặc tải lại dữ liệu.",
    actionLabel: "Tạo yêu cầu khác",
    actionKind: "new-offer",
  },
  SOLD_OUT_TRUE: {
    title: "Đã hết chỗ thật",
    description: "Tất cả ghế trên ít nhất một chặng của hành trình đã bán hết.",
    actionLabel: "Quay về tổng quan",
    actionKind: "back-to-overview",
  },
  ALLOCATION_REJECTED: {
    title: "Từ chối theo quota / giá sàn cơ hội",
    description:
      "Giá vé không bù đủ chi phí cơ hội (bid price) của các chặng chiếm dụng. Hệ thống giữ chỗ cho hành trình giá trị hơn.",
    actionLabel: "Tạo yêu cầu khác",
    actionKind: "new-offer",
  },
  CONSENT_REQUIRED: {
    title: "Cần xác nhận phương án đổi ghế",
    description: "Phương án sử dụng nhiều ghế. Hành khách cần đồng ý rõ ràng trước khi giữ chỗ.",
    actionLabel: "Xem lại phương án",
    actionKind: "new-offer",
  },
  STALE_SNAPSHOT: {
    title: "Dữ liệu đã thay đổi",
    description: "Ma trận ghế đã có phiên bản mới trong lúc bạn thao tác. Tải lại để lấy trạng thái mới nhất.",
    actionLabel: "Tải lại",
    actionKind: "reload",
  },
  SEAT_CONFLICT: {
    title: "Chỗ vừa được người khác giữ",
    description: "Một yêu cầu khác đã giữ đúng chỗ này trước bạn. Tạo đề nghị mới để tìm phương án còn khả dụng.",
    actionLabel: "Tạo đề nghị mới",
    actionKind: "new-offer",
  },
  OFFER_EXPIRED: {
    title: "Đề nghị đã hết hạn",
    description: "Giá và phương án ghế chỉ được giữ nguyên trong thời gian hiệu lực. Tạo đề nghị mới để tiếp tục.",
    actionLabel: "Tạo đề nghị mới",
    actionKind: "new-offer",
  },
  HOLD_EXPIRED: {
    title: "Giữ chỗ đã hết hạn",
    description: "Thời gian giữ chỗ đã kết thúc, ghế được trả về trạng thái có thể bán. Chọn lại từ đầu.",
    actionLabel: "Chọn lại",
    actionKind: "new-offer",
  },
  POLICY_UNAVAILABLE: {
    title: "Chính sách giá chưa sẵn sàng",
    description:
      "Hệ thống không dùng giá mặc định khi thiếu chính sách (fail-closed). Thử lại sau ít phút hoặc báo vận hành.",
    actionLabel: "Thử lại",
    actionKind: "retry",
  },
  RESOURCE_NOT_FOUND: {
    title: "Không tìm thấy dữ liệu",
    description: "Tài nguyên không tồn tại hoặc đã được xóa.",
    actionLabel: "Quay về tổng quan",
    actionKind: "back-to-overview",
  },
  FORBIDDEN: {
    title: "Không có quyền thực hiện",
    description: "Tài khoản hiện tại không có vai trò phù hợp cho thao tác này.",
    actionLabel: "Quay về tổng quan",
    actionKind: "back-to-overview",
  },
  GUARDRAIL_VIOLATION: {
    title: "Giá nằm ngoài giới hạn cho phép",
    description: "Mức giá đề nghị không nằm trong dải chính sách đã duyệt.",
    actionLabel: "Thử lại",
    actionKind: "retry",
  },
  NETWORK_ERROR: {
    title: "Không kết nối được máy chủ",
    description: "Kiểm tra backend đã chạy và API_SERVER_URL đã trỏ đúng địa chỉ.",
    actionLabel: "Thử lại",
    actionKind: "retry",
  },
  UNKNOWN: {
    title: "Lỗi không xác định",
    description: "Đã có lỗi ngoài dự kiến. Thử lại hoặc quay về tổng quan.",
    actionLabel: "Thử lại",
    actionKind: "retry",
  },
};

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number;
  readonly details?: Record<string, unknown>;

  constructor(code: ApiErrorCode, message: string, status = 0, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  if (err instanceof TypeError) {
    return new ApiError("NETWORK_ERROR", err.message);
  }
  return new ApiError("UNKNOWN", err instanceof Error ? err.message : String(err));
}

export function errorDisplay(err: unknown): ErrorDisplay {
  const e = toApiError(err);
  return ERROR_DISPLAY[e.code] ?? ERROR_DISPLAY.UNKNOWN;
}
