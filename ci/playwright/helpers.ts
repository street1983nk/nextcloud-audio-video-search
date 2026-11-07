// Shared pieces of the end-to-end specs: the users and file ids of ci/seed.sh,
// the login, the OCS search as a user, the media position and the screenshots.
//
// No fixed waits anywhere: web-first assertions, waitForResponse and
// expect.poll only.
import { expect, request, test, type APIRequestContext, type Page, type TestInfo } from '@playwright/test';

export const APP_PATH = '/index.php/apps/audio_video_search';
export const ADMIN_PATH = '/index.php/settings/admin/audio_video_search';
export const QUERY = 'Audiosuche';
// The test result is seeded at 42 s; the hit points to the word "Audiosuche",
// the 7th word of the sample text at 400 ms per word: 42 + 6 * 0.4 = 44.4 s.
export const MARK_SECONDS = 44.4;
export const TOLERANCE_SECONDS = 0.5;
/** Every name ci/seed.sh gives a test file; none of them may leak (T-01-44). */
export const TEST_FILE_NAMES = ['tone-90s', 'broken.webm', 'locked.webm'] as const;

export type User = { name: string; password: string };

function env(name: string): string {
	const value = process.env[name];
	if (value === undefined || value === '') {
		throw new Error(`${name} is not set; the specs run after ci/seed.sh in CI only`);
	}
	return value;
}

export const users = {
	admin: (): User => ({ name: 'admin', password: env('ADMIN_PASS') }),
	alice: (): User => ({ name: 'alice', password: env('ALICE_PASS') }),
	bob: (): User => ({ name: 'bob', password: env('BOB_PASS') }),
	carol: (): User => ({ name: 'carol', password: env('CAROL_PASS') }),
	mallory: (): User => ({ name: 'mallory', password: env('MALLORY_PASS') }),
	dora: (): User => ({ name: 'dora', password: env('DORA_PASS') }),
};

export const fileIds = {
	webm: (): string => env('FILEID_WEBM'),
	team: (): string => env('FILEID_TEAM'),
	broken: (): string => env('FILEID_BROKEN'),
	locked: (): string => env('FILEID_LOCKED'),
};

export function isHighContrast(testInfo: TestInfo): boolean {
	return testInfo.project.metadata?.highContrast === true;
}

/** Tests that are not part of the screenshot grid skip the high contrast project. */
export function gridOnly(testInfo: TestInfo): void {
	test.skip(isHighContrast(testInfo), 'the high contrast project only takes screenshots');
}

export function playPath(fileId: string): string {
	return `${APP_PATH}/play/${fileId}?t=44.4`;
}

/** Fill the login form the page shows right now and wait until it is gone. */
export async function submitLogin(page: Page, user: User): Promise<void> {
	await page.locator('#user').fill(user.name);
	await page.locator('#password').fill(user.password);
	await page.locator('form[name="login"] [type="submit"], button[type="submit"]').first().click();
	await expect(page).not.toHaveURL(/\/login(\?|$)/);
}

export async function login(page: Page, user: User): Promise<void> {
	await page.goto('/index.php/login');
	await submitLogin(page, user);
}

/** The OCS search of the provider as one user, with basic auth. */
export async function ocsSearch(user: User): Promise<Array<{ subline: string; attributes: Record<string, string> }>> {
	const api: APIRequestContext = await request.newContext({
		baseURL: process.env.NC_URL ?? 'http://localhost:8080',
		httpCredentials: { username: user.name, password: user.password, send: 'always' },
		extraHTTPHeaders: { 'OCS-APIRequest': 'true', Accept: 'application/json' },
	});
	try {
		const response = await api.get(`/ocs/v2.php/search/providers/audio_video_search/search?term=${QUERY}`);
		expect(response.status()).toBe(200);
		const body = await response.json();
		return body.ocs.data.entries;
	} finally {
		await api.dispose();
	}
}

/** The position of the medium once its metadata is there, else -1. */
export function position(page: Page): () => Promise<number> {
	const media = page.locator('#avs-media');
	return () => media.evaluate((element: HTMLMediaElement) => (element.readyState >= 1 ? element.currentTime : -1));
}

/**
 * The medium is at rest for a screenshot: the seek is done, the frame at the
 * mark is decoded and the browser stopped fetching. Metadata alone is not
 * enough: Chromium reaches readyState 1 with currentTime already on the mark
 * while it is still seeking, and draws its loading spinner over the video.
 */
export async function expectMediaSettled(page: Page): Promise<void> {
	const media = page.locator('#avs-media');
	await expect
		.poll(
			() =>
				media.evaluate(
					(element: HTMLMediaElement) =>
						element.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
						!element.seeking &&
						element.networkState !== HTMLMediaElement.NETWORK_LOADING,
				),
			{ timeout: 15_000 },
		)
		.toBe(true);
}

export async function expectAtMark(page: Page): Promise<void> {
	const at = position(page);
	await expect.poll(at).toBeGreaterThanOrEqual(MARK_SECONDS - TOLERANCE_SECONDS);
	expect(await at()).toBeLessThanOrEqual(MARK_SECONDS + TOLERANCE_SECONDS);
}

/** WebDAV answers the address of the medium with a byte range: 206. */
export async function expectPartialContent(page: Page): Promise<void> {
	const source = await page.locator('#avs-media').getAttribute('src');
	expect(source).toContain('/remote.php/dav/files/');
	const address = (source ?? '').split('#')[0];
	const response = await page.request.get(address, { headers: { Range: 'bytes=0-1023' } });
	expect(response.status()).toBe(206);
}

export async function screenshot(page: Page, name: string, testInfo: TestInfo): Promise<void> {
	await page.screenshot({ path: `screenshots/${name}-${testInfo.project.name}.png`, fullPage: true });
}
