// The core path of phase 1 as an end-to-end contract: find a spoken word in the
// Unified Search, click the hit, and the media stands at the time mark.
//
// This test fails until the whole chain exists (provider, play route, sample
// hit, CI instance); plan 11 runs it in CI against a throwaway instance that
// carries tone-90s.webm (ci/make-testmedia.sh) and a sample hit at 42 s for
// the word "Audiosuche" (occ audio_video_search:sample). Plan 09 adds the error
// states, the admin area and the three widths.
//
// No fixed waits: only web-first assertions, waitForResponse and expect.poll.
import { expect, test, type Page } from '@playwright/test';

const USER = process.env.NC_USER ?? 'admin';
const PASSWORD = process.env.NC_PASSWORD ?? '';
const MEDIA_NAME = 'tone-90s.webm';
const QUERY = 'Audiosuche';
const MARK_SECONDS = 42;
const TOLERANCE_SECONDS = 0.5;
// The provider name in the three catalogue languages (php/l10n).
const GROUP_NAME = /^(Audio and video|Audio und Video|Audio et vidéo)$/;

/** Log in through the regular login form; the session lives in the test's own context. */
async function login(page: Page): Promise<void> {
	await page.goto('/login');
	await page.locator('#user').fill(USER);
	await page.locator('#password').fill(PASSWORD);
	await page.locator('form[name="login"] [type="submit"], button[type="submit"]').first().click();
	await expect(page).not.toHaveURL(/\/login(\?|$)/);
	await page.context().storageState({ path: test.info().outputPath('storage-state.json') });
}

/** Open the Unified Search from the header, by shortcut or by its button. */
async function openUnifiedSearch(page: Page): Promise<void> {
	const button = page
		.locator('.unified-search-menu button, #unified-search button, header [aria-label="Unified search"]')
		.first();
	if (await button.isVisible()) {
		await button.click();
	} else {
		await page.keyboard.press('Control+K');
	}
}

test('Kernweg: Treffer finden und an der Zeitstelle abspielen', async ({ page }) => {
	await login(page);
	await openUnifiedSearch(page);

	const input = page.getByRole('dialog').locator('input[type="search"], input[type="text"]').first();
	await expect(input).toBeVisible();
	await input.fill(QUERY);

	await expect(page.getByText(GROUP_NAME)).toBeVisible();
	const hit = page
		.getByRole('link')
		.filter({ hasText: MEDIA_NAME })
		.filter({ hasText: /(^|\s)0:42 · / })
		.first();
	await expect(hit).toBeVisible();

	// The media request goes to WebDAV with a byte range, so the answer is 206.
	const partialContent = page.waitForResponse(
		(response) => response.url().includes('/remote.php/dav/files/') && response.status() === 206,
	);
	await hit.click();

	await expect(page).toHaveURL(/\/apps\/audio_video_search\/play\/\d+\?t=42\.0(&|$)/);
	await partialContent;

	const media = page.locator('#avs-media');
	await expect(media).toBeAttached();
	const support = await media.evaluate((element: HTMLMediaElement) =>
		element.canPlayType('video/webm; codecs="vp9, opus"'),
	);
	console.log(`canPlayType video/webm vp9+opus: "${support}"`);

	// After loadedmetadata (readyState >= 1) the media stands at the mark.
	const position = () =>
		media.evaluate((element: HTMLMediaElement) => (element.readyState >= 1 ? element.currentTime : -1));
	await expect.poll(position).toBeGreaterThanOrEqual(MARK_SECONDS - TOLERANCE_SECONDS);
	expect(await position()).toBeLessThanOrEqual(MARK_SECONDS + TOLERANCE_SECONDS);
});
