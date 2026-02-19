import { expect, test } from "@playwright/test";

test("smoke: task-specific profiles drive count/time tiles and submit", async ({ page }) => {
  let submittedPayload: Record<string, unknown> | null = null;

  await page.route("**/api/bootstrap", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          display_name: "Wouter",
          dojo_cohort: "1100-1200",
        },
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
            id: "study-time",
            name: "Study Mastering Time In Chess",
            category: "Study",
            counts: { "1100-1200": 30 },
            start_count: 0,
            progress_bar_suffix: "",
            scoreboard_display: "",
            number_of_cohorts: 1,
            sort_priority: "2",
            current_count: 4,
            target_count: 30,
          },
        ],
        progress_by_requirement_id: {},
        pinned_task_ids: ["polgar-m2"],
        available_cohorts: ["1100-1200"],
        default_filters: {
          cohort: "ALL",
        },
      }),
    });
  });

  await page.route("**/api/progress", async (route) => {
    const request = route.request();
    submittedPayload = JSON.parse(request.postData() ?? "{}");
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
        upstream_response: {
          ok: true,
        },
      }),
    });
  });

  await page.goto("/");

  await expect(page.getByTestId("pinned-task-polgar-m2")).toBeVisible();

  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByTestId("count-profile-polgar-m2").selectOption("count_polgar_next_30_absolute");
  await page.getByTestId("timer-profile-polgar-m2").selectOption("time_every_5_to_180");

  await page.getByRole("button", { name: "Pinned" }).click();

  await page.getByTestId("pinned-task-polgar-m2").click();
  await expect(page.getByTestId("count-tile-437")).toBeVisible();
  await page.getByTestId("count-tile-437").click();

  await expect(page.getByTestId("time-tile-5")).toBeVisible();
  await page.getByTestId("time-tile-5").click();

  await expect(page.getByText("Done")).toBeVisible();

  expect(submittedPayload).not.toBeNull();
  expect(submittedPayload).toMatchObject({
    requirement_id: "polgar-m2",
    count_increment: 1,
    minutes_spent: 5,
  });
});
