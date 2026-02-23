import { test } from "@playwright/test";

test("mobile layout capture", async ({ page }, testInfo) => {
  await page.route("**/api/auth/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        auth_mode: "session",
        has_refresh_token: true,
        username: "user@example.com",
        auth_state: "ok",
        needs_relogin: false,
      }),
    });
  });
  await page.addInitScript(() => {
    localStorage.clear();
  });

  await page.setViewportSize({ width: 390, height: 844 });

  await page.route("**/api/bootstrap", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { display_name: "Wouter", dojo_cohort: "1100-1200" },
        tasks: [
          {
            id: "polgar-m2",
            name: "Polgar M2s",
            category: "Mates",
            counts: { "1100-1200": 500 },
            start_count: 306,
            progress_bar_suffix: "",
            scoreboard_display: "",
            number_of_cohorts: 1,
            sort_priority: "1",
            current_count: 436,
            target_count: 500,
          },
          {
            id: "classical",
            name: "Classical Games",
            category: "Play",
            counts: { "1100-1200": 180 },
            start_count: 0,
            progress_bar_suffix: "",
            scoreboard_display: "",
            number_of_cohorts: 1,
            sort_priority: "2",
            current_count: 61,
            target_count: 180,
          },
        ],
        progress_by_requirement_id: {},
        pinned_task_ids: ["polgar-m2", "classical"],
        available_cohorts: ["1100-1200"],
        default_filters: { cohort: "ALL" },
      }),
    });
  });

  await page.route("**/api/progress", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        submitted_payload: {
          cohort: "1100-1200",
          requirementId: "polgar-m2",
          previousCount: 436,
          newCount: 437,
          incrementalMinutesSpent: 5,
          date: "2026-02-19T20:00:00Z",
          notes: "",
        },
        upstream_response: { ok: true },
      }),
    });
  });

  await page.goto("/");
  await page.screenshot({ path: testInfo.outputPath("mobile-pinned.png"), fullPage: true });
  await page.getByRole("button", { name: "Settings" }).click();
  await page.screenshot({ path: testInfo.outputPath("mobile-settings.png"), fullPage: true });
});

