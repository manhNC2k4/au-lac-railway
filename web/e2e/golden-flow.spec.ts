import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  const response = await request.post("/api/v1/demo/scenarios/golden_scenario_1/reset", {
    data: { reset_clock: true, apply_golden_gap: true },
  });
  expect(response.ok()).toBeTruthy();
});

test("hành khách đặt vé qua offer, hold và confirm", async ({ page }) => {
  await page.goto("/booking");
  await page.getByLabel("Tên hành khách").fill("Nguyễn Văn A");
  await page.getByRole("button", { name: "Tìm phương án" }).click();
  await expect(page).toHaveURL(/\/booking\/offer/);
  await expect(page.getByText("C01-S017", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Giữ phương án này" }).click();
  await expect(page).toHaveURL(/\/booking\/hold/);
  await page.getByRole("button", { name: "Xác nhận đặt vé" }).click();
  await expect(page.getByRole("heading", { name: "Đặt vé thành công" })).toBeVisible();
});

test("dashboard và seat matrix đọc được API", async ({ page }) => {
  await page.goto("/admin/overview");
  await expect(page.getByText("Tỷ lệ lấp đầy", { exact: true })).toBeVisible();
  await page.goto("/admin/seat-matrix");
  await expect(page.getByRole("heading", { name: "Ma trận trạng thái ghế theo chặng" })).toBeVisible();
  await expect(page.getByText("C01-S017", { exact: true })).toBeVisible();
});
