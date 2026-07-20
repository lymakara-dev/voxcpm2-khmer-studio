import { test, expect } from "@playwright/test";

function makeWavBuffer() {
  const samples = 100;
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + samples * 2, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(48000, 24);
  header.writeUInt32LE(96000, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(samples * 2, 40);
  return Buffer.concat([header, Buffer.alloc(samples * 2)]);
}

async function mockBackend(page) {
  const wav = makeWavBuffer();
  await page.route("**/api/model-info", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        model_id: "sumnim/VoxCPM2-Khmer",
        base: "openbmb/VoxCPM2",
        params: "2B",
        sample_rate_out: 48000,
        languages: 30,
        license: "apache-2.0",
        allow_raw_paths: false,
        mock: true,
        auth_required: false,
      }),
    })
  );
  await page.route("**/api/tts?async=1", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ job_id: "test-job", position: 0 }),
    })
  );
  await page.route("**/api/jobs/test-job", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "done", position: 0 }),
    })
  );
  await page.route("**/api/jobs/test-job/result", (route) =>
    route.fulfill({ status: 200, contentType: "audio/wav", body: wav })
  );
}

test("app loads and shows the Speak tab by default", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  await expect(page.getByRole("tab", { name: "Speak" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "Text to speak" })).toBeVisible();
});

test("tab switching shows the right panel", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  await page.getByRole("tab", { name: "Voice design" }).click();
  await expect(page.getByRole("heading", { name: "Describe the voice" })).toBeVisible();
  await page.getByRole("tab", { name: "Model" }).click();
  await expect(page.getByRole("heading", { name: "Architecture" })).toBeVisible();
});

test("typing text and clicking Generate produces a player", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  const textarea = page.locator("textarea.kh");
  await textarea.fill("សួស្តី");
  await page.getByRole("button", { name: "Generate speech" }).click();
  await expect(page.getByRole("button", { name: /^(Play|Pause)$/ })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("output.wav · 48 kHz")).toBeVisible();
});

test("moving a slider updates the Python snippet", async ({ page }) => {
  await mockBackend(page);
  await page.goto("/");
  const code = page.locator("pre.code");
  await expect(code).toContainText("cfg_value=2");
  const slider = page.locator('input[type="range"]').first();
  await slider.fill("3.5");
  await slider.dispatchEvent("input");
  await expect(code).toContainText("cfg_value=3.5");
});
