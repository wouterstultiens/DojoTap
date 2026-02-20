import { expect, test } from "@playwright/test";

test("smoke: on-card controls drive count labels and submit", async ({ page }) => {
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
            is_custom: false,
            time_only: false,
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
            is_custom: false,
            time_only: false,
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
  await page.getByTestId("count-label-mode-polgar-m2").selectOption("absolute");
  await page.getByTestId("tile-size-polgar-m2").selectOption("small");
  await page.getByTestId("count-cap-polgar-m2").selectOption("3");
  await page.getByRole("button", { name: "Pinned" }).click();

  await page.getByTestId("pinned-task-polgar-m2").click();
  await expect(page.getByTestId("count-tile-1")).toContainText("437");
  await expect(page.getByTestId("count-tile-3")).toBeVisible();
  await expect(page.getByTestId("count-tile-4")).toHaveCount(0);
  await page.getByTestId("count-tile-1").click();

  await expect(page.getByTestId("time-tile-5")).toBeVisible();
  await expect(page.getByTestId("time-tile-180")).toBeVisible();
  await page.getByTestId("time-tile-5").click();

  await expect(page.getByText("Done")).toBeVisible();

  expect(submittedPayload).not.toBeNull();
  expect(submittedPayload).toMatchObject({
    requirement_id: "polgar-m2",
    count_increment: 1,
    minutes_spent: 5,
  });
});

test("smoke: settings filters include pinned label and hide completed", async ({ page }) => {
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
            id: "completed-task",
            name: "Completed Task",
            category: "Study",
            counts: { "1100-1200": 10 },
            start_count: 0,
            progress_bar_suffix: "",
            scoreboard_display: "",
            number_of_cohorts: 1,
            sort_priority: "1",
            current_count: 10,
            target_count: 10,
            is_custom: false,
            time_only: false,
          },
          {
            id: "active-task",
            name: "Active Task",
            category: "Study",
            counts: { "1100-1200": 10 },
            start_count: 0,
            progress_bar_suffix: "",
            scoreboard_display: "",
            number_of_cohorts: 1,
            sort_priority: "2",
            current_count: 4,
            target_count: 10,
            is_custom: false,
            time_only: false,
          },
        ],
        progress_by_requirement_id: {},
        pinned_task_ids: ["active-task"],
        available_cohorts: ["1100-1200"],
        default_filters: {
          cohort: "ALL",
        },
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
          requirementId: "active-task",
          previousCount: 4,
          newCount: 5,
          incrementalMinutesSpent: 5,
          date: "2026-02-20T20:00:00Z",
          notes: "",
        },
        upstream_response: { ok: true },
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();

  await expect(page.getByLabel("Pinned")).toBeVisible();
  await expect(page.getByText("Pinned only")).toHaveCount(0);
  await page.getByLabel("Pinned").uncheck();
  await expect(page.getByRole("heading", { name: "Completed Task" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Active Task" })).toBeVisible();

  await page.getByLabel("Hide completed").check();
  await expect(page.getByRole("heading", { name: "Completed Task" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Active Task" })).toBeVisible();
});

test("smoke: cohort-aware task names interpolate count placeholders", async ({ page }) => {
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
            id: "classical-play",
            name: "Play {{count}} Classical Games per Year",
            category: "Games + Analysis",
            counts: {
              "1100-1200": 120,
              "1200-1300": 90,
            },
            start_count: 0,
            progress_bar_suffix: "",
            scoreboard_display: "",
            number_of_cohorts: 2,
            sort_priority: "1",
            current_count: 12,
            target_count: 120,
            is_custom: false,
            time_only: false,
          },
        ],
        progress_by_requirement_id: {},
        pinned_task_ids: ["classical-play"],
        available_cohorts: ["1100-1200", "1200-1300"],
        default_filters: {
          cohort: "ALL",
        },
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
          requirementId: "classical-play",
          previousCount: 12,
          newCount: 13,
          incrementalMinutesSpent: 60,
          date: "2026-02-20T20:00:00Z",
          notes: "",
        },
        upstream_response: { ok: true },
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();

  await expect(page.getByRole("heading", { name: "Play 120 Classical Games per Year" })).toBeVisible();
  await expect(page.getByText("Play {{count}} Classical Games per Year")).toHaveCount(0);

  await page.getByLabel("Cohort").selectOption("1200-1300");
  await expect(page.getByRole("heading", { name: "Play 90 Classical Games per Year" })).toBeVisible();
});

test("smoke: custom time-only task skips count and submits zero increment", async ({ page }) => {
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
            id: "custom-timer-1",
            name: "Deep Work Timer",
            category: "Custom",
            counts: {},
            start_count: 0,
            progress_bar_suffix: "",
            scoreboard_display: "",
            number_of_cohorts: 0,
            sort_priority: "zzz_custom",
            current_count: 0,
            target_count: null,
            is_custom: true,
            time_only: true,
          },
        ],
        progress_by_requirement_id: {},
        pinned_task_ids: ["custom-timer-1"],
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
          requirementId: "custom-timer-1",
          previousCount: 0,
          newCount: 0,
          incrementalMinutesSpent: 10,
          date: "2026-02-20T20:00:00Z",
          notes: "",
        },
        upstream_response: {
          ok: true,
        },
      }),
    });
  });

  await page.goto("/");
  await page.getByTestId("pinned-task-custom-timer-1").click();

  await expect(page.getByTestId("count-tile-1")).toHaveCount(0);
  await expect(page.getByTestId("time-tile-10")).toBeVisible();
  await page.getByTestId("time-tile-10").click();
  await expect(page.getByText("Done")).toBeVisible();

  expect(submittedPayload).toMatchObject({
    requirement_id: "custom-timer-1",
    count_increment: 0,
    minutes_spent: 10,
  });
});

test("smoke: mobile very-small tiles are dense and stage changes scroll to top", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });

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
            id: "mobile-polgar",
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
            is_custom: false,
            time_only: false,
          },
        ],
        progress_by_requirement_id: {},
        pinned_task_ids: ["mobile-polgar"],
        available_cohorts: ["1100-1200"],
        default_filters: {
          cohort: "ALL",
        },
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
          requirementId: "mobile-polgar",
          previousCount: 436,
          newCount: 437,
          incrementalMinutesSpent: 5,
          date: "2026-02-20T20:00:00Z",
          notes: "",
        },
        upstream_response: { ok: true },
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByTestId("tile-size-mobile-polgar").selectOption("very-small");
  await page.getByRole("button", { name: "Pinned" }).click();

  await page.evaluate(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: "auto" });
  });
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);

  await page.getByTestId("pinned-task-mobile-polgar").click();
  await page.getByTestId("count-tile-1").waitFor();
  await expect.poll(() => page.evaluate(() => Math.round(window.scrollY))).toBe(0);

  const columns = await page.locator(".tile-grid .input-tile").evaluateAll((elements) => {
    const tops = elements.map((element) =>
      Math.round((element as HTMLElement).getBoundingClientRect().top)
    );
    const firstRowTop = Math.min(...tops);
    const firstRowElements = elements.filter(
      (_element, index) => Math.abs(tops[index] - firstRowTop) <= 2
    );
    const uniqueLefts = new Set(
      firstRowElements.map((element) =>
        Math.round((element as HTMLElement).getBoundingClientRect().left)
      )
    );
    return uniqueLefts.size;
  });
  expect(columns).toBeGreaterThanOrEqual(4);

  await page.getByTestId("count-tile-1").click();
  await page.getByTestId("time-tile-5").waitFor();
  await expect.poll(() => page.evaluate(() => Math.round(window.scrollY))).toBe(0);
});
