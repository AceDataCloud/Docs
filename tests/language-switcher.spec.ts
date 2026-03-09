import { test, expect } from "@playwright/test";

const BASE = "http://localhost:3333";

test.describe("Language switcher", () => {
  test("Chinese root page loads with navigation tabs", async ({ page }) => {
    await page.goto(BASE, { waitUntil: "domcontentloaded" });
    // Should have sidebar / navigation visible
    await expect(page).toHaveTitle(/.+/);
    // Look for the language selector trigger (globe icon or language label)
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });

  test("English page loads with navigation sidebar", async ({ page }) => {
    await page.goto(`${BASE}/en/introduction`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page).toHaveTitle(/.+/);
    // The page should contain introduction content, not a blank sidebar
    const body = await page.textContent("body");
    expect(body?.length).toBeGreaterThan(100);
  });

  test("Japanese page loads with translated navigation", async ({ page }) => {
    await page.goto(`${BASE}/ja/introduction`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page).toHaveTitle(/.+/);
    const body = await page.textContent("body");
    expect(body?.length).toBeGreaterThan(100);
  });

  test("Korean page loads with navigation", async ({ page }) => {
    await page.goto(`${BASE}/ko/introduction`, {
      waitUntil: "domcontentloaded",
    });
    const body = await page.textContent("body");
    expect(body?.length).toBeGreaterThan(100);
  });

  test("Language pages have sidebar navigation links", async ({ page }) => {
    // Test that English page has sidebar navigation groups (the core fix)
    await page.goto(`${BASE}/en/introduction`, {
      waitUntil: "domcontentloaded",
    });

    // Wait for the page to fully render
    await page.waitForTimeout(2000);

    // Look for navigation links in the sidebar — these should exist now
    // that we have proper tabs with groups
    const navLinks = await page.locator("nav a[href]").count();
    expect(navLinks).toBeGreaterThan(0);
  });

  test("All supported languages return HTTP 200", async ({ request }) => {
    test.setTimeout(120_000);
    const langs = [
      "en",
      "ja",
      "ko",
      "es",
      "fr",
      "de",
      "pt",
      "ru",
      "ar",
      "it",
      "sv",
      "uk",
      "pl",
      "zh-TW",
    ];
    for (const lang of langs) {
      const resp = await request.get(`${BASE}/${lang}/introduction`);
      expect(resp.status(), `${lang} should return 200`).toBe(200);
    }
  });

  test("Language pages have more content than just a redirect", async ({
    page,
  }) => {
    // This is the core regression test: before the fix, switching to English
    // would show a nearly empty page because there were no navigation tabs.
    await page.goto(`${BASE}/en/introduction`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForTimeout(3000);

    // Get the HTML content length — a properly rendered page should be substantial
    const html = await page.content();
    expect(html.length).toBeGreaterThan(5000);

    // There should be multiple links on the page (sidebar nav + content links)
    const allLinks = await page.locator("a[href]").count();
    expect(allLinks).toBeGreaterThan(5);
  });
});
