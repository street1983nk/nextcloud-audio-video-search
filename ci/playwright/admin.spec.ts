// The admin section (UI-SPEC, surface 3): state of the other half, versions,
// "Check again" and the debug block with the test result switch.
//
// The tests tagged @disabled, @unreachable and @nodebug need an instance the
// workflow rebuilt beforehand (backend disabled, container stopped, debug mode
// off); deploy-harp.yml runs each of them in its own step with --grep and
// leaves them out of the main run. The same holds for @drift, @patch and
// @missing (plan 10): the backend registered again a minor apart, a patch
// apart, and not registered at all; AVS_BACKEND_VERSION names the version the
// workflow registered.
import { expect, test, type Page } from '@playwright/test';
import { ADMIN_PATH, gridOnly, isHighContrast, login, ocsSearch, screenshot, users } from './helpers';

const VERSION = '0.1.0';
// The mark of a test result in the subline, in the three languages.
const SAMPLE_MARK = /Test result|Testtreffer|Résultat de test/;

async function openSection(page: Page, highContrast: boolean): Promise<void> {
	// dora is an admin as well and carries the high contrast theme.
	await login(page, highContrast ? users.dora() : users.admin());
	await page.goto(ADMIN_PATH);
	await expect(page.locator('#avs-admin')).toBeVisible();
}

/** The backend version the drift step of the workflow registered. */
function registeredBackendVersion(): string {
	const value = process.env.AVS_BACKEND_VERSION;
	if (value === undefined || value === '') {
		throw new Error('AVS_BACKEND_VERSION is not set; the drift tests run in the drift steps of deploy-harp.yml only');
	}
	return value;
}

/** The one action of an error banner leads to the app management, on every version. */
async function expectAppsLink(page: Page, state: string): Promise<void> {
	const link = page.locator(`[data-state="${state}"] .avs-banner__action`);
	await expect(link).toBeVisible();
	await expect(link).toHaveAttribute('href', /\/settings\/apps$/);
}

/**
 * The seed created test results, so the empty hint of the debug block never
 * shows: not with a count above zero, and not while the backend cannot report
 * its count at all.
 */
async function expectNoEmptyHint(page: Page): Promise<void> {
	await expect(page.locator('#avs-sample-empty')).toBeHidden();
}

/** "Check again", so the banner shows the state of right now. */
async function recheck(page: Page): Promise<void> {
	const answer = page.waitForResponse((response) => response.url().includes('/apps/audio_video_search/admin/state'));
	await page.locator('#avs-recheck').click();
	await answer;
}

test('Zustand ok mit Version auf beiden Seiten @screenshot', async ({ page }, testInfo) => {
	await openSection(page, isHighContrast(testInfo));

	await expect(page.locator('[data-state="ok"]')).toBeVisible();
	await expect(page.locator('.avs-version-own').first()).toHaveText(VERSION);
	await expect(page.locator('.avs-version-backend').first()).toHaveText(VERSION);
	// At rest the spinner of "Check again" is hidden, server button styles or not.
	await expect(page.locator('#avs-recheck-spinner')).toBeHidden();
	await expectNoEmptyHint(page);
	await screenshot(page, 'admin-ok', testInfo);
});

test('Debug-Block: Schalter blendet den Testtreffer ein und aus', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await openSection(page, false);

	const toggle = page.locator('#avs-sample-visible');
	// The Nextcloud checkbox style moves the input out of sight; a user clicks its label.
	const toggleLabel = page.locator('label[for="avs-sample-visible"]');
	await expect(toggle).toBeVisible();
	const alice = users.alice();

	// ci/seed.sh switched it on: the test result is in the search, marked.
	await expect(toggle).toBeChecked();
	await expect.poll(async () => (await ocsSearch(alice)).length).toBeGreaterThan(0);
	for (const entry of await ocsSearch(alice)) {
		expect(entry.subline).toMatch(SAMPLE_MARK);
	}

	const saved = () => page.waitForResponse((response) => response.url().includes('/apps/audio_video_search/admin/sample'));
	let answer = saved();
	await toggleLabel.click();
	expect((await answer).ok()).toBe(true);
	await expect(toggle).not.toBeChecked();
	await expect.poll(async () => (await ocsSearch(alice)).length).toBe(0);

	// And back on, so the tests after this one find the hits again.
	answer = saved();
	await toggleLabel.click();
	expect((await answer).ok()).toBe(true);
	await expect(toggle).toBeChecked();
	await expect.poll(async () => (await ocsSearch(alice)).length).toBeGreaterThan(0);
});

test('Erneut prüfen: aria-busy während der Prüfung, danach Fokus auf dem Zustand', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await openSection(page, false);

	// The answer is held back until aria-busy has been seen; no fixed wait.
	let release: () => void = () => {};
	const held = new Promise<void>((resolve) => {
		release = resolve;
	});
	await page.route('**/apps/audio_video_search/admin/state', async (route) => {
		await held;
		await route.continue();
	});

	const stateArea = page.locator('#avs-backend-state');
	await page.locator('#avs-recheck').click();
	await expect(stateArea).toHaveAttribute('aria-busy', 'true');
	release();

	await expect(stateArea).not.toHaveAttribute('aria-busy', 'true');
	await expect(stateArea).toBeFocused();
	await expect(page.locator('[data-state="ok"]')).toBeVisible();
});

test('Backend deaktiviert: Banner und leere Suche @disabled @screenshot', async ({ page }, testInfo) => {
	await openSection(page, isHighContrast(testInfo));
	await recheck(page);

	await expect(page.locator('[data-state="backend_disabled"]')).toBeVisible();
	await expectAppsLink(page, 'backend_disabled');
	expect(await ocsSearch(users.alice())).toHaveLength(0);
	await expectNoEmptyHint(page);
	await screenshot(page, 'admin-backend_disabled', testInfo);
});

test('Backend nicht erreichbar: Banner und leere Suche @unreachable @screenshot', async ({ page }, testInfo) => {
	await openSection(page, isHighContrast(testInfo));
	await recheck(page);

	await expect(page.locator('[data-state="backend_unreachable"]')).toBeVisible();
	await expectAppsLink(page, 'backend_unreachable');
	expect(await ocsSearch(users.alice())).toHaveLength(0);
	await expectNoEmptyHint(page);
	await screenshot(page, 'admin-backend_unreachable', testInfo);
});

test('Ohne Debug-Modus wird der Debug-Block nicht gerendert @nodebug', async ({ page }, testInfo) => {
	gridOnly(testInfo);
	await openSection(page, false);

	await expect(page.locator('.avs-admin__debug')).toHaveCount(0);
	await expect(page.locator('#avs-sample-visible')).toHaveCount(0);
});

test('Versionen weichen in Major.Minor ab: Fehlerbanner mit beiden Versionen, leere Suche @drift @screenshot', async ({ page }, testInfo) => {
	await openSection(page, isHighContrast(testInfo));
	await recheck(page);

	const banner = page.locator('[data-state="version_drift"]');
	await expect(banner).toBeVisible();
	await expect(banner.locator('.avs-version-own')).toHaveText(VERSION);
	await expectAppsLink(page, 'version_drift');
	await expect(banner.locator('.avs-version-backend')).toHaveText(registeredBackendVersion());
	expect(await ocsSearch(users.alice())).toHaveLength(0);
	await screenshot(page, 'admin-version_drift', testInfo);
});

test('Nur der Patch-Teil weicht ab: Hinweis mit beiden Versionen, Suche liefert Treffer @patch @screenshot', async ({ page }, testInfo) => {
	await openSection(page, isHighContrast(testInfo));
	await recheck(page);

	const banner = page.locator('[data-state="version_patch_differs"]');
	await expect(banner).toBeVisible();
	await expect(banner.locator('.avs-version-own')).toHaveText(VERSION);
	await expect(banner.locator('.avs-version-backend')).toHaveText(registeredBackendVersion());
	await expect.poll(async () => (await ocsSearch(users.alice())).length).toBeGreaterThan(0);
	await screenshot(page, 'admin-version_patch_differs', testInfo);
});

test('Backend nicht installiert: Banner und leere Suche @missing @screenshot', async ({ page }, testInfo) => {
	await openSection(page, isHighContrast(testInfo));
	await recheck(page);

	await expect(page.locator('[data-state="backend_missing"]')).toBeVisible();
	await expectAppsLink(page, 'backend_missing');
	expect(await ocsSearch(users.alice())).toHaveLength(0);
	await expectNoEmptyHint(page);
	await screenshot(page, 'admin-backend_missing', testInfo);
});
