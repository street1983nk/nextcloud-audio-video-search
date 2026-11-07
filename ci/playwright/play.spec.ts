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
	expectMediaSettled,
	expectPartialContent,
	fileIds,
	gridOnly,
	login,
	playPath,
	position,
	QUERY,
	reviewer,
	SAMPLE_MARK,
	screenshot,
	submitLogin,
	TEST_FILE_NAMES,
	users,
} from './helpers';

const MEDIA_NAME = 'tone-90s.webm';
// The provider name in the three catalogue languages (php/l10n). The result
// list carries it as its name: "Audio and video" on 33 and 34, "More from
// Audio and video" on 35 (checked in the CI snapshots of all three).
const GROUP_NAME = /(^|\s)(Audio and video|Audio und Video|Audio et vidéo)$/;
// The heading of a page that names no file, in the three languages.
const NEUTRAL_HEADING = /^(Playback|Wiedergabe|Lecture)$/;

/**
 * Open the Unified Search from the header, the way a user does. Nextcloud 33
 * has a header button "Unified search"; 34 and 35 put the trigger into a
 * search landmark: a button on narrow screens and on wide 34, the combobox
 * itself on wide 35.
 */
async function openUnifiedSearch(page: Page): Promise<void> {
	const landmark = page.getByRole('search');
	const trigger = landmark
		.getByRole('button')
		.or(landmark.getByRole('combobox'))
		.or(page.locator('#unified-search button, header [aria-label="Unified search"], header [aria-label="Einheitliche Suche"], header [aria-label="Recherche unifiée"]'))
		.first();
	await expect(trigger).toBeVisible();
	await trigger.click();
}

/** Where the query goes once the search is open: the dialog field, or on wide 35 the header combobox. */
function searchField(page: Page) {
	return page
		.getByRole('dialog')
		.locator('input[type="search"], input[type="text"]')
		.or(page.locator('.unified-search-modal-root input[type="search"]'))
		.or(page.getByRole('search').getByRole('combobox'))
		.first();
}

/** Open the Unified Search, type the query and return the visible hit on the medium at 0:44. */
async function searchHit(page: Page) {
	await openUnifiedSearch(page);

	const input = searchField(page);
	await expect(input).toBeVisible();
	await input.fill(QUERY);

	// A list on 33, 34 and narrow 35, a listbox on wide 35.
	const group = page.getByRole('list', { name: GROUP_NAME }).or(page.getByRole('listbox', { name: GROUP_NAME }));
	await expect(group).toBeVisible();
	// Options hide the role of the link inside them, so the hit is found as an anchor.
	const hit = group
		.locator('a[href]')
		.filter({ hasText: MEDIA_NAME })
		.filter({ hasText: /(^|\s)0:44 · / })
		.first();
	await expect(hit).toBeVisible();
	return hit;
}

test('Kernweg: Treffer finden und an der Zeitstelle abspielen', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await login(page, users.alice());
	const hit = await searchHit(page);

	// The media request goes to WebDAV with a byte range, so the answer is 206.
	const partialContent = page.waitForResponse(
		(response) => response.url().includes('/remote.php/dav/files/') && response.status() === 206,
	);
	await hit.click();

	await expect(page).toHaveURL(/\/apps\/audio_video_search\/play\/\d+\?t=44\.4(&|$)/);
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
	// Leave the page first: its background requests would otherwise start a new
	// session after the cookies are gone and void the token of the login form.
	await page.goto('about:blank');
	await page.context().clearCookies();

	await page.goto(playPath(fileIds.webm()));
	await expect(page).toHaveURL(/\/login/);
	await submitLogin(page, users.alice());

	await expect(page).toHaveURL(/\/apps\/audio_video_search\/play\/\d+\?t=44\.4(&|$)/);
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
// review projects open the team folder copy as their review user; the English
// grid opens alice's own file.
test('Abspielansicht für die Abnahme @screenshot', async ({ page }, testInfo) => {
	const review = reviewer(testInfo);
	await login(page, review ?? users.alice());
	await page.goto(playPath(review !== null ? fileIds.team() : fileIds.webm()));

	await expectAtMark(page);
	await expectMediaSettled(page);
	await screenshot(page, 'play', testInfo);
});

// The hit in the Unified Search for every project of the grid: group name,
// time and the test result mark in the subline (UI-SPEC, surface 1). The
// review users find the copy in the team folder.
test('Suchtreffer für die Abnahme @screenshot', async ({ page }, testInfo) => {
	await login(page, reviewer(testInfo) ?? users.alice());
	const hit = await searchHit(page);
	await expect(hit).toContainText(SAMPLE_MARK);
	// Typing can start a second search; the picture waits until no loading ring
	// and no placeholder row is visible and the hit is shown again.
	await expect(page.locator('.loading-icon:visible, [class*="skeleton"]:visible')).toHaveCount(0);
	await expect(hit).toBeVisible();
	await screenshot(page, 'search-hit', testInfo);
});

// The banners of the playback page for every project of the grid (UI-SPEC,
// surface 2, state table). The English grid reaches each state with the user
// of its functional test above; a review user reaches all three, since alice's
// own file is not shared with them and they hold the shares of locked.webm
// (download switched off) and broken.webm.
const BANNER_SHOTS = [
	{ title: 'Nicht verfügbar', name: 'play-unavailable', banner: '#avs-banner-unavailable', user: users.mallory, fileId: fileIds.webm },
	{ title: 'Download gesperrt', name: 'play-download_blocked', banner: '#avs-banner-download_blocked', user: users.bob, fileId: fileIds.locked },
	{ title: 'Format kaputt', name: 'play-format_broken', banner: '#avs-banner-format', user: users.alice, fileId: fileIds.broken },
] as const;

for (const shot of BANNER_SHOTS) {
	test(`Banner "${shot.title}" für die Abnahme @screenshot`, async ({ page }, testInfo) => {
		await login(page, reviewer(testInfo) ?? shot.user());
		await page.goto(playPath(shot.fileId()));
		await expect(page.locator(shot.banner)).toBeVisible();
		await screenshot(page, shot.name, testInfo);
	});
}
