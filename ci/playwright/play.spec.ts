// The core path of phase 1 as an end-to-end contract and the states of the
// playback page (UI-SPEC, surface 2), against the throwaway instance that
// ci/seed.sh filled: tone-90s.webm with a test result at 42 s for the word
// "Audiosuche", reachable for its owner alice, for carol through the team
// folder and for bob through a share; mallory reads none of it.
//
// No fixed waits: only web-first assertions, waitForResponse and expect.poll.
import { expect, test, type Page } from '@playwright/test';
import {
	expectAtMark,
	expectPartialContent,
	fileIds,
	gridOnly,
	isHighContrast,
	login,
	playPath,
	position,
	QUERY,
	screenshot,
	submitLogin,
	TEST_FILE_NAMES,
	users,
} from './helpers';

const MEDIA_NAME = 'tone-90s.webm';
// The provider name in the three catalogue languages (php/l10n).
const GROUP_NAME = /^(Audio and video|Audio und Video|Audio et vidéo)$/;
// The heading of a page that names no file, in the three languages.
const NEUTRAL_HEADING = /^(Playback|Wiedergabe|Lecture)$/;

/** Open the Unified Search from the header, by its button or by shortcut. */
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

test('Kernweg: Treffer finden und an der Zeitstelle abspielen', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.alice());
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

	await expectAtMark(page);
});

test('Gruppenordner: Mitglied spielt ab der Zeitstelle, WebDAV 206', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.carol());
	await page.goto(playPath(fileIds.team()));

	await expect(page.locator('#avs-media')).toBeAttached();
	await expectPartialContent(page);
	await expectAtMark(page);
});

test('Freigabe: Empfänger spielt ab der Zeitstelle, WebDAV 206', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.bob());
	await page.goto(playPath(fileIds.webm()));

	await expect(page.locator('#avs-media')).toBeAttached();
	await expectPartialContent(page);
	await expectAtMark(page);
});

// Pitfall 1: the time mark must survive the detour over the login page.
test('Abgelaufene Sitzung: nach der Anmeldung steht das Medium an der Zeitstelle', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.alice());
	await page.context().clearCookies();

	await page.goto(playPath(fileIds.webm()));
	await expect(page).toHaveURL(/\/login/);
	await submitLogin(page, users.alice());

	await expect(page).toHaveURL(/\/apps\/audio_video_search\/play\/\d+\?t=42\.0(&|$)/);
	await expect(page.locator('#avs-media')).toBeAttached();
	await expectAtMark(page);
});

test('Fremde Datei: 404 ohne Dateinamen', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.mallory());

	const response = await page.goto(playPath(fileIds.webm()));
	expect(response?.status()).toBe(404);
	await expect(page.locator('h2').first()).toHaveText(NEUTRAL_HEADING);
	await expect(page.locator('#avs-media')).toHaveCount(0);

	const content = await page.content();
	for (const name of TEST_FILE_NAMES) {
		expect(content).not.toContain(name);
	}
});

test('Download-Sperre: Hinweis-Banner statt Medium', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.bob());
	await page.goto(playPath(fileIds.locked()));

	await expect(page.locator('#avs-banner-download_blocked')).toBeVisible();
	await expect(page.locator('#avs-media')).toHaveCount(0);
});

test('Kaputte Datei: Format-Banner mit role=alert und Fokus', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.alice());
	await page.goto(playPath(fileIds.broken()));

	const banner = page.locator('#avs-banner-format');
	await expect(banner).toBeVisible();
	await expect(banner).toHaveAttribute('role', 'alert');
	await expect(banner).toBeFocused();
	await expect(page.locator('#avs-media')).toBeHidden();
});

test('Sprungknopf: zurück auf die Zeitstelle, Fokus auf dem Medium, bleibt pausiert', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.alice());
	await page.goto(playPath(fileIds.webm()));
	await expectAtMark(page);

	const media = page.locator('#avs-media');
	await media.evaluate((element: HTMLMediaElement) => {
		element.currentTime = 10;
	});
	const at = position(page);
	await expect.poll(at).toBeLessThan(11);

	const jump = page.locator('#avs-jump');
	await expect(jump).toBeVisible();
	await jump.click();

	await expectAtMark(page);
	expect(await page.evaluate(() => document.activeElement?.id)).toBe('avs-media');
	expect(await media.evaluate((element: HTMLMediaElement) => element.paused)).toBe(true);
});

test('Seitentitel nennt die Datei, nichts startet von selbst', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.alice());
	await page.goto(playPath(fileIds.webm()));

	await expect(page.locator('#avs-media')).toBeAttached();
	expect(await page.title()).toContain(MEDIA_NAME);
	await expect(page.locator('[autoplay]')).toHaveCount(0);
});

// The screenshot of the playback page for every project of the grid. The high
// contrast project opens the team folder copy as dora, whose theme is high
// contrast; every other project opens alice's own file.
test('Abspielansicht für die Abnahme @screenshot', async ({ page }, testInfo) => {
	const highContrast = isHighContrast(testInfo);
	await login(page, highContrast ? users.dora() : users.alice());
	await page.goto(playPath(highContrast ? fileIds.team() : fileIds.webm()));

	await expectAtMark(page);
	await screenshot(page, 'play', testInfo);
});
