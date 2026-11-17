import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeEach(async ({ page }) => {
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return url.hostname === "127.0.0.1" ? route.continue() : route.abort();
  });
});

test("a finite accessible edition fits the viewport in light and dark modes", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "A little perspective.",
  );
  await expect(page.locator(".story")).toHaveCount(15);
  await expect(page.locator("iframe")).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
  const audit = async () => {
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  };
  await audit();
  await page.getByRole("button", { name: "Switch to dark appearance" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await audit();
  expect(errors).toEqual([]);
});

test("saved selections and read progress survive reload and can be cleared", async ({
  page,
}) => {
  await page.goto("/");
  const first = page.locator(".story").first();
  await first.getByRole("button", { name: "Save", exact: true }).click();
  await first.getByRole("button", { name: "Mark read" }).click();
  await expect(page.locator("[data-progress]")).toHaveText(
    "1 of 15 marked as read",
  );
  await page.reload();
  await expect(first.getByRole("button", { name: "Saved ✓" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.locator('[data-view="saved"]').click();
  await expect(page.locator(".story:visible")).toHaveCount(1);
  await first.getByRole("button", { name: "Saved ✓" }).click();
  await expect(page.locator(".story:visible")).toHaveCount(0);
  await expect(page.locator('[data-view="saved"]')).toBeFocused();
  await page.locator("#privacy summary").click();
  await page
    .getByRole("button", { name: "Clear my local preferences" })
    .click();
  await expect(page.locator(".story:visible")).toHaveCount(15);
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
});

test("YouTube connects only after an explicit choice and keeps its official controls", async ({
  page,
}) => {
  const external = [];
  page.on("request", (request) => {
    if (!request.url().startsWith("http://127.0.0.1:8765"))
      external.push(request.url());
  });
  await page.goto("/");
  expect(external).toEqual([]);
  await page.route("https://www.youtube-nocookie.com/**", (route) =>
    route.fulfill({
      body: "<html><body>Mock official player</body></html>",
      contentType: "text/html",
    }),
  );
  await page.getByRole("button", { name: "Load player" }).first().click();
  const frame = page.locator("iframe");
  await expect(frame).toHaveCount(1);
  await expect(frame).toHaveAttribute(
    "src",
    "https://www.youtube-nocookie.com/embed/11111111111?playsinline=1",
  );
  await expect(frame).toHaveAttribute(
    "referrerpolicy",
    "strict-origin-when-cross-origin",
  );
  expect(await frame.getAttribute("allow")).not.toContain("autoplay");
  const box = await frame.boundingBox();
  expect(box.width).toBeGreaterThanOrEqual(200);
  expect(box.height).toBeGreaterThanOrEqual(200);
});

test("empty lanes, blocked storage and stale editions remain understandable", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get: () => {
        throw new Error("blocked");
      },
    });
    Date.now = () => Date.parse("2026-11-25T12:00:00Z");
  });
  await page.goto("/empty.html");
  await expect(page.locator(".empty")).toHaveCount(3);
  await expect(page.locator("#youtube")).toContainText(
    "No new videos from your channels this week",
  );
  await expect(page.locator(".freshness-notice")).toBeVisible();
  await page.goto("/");
  await page.locator(".save-button").first().click();
  await expect(page.locator(".save-button").first()).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.locator(".storage-status")).toContainText(
    "this visit only",
  );
});

test("expired choices are ignored and a narrow phone never overflows", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem(
      "offscroll.preferences.v1",
      JSON.stringify({
        items: {
          "hackernews:https://example.org/story-1": {
            saved: true,
            read: true,
            at: 1,
          },
        },
      }),
    ),
  );
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/");
  await expect(page.locator("[data-saved-count]")).toHaveText("0");
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
  const manifest = await (
    await page.request.get("/manifest.webmanifest")
  ).json();
  expect(manifest.start_url).toBe("./");
});

test("the core edition works without JavaScript", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:8765");
  await expect(page.locator(".story")).toHaveCount(15);
  await expect(page.locator(".save-button:visible")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Open on YouTube" })).toHaveCount(
    4,
  );
  await context.close();
});
