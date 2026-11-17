// Shared pieces of the end-to-end specs: the users and file ids of ci/seed.sh,
// the login, the OCS search as a user, the Unified Search dialog, the media
// position, the screenshots, occ of the test instance and the contrast
// measurement of plan 03-18, and the pieces of phase 4 (plan 04-14): the admin
// switch for viewing without download, sha256 of a file over WebDAV, a
// download into a folder, the export as text and the measured S7 forms; and
// for plan 04-17 the approved texts of 04-UI-SPEC, shares, the exclusion of a
// user, the stop and start of the backend container and the cue readers.
//
// No fixed waits anywhere: web-first assertions, waitForResponse and
// expect.poll only.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { expect, request, test, type APIRequestContext, type Locator, type Page, type TestInfo } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

export const APP_PATH = '/index.php/apps/audio_video_search';
export const ADMIN_PATH = '/index.php/settings/admin/audio_video_search';
export const QUERY = 'Audiosuche';
// The test result is seeded at 42 s; the hit points to the word "Audiosuche",
// the 7th word of the sample text at 400 ms per word: 42 + 6 * 0.4 = 44.4 s.
export const MARK_SECONDS = 44.4;
export const TOLERANCE_SECONDS = 0.5;
/** Every name ci/seed.sh gives a test file; none of them may leak (T-01-44). */
export const TEST_FILE_NAMES = ['tone-90s', 'broken.webm', 'locked.webm'] as const;
/** The mark of a test result in the subline, in the three languages. */
export const SAMPLE_MARK = /Test result|Testtreffer|Résultat de test/;

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
	elke: (): User => ({ name: 'elke', password: env('ELKE_PASS') }),
	fleur: (): User => ({ name: 'fleur', password: env('FLEUR_PASS') }),
	// Excluded from the app by ci/seed.sh, receives stille-60s.ogg (plan 03-18, P11).
	oskar: (): User => ({ name: 'oskar', password: env('OSKAR_PASS') }),
};

export const fileIds = {
	webm: (): string => env('FILEID_WEBM'),
	team: (): string => env('FILEID_TEAM'),
	broken: (): string => env('FILEID_BROKEN'),
	locked: (): string => env('FILEID_LOCKED'),
	// Phase 3 (ci/seed.sh with AVS_PHASE3_MEDIA=1): alice's files with one reason each.
	stille: (): string => env('FILEID_STILLE'),
	kaputt: (): string => env('FILEID_KAPUTT'),
	geschuetzt: (): string => env('FILEID_GESCHUETZT'),
	lang: (): string => env('FILEID_LANG'),
	tuerkisch: (): string => env('FILEID_TUERKISCH'),
	ohneTon: (): string => env('FILEID_OHNE_TON'),
	// bob's two files with speech: four places and two places.
	viele: (): string => env('FILEID_VIELE'),
	zwei: (): string => env('FILEID_ZWEI'),
	// Phase 4 (ci/seed.sh with AVS_PHASE4_MEDIA=1, plan 04-14): alice's S7 clips.
	// s7De is shared with the group "review" with the download switched off
	// (SRCH-04, X3), s7DeDigit with carol read only with download (X5).
	s7De: (): string => env('FILEID_S7_DE'),
	s7DeDigit: (): string => env('FILEID_S7_DE_DIGIT'),
	// Plan 04-17: S7-Übung.webm, a video with the speech of S7_DE, shared with
	// the group "review" with download (X1, D1 with an umlaut, sidecar, track),
	// and Ablage/s7-ablage.wav in alice's folder Ablage, shared with carol
	// with the right to create files (X5, E3, E4 change that share for a moment).
	s7Video: (): string => env('FILEID_S7_VIDEO'),
	ablage: (): string => env('FILEID_ABLAGE'),
};

export function isHighContrast(testInfo: TestInfo): boolean {
	return testInfo.project.metadata?.highContrast === true;
}

/**
 * The review user of a project beside the English grid, else null: dora for
 * high contrast, elke for German, fleur for French. ci/seed.sh gives all three
 * the reach of every screenshot (admin, member of the team folder, the shares
 * of locked.webm and broken.webm, no access to alice's own tone-90s.webm) and
 * sets the theme or the language.
 */
export function reviewer(testInfo: TestInfo): User | null {
	if (isHighContrast(testInfo)) {
		return users.dora();
	}
	switch (testInfo.project.metadata?.language) {
		case 'de':
			return users.elke();
		case 'fr':
			return users.fleur();
		default:
			return null;
	}
}

/** Tests that are not part of the screenshot grid skip the review projects. */
export function gridOnly(testInfo: TestInfo): void {
	test.skip(reviewer(testInfo) !== null, 'the review projects only take screenshots');
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

/** A node of the DevTools protocol DOM tree, as far as the loading panel check reads it. */
type ProtocolNode = {
	attributes?: string[];
	children?: ProtocolNode[];
	shadowRoots?: ProtocolNode[];
	shadowRootType?: string;
	childNodeCount?: number;
};

function loadingPanels(node: ProtocolNode, found: ProtocolNode[] = []): ProtocolNode[] {
	const attributes = node.attributes ?? [];
	const pseudo = attributes.indexOf('pseudo');
	if (pseudo !== -1 && attributes[pseudo + 1] === '-internal-media-controls-loading-panel') {
		found.push(node);
	}
	for (const child of [...(node.children ?? []), ...(node.shadowRoots ?? [])]) {
		loadingPanels(child, found);
	}
	return found;
}

/**
 * The state of the loading ring of the native media controls: 'spinning' while
 * Chromium draws it, 'idle' once it is gone, 'no controls' if the user agent
 * shadow tree of the medium is not readable (then the check proves nothing).
 *
 * The ring lives in the closed user agent shadow tree, out of reach of page
 * scripts and locators; the DevTools protocol reads it with pierce. Chromium
 * (media_control_loading_panel_element.cc) fills the shadow root of the panel
 * when loading starts and empties it in HideAnimation(), so a filled root is
 * a ring on screen.
 */
async function loadingRing(page: Page): Promise<'spinning' | 'idle' | 'no controls'> {
	const cdp = await page.context().newCDPSession(page);
	try {
		const { result } = await cdp.send('Runtime.evaluate', {
			expression: 'document.getElementById("avs-media")',
			objectGroup: 'avs-loading-ring',
		});
		if (result.objectId === undefined) {
			return 'no controls';
		}
		const { node } = await cdp.send('DOM.describeNode', { objectId: result.objectId, depth: -1, pierce: true });
		const medium: ProtocolNode = node;
		if (!(medium.shadowRoots ?? []).some((root) => root.shadowRootType === 'user-agent')) {
			return 'no controls';
		}
		const spinning = loadingPanels(medium).some((panel) =>
			(panel.shadowRoots ?? []).some((root) => (root.childNodeCount ?? root.children?.length ?? 0) > 0),
		);
		return spinning ? 'spinning' : 'idle';
	} finally {
		await cdp.send('Runtime.releaseObjectGroup', { objectGroup: 'avs-loading-ring' }).catch(() => undefined);
		await cdp.detach();
	}
}

/**
 * The medium is at rest for a screenshot: the seek is done, the frame at the
 * mark is decoded, the browser stopped fetching and the native controls took
 * their loading ring away. Metadata alone is not enough: Chromium reaches
 * readyState 1 with currentTime already on the mark while it is still seeking.
 * The ring outlives the loading as well: once the medium is ready, Chromium
 * lets the ring finish its current turn of up to 1333 ms (state kCoolingDown,
 * animation-iteration-count set to the next turn) and removes it only on
 * animationend. A picture right after the media checks catches that turn,
 * whatever the screenshot does with the page's own animations, which never
 * reach the user agent shadow tree.
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
	await expect.poll(() => loadingRing(page), { timeout: 15_000 }).toBe('idle');
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

/**
 * A full page picture as screenshots/<name>-<variant>.png (under
 * AVS_SCREENSHOT_DIR instead when set: the step @phase4 keeps its pictures
 * apart for the artifact phase4-screens). The variant is the
 * project name; a test that switches width and colour scheme itself (the
 * single runs of plan 03-18) names the variant it set, e.g. "w375-dark".
 */
export async function screenshot(page: Page, name: string, testInfo: TestInfo, variant?: string): Promise<void> {
	// Finite animations end, endless ones (the loading ring of the media controls,
	// the shimmer of placeholders) stop, so a picture never shows a moment between states.
	await page.screenshot({
		path: `${process.env.AVS_SCREENSHOT_DIR ?? 'screenshots'}/${name}-${variant ?? testInfo.project.name}.png`,
		fullPage: true,
		animations: 'disabled',
		caret: 'hide',
	});
}

// The tallest picture wholePage takes; the playback page needs about 2000 px at 375 px.
const WHOLE_PAGE_MAX_HEIGHT = 8000;

/**
 * The height the viewport needs so that no inner scroller of the page hides
 * content: the viewport plus the largest overflow of an element that scrolls
 * vertically (#app-content of Nextcloud, the result list of the search).
 */
async function heightWithoutInnerScroll(page: Page): Promise<number> {
	return page.evaluate(() => {
		let overflow = 0;
		for (const element of Array.from(document.querySelectorAll('*'))) {
			const style = getComputedStyle(element);
			if (!['auto', 'scroll', 'overlay'].includes(style.overflowY)) {
				continue;
			}
			overflow = Math.max(overflow, element.scrollHeight - element.clientHeight);
		}
		return Math.ceil(window.innerHeight + overflow);
	});
}

/**
 * A picture of the whole page for the review of phase 4 (owner 16.11.2026).
 * fullPage alone stops at the viewport on Nextcloud: the document never grows,
 * #app-content scrolls inside it, so screenshot() of a playback page is 900 px
 * high whatever lies below. This grows the viewport until no inner scroller
 * overflows (a few rounds, a layout may grow with it), takes the picture with
 * fullPage as well and puts the viewport back.
 */
export async function wholePage(page: Page, name: string, testInfo: TestInfo, variant?: string): Promise<void> {
	const original = page.viewportSize();
	if (original === null) {
		throw new Error('wholePage needs a page with a fixed viewport');
	}
	try {
		let height = original.height;
		for (let round = 0; round < 4; round += 1) {
			const needed = Math.min(WHOLE_PAGE_MAX_HEIGHT, await heightWithoutInnerScroll(page));
			if (needed <= height) {
				break;
			}
			height = needed;
			await page.setViewportSize({ width: original.width, height });
		}
		await screenshot(page, name, testInfo, variant);
	} finally {
		await page.setViewportSize(original);
	}
}

/** A picture of one part of the page (the export section, a banner) under the same naming as screenshot(). */
export async function screenshotPart(locator: Locator, name: string, testInfo: TestInfo, variant?: string): Promise<void> {
	await expect(locator).toBeVisible();
	await locator.screenshot({
		path: `${process.env.AVS_SCREENSHOT_DIR ?? 'screenshots'}/${name}-${variant ?? testInfo.project.name}.png`,
		animations: 'disabled',
		caret: 'hide',
	});
}

/**
 * The pointer leaves the content and nothing keeps the focus: a picture after
 * a click shows the page at rest, not the hover or focus colour of the button
 * clicked last (X5, X6: the TXT button looked darker than SRT and VTT).
 */
export async function restPointerAndFocus(page: Page): Promise<void> {
	await page.mouse.move(0, 0);
	await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
}

// -- the Unified Search dialog (moved here from play.spec.ts for plan 03-18) --

// The provider name in the three catalogue languages (php/l10n). The result
// list carries it as its name: "Audio and video" on 33 and 34, "More from
// Audio and video" on 35 (checked in the CI snapshots of all three).
export const GROUP_NAME = /(^|\s)(Audio and video|Audio und Video|Audio et vidéo)$/;

/**
 * Open the Unified Search from the header, the way a user does. Nextcloud 33
 * has a header button "Unified search"; 34 and 35 put the trigger into a
 * search landmark: a button on narrow screens and on wide 34, the combobox
 * itself on wide 35.
 */
export async function openUnifiedSearch(page: Page): Promise<void> {
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
export function searchField(page: Page) {
	return page
		.getByRole('dialog')
		.locator('input[type="search"], input[type="text"]')
		.or(page.locator('.unified-search-modal-root input[type="search"]'))
		.or(page.getByRole('search').getByRole('combobox'))
		.first();
}

// Nextcloud 33 to 35 wait this long after the last keystroke before they
// search: debounce(this.find, 300) in core/src/components/UnifiedSearch/UnifiedSearchModal.vue.
const SEARCH_DEBOUNCE_MS = 300;
const PROVIDER_SEARCH = '/search/providers/audio_video_search/search?';

/**
 * Note in the page when the query was typed and when each search of this
 * provider started, both on the clock of the page. A resource entry only
 * arrives once its response is complete, and observers see it even when the
 * resource timing buffer of the page is full.
 */
export async function watchProviderSearches(page: Page): Promise<void> {
	await page.evaluate((path) => {
		const state = window as unknown as { avsInputAt: number; avsSearchStarts: number[] };
		state.avsInputAt = Number.POSITIVE_INFINITY;
		state.avsSearchStarts = [];
		document.addEventListener('input', () => {
			state.avsInputAt = performance.now();
		}, true);
		new PerformanceObserver((list) => {
			for (const entry of list.getEntries()) {
				if (entry.name.includes(path)) {
					state.avsSearchStarts.push(entry.startTime);
				}
			}
		}).observe({ type: 'resource' });
	}, PROVIDER_SEARCH);
}

/**
 * Wait for the search that answers the typed query, not an earlier one. On 35
 * the modal opens with the first keystroke on wide screens and loads its
 * providers then; when they arrive before the debounce runs out, the modal
 * searches at once (the open watcher calls find()) and clears its busy flag,
 * shows the results with no placeholder, and 300 ms after the keystroke the
 * debounced find() empties the list and searches a second time. Whichever
 * search comes last starts at least the debounce after the keystroke, so the
 * hit counts only once such a search of this provider has come back.
 */
export async function expectFinalSearchDone(page: Page): Promise<void> {
	await expect
		.poll(
			() =>
				page.evaluate((debounce) => {
					const state = window as unknown as { avsInputAt: number; avsSearchStarts: number[] };
					return state.avsSearchStarts.some((start) => start >= state.avsInputAt + debounce);
				}, SEARCH_DEBOUNCE_MS),
			{ timeout: 15_000 },
		)
		.toBe(true);
}

/** Open the Unified Search, type the term and answer the group of this provider once the last search came back. */
export async function searchInDialog(page: Page, term: string) {
	await watchProviderSearches(page);
	await openUnifiedSearch(page);

	const input = searchField(page);
	await expect(input).toBeVisible();
	await input.fill(term);
	await expectFinalSearchDone(page);

	// A list on 33, 34 and narrow 35, a listbox on wide 35.
	const group = page.getByRole('list', { name: GROUP_NAME }).or(page.getByRole('listbox', { name: GROUP_NAME }));
	await expect(group).toBeVisible();
	return group;
}

/**
 * Open the Unified Search, type the term and answer once the last search came
 * back: the group of this provider is not there. A term without a hit never
 * renders the group, which no visibility wait could tell apart from a slow
 * search; the resource timing of the provider says when the search is over.
 */
export async function searchInDialogEmpty(page: Page, term: string): Promise<void> {
	await watchProviderSearches(page);
	await openUnifiedSearch(page);

	const input = searchField(page);
	await expect(input).toBeVisible();
	await input.fill(term);
	await expectFinalSearchDone(page);

	const group = page.getByRole('list', { name: GROUP_NAME }).or(page.getByRole('listbox', { name: GROUP_NAME }));
	await expect(group).toHaveCount(0);
}

// -- phase 3 (plan 03-18) ----------------------------------------------------------

/**
 * Run occ of the test instance and answer its output. The step @preview of
 * deploy-harp.yml sets AVS_OCC to the occ of the server checkout.
 */
export function occ(...args: string[]): string {
	const bin = env('AVS_OCC');
	return execFileSync(bin, args, { cwd: dirname(bin), encoding: 'utf8', timeout: 120_000 });
}

/** A colour with channels 0 to 255 and alpha 0 to 1. */
export type Rgba = { r: number; g: number; b: number; a: number };

const HEX_COLOUR = /^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
const FUNCTION_COLOUR = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)\s*(?:[,/]\s*([\d.]+%?)\s*)?\)$/i;

/**
 * A colour as getComputedStyle writes it (rgb(), rgba(), the space form with
 * a slash, transparent) or as hex. Anything else throws: a colour this cannot
 * read must fail the measurement, never pass as black or white.
 */
export function parseColor(text: string): Rgba {
	const value = text.trim();
	if (value.toLowerCase() === 'transparent') {
		return { r: 0, g: 0, b: 0, a: 0 };
	}
	const hex = HEX_COLOUR.exec(value);
	if (hex !== null) {
		const digits = hex[1].length === 3 ? [...hex[1]].map((digit) => digit + digit).join('') : hex[1];
		const channel = (at: number) => Number.parseInt(digits.slice(at, at + 2), 16);
		return { r: channel(0), g: channel(2), b: channel(4), a: digits.length === 8 ? channel(6) / 255 : 1 };
	}
	const fn = FUNCTION_COLOUR.exec(value);
	if (fn !== null) {
		const alpha = fn[4] === undefined ? 1 : fn[4].endsWith('%') ? Number.parseFloat(fn[4]) / 100 : Number.parseFloat(fn[4]);
		return { r: Number(fn[1]), g: Number(fn[2]), b: Number(fn[3]), a: alpha };
	}
	throw new Error(`colour not readable for the contrast measurement: ${text}`);
}

/** The colour that shows when top lies over an opaque bottom (source over). */
export function composite(top: Rgba, bottom: Rgba): Rgba {
	const mix = (upper: number, lower: number) => upper * top.a + lower * (1 - top.a);
	return { r: mix(top.r, bottom.r), g: mix(top.g, bottom.g), b: mix(top.b, bottom.b), a: 1 };
}

/** Relative luminance after WCAG 2.1 (definition "relative luminance", sRGB). */
function relativeLuminance(colour: Rgba): number {
	const linear = (channel: number) => {
		const c = channel / 255;
		return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
	};
	return 0.2126 * linear(colour.r) + 0.7152 * linear(colour.g) + 0.0722 * linear(colour.b);
}

/**
 * The contrast ratio after WCAG 2.1, (L1 + 0.05) / (L2 + 0.05) with the
 * lighter colour on top. A foreground with alpha is laid over the background
 * first; the background has to be opaque.
 */
export function contrastRatio(fg: string | Rgba, bg: string | Rgba): number {
	const background = typeof bg === 'string' ? parseColor(bg) : bg;
	if (background.a !== 1) {
		throw new Error('the background of a contrast measurement has to be opaque');
	}
	const foreground = composite(typeof fg === 'string' ? parseColor(fg) : fg, background);
	const [light, dark] = [relativeLuminance(foreground), relativeLuminance(background)].sort((x, y) => y - x);
	return (light + 0.05) / (dark + 0.05);
}

/**
 * The contrast of the preview note (.avs-excerpt__note) on the excerpt block,
 * from the computed colours: the text colour of the note against the
 * background colours from the note up to the root, laid over each other on a
 * white canvas. In practice section.avs-excerpt carries an opaque
 * --color-background-hover and decides alone; the colours go into the
 * annotation, so a surprise is visible in the report.
 */
export async function excerptNoteContrast(page: Page): Promise<{ ratio: number; fg: string; backgrounds: string[] }> {
	return textContrast(page.locator('section.avs-excerpt p.avs-excerpt__note'));
}

/**
 * The contrast of the text of one element after the same rule as
 * excerptNoteContrast: its text colour against the background colours from
 * the element up to the root, laid over each other on a white canvas.
 */
export async function textContrast(locator: Locator): Promise<{ ratio: number; fg: string; backgrounds: string[] }> {
	const colours = await locator.evaluate((node) => {
		const backgrounds: string[] = [];
		for (let element: Element | null = node; element !== null; element = element.parentElement) {
			backgrounds.push(getComputedStyle(element).backgroundColor);
		}
		return { fg: getComputedStyle(node).color, backgrounds };
	});
	let background = parseColor('#ffffff');
	for (const layer of [...colours.backgrounds].reverse()) {
		background = composite(parseColor(layer), background);
	}
	return { ratio: contrastRatio(colours.fg, background), ...colours };
}

/**
 * The measurement passes its self test first (T-03-60): black on white is
 * 21:1, #767676 on white is just above 4.5:1 and #999999 on white below.
 */
export function expectContrastSelfTest(): void {
	expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 6);
	const justEnough = contrastRatio('#767676', '#ffffff');
	expect(justEnough).toBeGreaterThanOrEqual(4.5);
	expect(justEnough).toBeLessThanOrEqual(4.6);
	expect(contrastRatio('#999999', '#ffffff')).toBeLessThan(4.5);
	expect(contrastRatio('rgb(255, 255, 255)', 'rgb(0, 0, 0)')).toBeCloseTo(21, 6);
}

// -- phase 4 (plan 04-14) ------------------------------------------------------------

/**
 * Switch "allow viewing without download" of the sharing settings. ci/seed.sh
 * leaves it off (locked shares show the hint instead of the medium); a test that
 * turns it on puts it back in finally or afterEach (T-04-52).
 */
export function toggleViewWithoutDownload(on: boolean): void {
	occ('config:app:set', 'core', 'shareapi_allow_view_without_download', `--value=${on ? 'yes' : 'no'}`, '--type=boolean');
}

/** A request context that signs in as the user with basic auth on every request. */
export async function apiAs(user: User): Promise<APIRequestContext> {
	return request.newContext({
		baseURL: process.env.NC_URL ?? 'http://localhost:8080',
		httpCredentials: { username: user.name, password: user.password, send: 'always' },
	});
}

/** The sha256 of a file of the user as WebDAV delivers it, path relative to the user's root. */
export async function sha256OfFile(user: User, path: string): Promise<string> {
	const api = await apiAs(user);
	try {
		const encoded = path.split('/').map(encodeURIComponent).join('/');
		const response = await api.get(`/remote.php/dav/files/${encodeURIComponent(user.name)}/${encoded}`);
		expect(response.status(), `WebDAV GET of ${path}`).toBe(200);
		return createHash('sha256').update(await response.body()).digest('hex');
	} finally {
		await api.dispose();
	}
}

/**
 * Click the locator, take the download it starts and keep it in dir under the
 * name the server suggested; answers the full path and that name. The step
 * @phase4 points dir at AVS_DOWNLOADS_DIR, which tests/test_downloaded_subtitles.py
 * checks afterwards.
 */
export async function downloadTo(page: Page, locator: Locator, dir: string): Promise<{ path: string; name: string }> {
	mkdirSync(dir, { recursive: true });
	const [download] = await Promise.all([page.waitForEvent('download'), locator.click()]);
	const name = download.suggestedFilename();
	const path = join(dir, name);
	await download.saveAs(path);
	return { path, name };
}

export type ExportFormat = 'srt' | 'vtt' | 'txt';

/** The export of one file in one format as the user (the owner, as a rule), over the route of the page. */
export async function exportResponse(user: User, fileId: string, format: ExportFormat): Promise<{ status: number; body: string }> {
	const api = await apiAs(user);
	try {
		const response = await api.get(`${APP_PATH}/export/${fileId}/${format}`);
		return { status: response.status(), body: await response.text() };
	} finally {
		await api.dispose();
	}
}

/** The export as text; anything but 200 throws with the status. */
export async function exportText(user: User, fileId: string, format: ExportFormat): Promise<string> {
	const { status, body } = await exportResponse(user, fileId, format);
	if (status !== 200) {
		throw new Error(`export ${format} of file ${fileId} answered ${status}`);
	}
	return body;
}

/** One S7 clip as ci/media/fetch_speech.py measured it (S7Targets), with its file id from the seed. */
export type S7Clip = {
	key: string;
	fileId: string;
	numberWord: string;
	numberForms: readonly string[];
	compound: string;
	head: string;
	plural: string | null;
	singular: string | null;
};

function optional(value: unknown): string | null {
	return value === null || value === undefined ? null : String(value);
}

/**
 * The measured S7 forms out of AVS_S7_TARGETS, which deploy-harp.yml writes
 * with `fetch_speech.py --s7-env`. No sentence of a clip is typed into a spec:
 * a new measurement changes fetch_speech.py and nothing else.
 */
export function s7Expectations(): S7Clip[] {
	const parsed: unknown = JSON.parse(env('AVS_S7_TARGETS'));
	if (!Array.isArray(parsed) || parsed.length === 0) {
		throw new Error('AVS_S7_TARGETS holds no clip');
	}
	return parsed.map((item: Record<string, unknown>) => {
		const key = String(item.key);
		const forms = item.number_forms;
		if (!Array.isArray(forms) || forms.length !== 4) {
			throw new Error(`${key}: number_forms must hold digit, DE, EN and FR`);
		}
		return {
			key,
			fileId: env(`FILEID_${key}`),
			numberWord: String(item.number_word),
			numberForms: forms.map(String),
			compound: String(item.compound),
			head: String(item.head),
			plural: optional(item.plural),
			singular: optional(item.singular),
		};
	});
}

/** Tokens the way the model test compares them: lower case, letters and digits only. */
export function foldedTokens(text: string): Set<string> {
	return new Set(
		text
			.toLowerCase()
			.split(/\s+/u)
			.map((part) => part.replace(/[^\p{L}\p{N}]/gu, ''))
			.filter((part) => part !== ''),
	);
}

/** One token folded like foldedTokens. */
export function fold(word: string): string {
	return word.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
}

// -- phase 4, export and sidecar (plan 04-17) ------------------------------------------

/** The name alice gave the video of the seed (with an umlaut, D1), and the folder of the sidecar share. */
export const S7_VIDEO_NAME = 'S7-Übung.webm';
/**
 * The base of every export name of that video: the umlaut is spelled out in
 * the name of a download and a sidecar (owner 17.11.2026, UAT 04 test 5). A
 * literal on purpose, not derived from S7_VIDEO_NAME, so the check does not
 * repeat the pattern of the implementation.
 */
export const S7_EXPORT_BASE = 'S7-Uebung';
export const ABLAGE_FOLDER = 'Ablage';
export const ABLAGE_FILE = 's7-ablage.wav';
/** The transcript language of both: the speech of S7_DE and S7_DE_DIGIT is German (fetch_speech.py). */
export const S7_LANGUAGE = 'de';

export type Language = 'en' | 'de' | 'fr';
export type Texts = Record<Language, string>;

// The texts of 04-UI-SPEC (Copywriting Contract, approved by the owner on
// 2026-11-16) and the stock key it names, copied from its tables, never
// written here: the test has to see what the owner approved. The catalogues
// themselves (php/l10n) are held to the same wording by the backend gates.
export const EXPORT_TEXTS = {
	T13: { de: 'Untertitel-Entwurf', en: 'Subtitle draft', fr: 'Brouillon de sous-titres' },
	T14: {
		de: 'Automatisch erstellt und nicht geprüft. SRT und VTT enthalten Zeitmarken, TXT nur den Text.',
		en: 'Created automatically and not reviewed. SRT and VTT contain time marks, TXT only the text.',
		fr: 'Créé automatiquement et non vérifié. SRT et VTT contiennent des repères temporels, TXT uniquement le texte.',
	},
	T15: {
		de: 'Transkript bis %s, Datei wird noch verarbeitet.',
		en: 'Transcript up to %s, the file is still being processed.',
		fr: "Transcription jusqu'à %s, le fichier est encore en cours de traitement.",
	},
	T16: { de: 'SRT herunterladen', en: 'Download SRT', fr: 'Télécharger le SRT' },
	T17: { de: 'VTT herunterladen', en: 'Download VTT', fr: 'Télécharger le VTT' },
	T18: { de: 'TXT herunterladen', en: 'Download TXT', fr: 'Télécharger le TXT' },
	T19: { de: 'Neben die Datei legen', en: 'Save next to the file', fr: 'Enregistrer à côté du fichier' },
	T20: {
		de: 'Legt %s in denselben Ordner wie die Aufnahme. Eine vorhandene Datei wird nie überschrieben.',
		en: 'Saves %s in the same folder as the recording. An existing file is never overwritten.',
		fr: "Enregistre %s dans le même dossier que l'enregistrement. Un fichier existant n'est jamais remplacé.",
	},
	T21: {
		de: '%s liegt jetzt im selben Ordner wie die Aufnahme.',
		en: '%s is now in the same folder as the recording.',
		fr: "%s se trouve maintenant dans le même dossier que l'enregistrement.",
	},
	T22a: { de: 'Datei existiert bereits', en: 'File already exists', fr: 'Le fichier existe déjà' },
	T22b: {
		de: 'Im Ordner liegt schon eine Datei namens %s. Sie wird nicht überschrieben. Für eine neue Ablage die vorhandene Datei zuerst löschen oder umbenennen.',
		en: 'The folder already contains a file named %s. It is not overwritten. To save again, delete or rename the existing file first.',
		fr: "Le dossier contient déjà un fichier nommé %s. Il n'est pas remplacé. Pour enregistrer à nouveau, supprimez ou renommez d'abord le fichier existant.",
	},
	T23: {
		de: 'In diesem Ordner dürfen keine Dateien angelegt werden. Herunterladen geht trotzdem.',
		en: 'Files cannot be created in this folder. Downloading still works.',
		fr: "Il n'est pas possible de créer des fichiers dans ce dossier. Le téléchargement reste possible.",
	},
	T24: {
		de: 'Diese Freigabe erlaubt keine Downloads. Untertitel und Transkript lassen sich deshalb weder herunterladen noch ablegen.',
		en: 'This share does not allow downloads. Subtitles and transcript can therefore neither be downloaded nor saved.',
		fr: "Ce partage n'autorise pas les téléchargements. Les sous-titres et la transcription ne peuvent donc être ni téléchargés ni enregistrés.",
	},
	T25: {
		de: 'Der Untertitel-Entwurf lässt sich gerade nicht erstellen. Die Wiedergabe funktioniert trotzdem. Später erneut versuchen.',
		en: 'The subtitle draft cannot be created right now. Playback works regardless. Try again later.',
		fr: 'Le brouillon de sous-titres ne peut pas être créé pour le moment. La lecture fonctionne quand même. Réessayez plus tard.',
	},
	T26: {
		de: 'Der Name der Untertiteldatei wäre zu lang. Nach einer Umbenennung der Aufnahme in einen kürzeren Namen erneut versuchen.',
		en: 'The name of the subtitle file would be too long. Rename the recording to a shorter name and try again.',
		fr: "Le nom du fichier de sous-titres serait trop long. Renommez l'enregistrement avec un nom plus court et réessayez.",
	},
	T27: {
		de: 'Zu viele Versuche in kurzer Zeit. Etwas später erneut versuchen.',
		en: 'Too many attempts in a short time. Try again a little later.',
		fr: 'Trop de tentatives en peu de temps. Réessayez un peu plus tard.',
	},
	T29: {
		de: 'Der Untertitel-Entwurf konnte nicht erstellt werden',
		en: 'The subtitle draft could not be created',
		fr: "Le brouillon de sous-titres n'a pas pu être créé",
	},
	T29b: { de: 'Die Untertitel wurden nicht abgelegt', en: 'The subtitles were not saved', fr: "Les sous-titres n'ont pas été enregistrés" },
	T30: { de: 'Zurück zur Wiedergabe', en: 'Back to playback', fr: 'Retour à la lecture' },
	T31: { de: '%s, Untertitel-Entwurf', en: '%s, subtitle draft', fr: '%s, brouillon de sous-titres' },
	T32: { de: 'Deutsch', en: 'German', fr: 'Allemand' },
	T35: {
		de: 'Untertitel-Entwurf, automatisch erstellt und nicht geprüft.',
		en: 'Subtitle draft, created automatically and not reviewed.',
		fr: 'Brouillon de sous-titres, créé automatiquement et non vérifié.',
	},
	// Stock key "Show in Files" with the wording of the catalogues (04-UI-SPEC, owner answer).
	SHOW_IN_FILES: { de: 'In Dateien anzeigen', en: 'Show in Files', fr: 'Afficher dans Fichiers' },
	// Stock text A5 (04-UI-SPEC, "Unverändert weiterverwendete Texte"): no transcript, and every exclusion.
	A5: {
		de: 'Für diese Datei gibt es noch kein Transkript.',
		en: 'There is no transcript for this file yet.',
		fr: "Il n'y a pas encore de transcription pour ce fichier.",
	},
} as const satisfies Record<string, Texts>;

/** A text with its one placeholder %s filled. */
export function fill(text: string, value: string): string {
	return text.replace('%s', value);
}

/**
 * The user and display language of a project for the specs of plan 04-17:
 * the basic matrix of 04-UI-SPEC is German (elke, de_DE), the French project
 * reads as fleur, high contrast as dora. dora reads English in the seed (her
 * theme is the point of her), so a test of the high contrast project runs
 * inside withLanguage(): 04-UI-SPEC wants the high contrast pictures in German
 * too (owner 16.11.2026). All three are in the group "review", which receives
 * S7-Übung.webm and s7-zahlwort.wav.
 */
export function phase4User(testInfo: TestInfo): { user: User; language: Language } {
	if (isHighContrast(testInfo)) {
		return { user: users.dora(), language: 'de' };
	}
	if (testInfo.project.metadata?.language === 'fr') {
		return { user: users.fleur(), language: 'fr' };
	}
	return { user: users.elke(), language: 'de' };
}

// The settings ci/seed.sh gives elke and fleur, for every language a test can ask for.
const USER_LANGUAGE: Record<Language, { lang: string; locale: string }> = {
	de: { lang: 'de_DE', locale: 'de_DE' },
	en: { lang: 'en', locale: 'en_US' },
	fr: { lang: 'fr', locale: 'fr_FR' },
};

/** One core setting of a user by occ, or null when the user has none (occ answers 1 then). */
function coreSetting(uid: string, key: string): string | null {
	try {
		return occ('user:setting', uid, 'core', key).trim();
	} catch (error) {
		if ((error as { status?: number }).status === 1) {
			return null;
		}
		throw error;
	}
}

function restoreCoreSetting(uid: string, key: string, value: string | null): void {
	if (value === null) {
		occ('user:setting', '--delete', uid, 'core', key);
	} else {
		occ('user:setting', uid, 'core', key, value);
	}
}

/**
 * Run body with the user reading the given language (core lang and locale by
 * occ, the way ci/seed.sh sets elke and fleur) and put both settings back in
 * finally (T-04-52). The review pictures of phase 4 are German (04-UI-SPEC,
 * owner 16.11.2026), also where the state needs alice, carol or dora, who read
 * English everywhere else. One worker runs the specs, so no other test meets
 * the user in the meantime. Set it before the login of the user.
 */
export async function withLanguage<T>(user: User, language: Language, body: () => Promise<T>): Promise<T> {
	const wanted = USER_LANGUAGE[language];
	const before = { lang: coreSetting(user.name, 'lang'), locale: coreSetting(user.name, 'locale') };
	if (before.lang === wanted.lang && before.locale === wanted.locale) {
		return body();
	}
	occ('user:setting', user.name, 'core', 'lang', wanted.lang);
	occ('user:setting', user.name, 'core', 'locale', wanted.locale);
	try {
		return await body();
	} finally {
		restoreCoreSetting(user.name, 'lang', before.lang);
		restoreCoreSetting(user.name, 'locale', before.locale);
	}
}

/** The name of the export of a file: last extension cut, then language and format (D-04-04). */
export function exportName(fileName: string, format: ExportFormat, language = S7_LANGUAGE): string {
	const dot = fileName.lastIndexOf('.');
	const base = dot <= 0 ? fileName : fileName.slice(0, dot);
	return `${base}.${language}.${format}`;
}

/** The export name of the S7 video, umlaut spelled out: "S7-Uebung.de.vtt". */
export function s7ExportName(format: ExportFormat, language = S7_LANGUAGE): string {
	return `${S7_EXPORT_BASE}.${language}.${format}`;
}

/** The playback page of a file at a time mark. */
export function playAt(fileId: string, seconds: number): string {
	return `${APP_PATH}/play/${fileId}?t=${seconds}`;
}

/** The export, track and sidecar addresses of a file, built like the routes of ExportController. */
export function exportRoutes(fileId: string): { srt: string; vtt: string; txt: string; track: string; sidecar: string } {
	return {
		srt: `${APP_PATH}/export/${fileId}/srt`,
		vtt: `${APP_PATH}/export/${fileId}/vtt`,
		txt: `${APP_PATH}/export/${fileId}/txt`,
		track: `${APP_PATH}/track/${fileId}`,
		sidecar: `${APP_PATH}/sidecar/${fileId}`,
	};
}

/** A transcript can take minutes after the seed; the export answers 200 once it is there. */
export const TRANSCRIPT_WITHIN_MS = 15 * 60_000;

/** Wait until the export of the file answers 200 for the user: there is a transcript to export. */
export async function expectTranscript(user: User, fileId: string): Promise<void> {
	await expect
		.poll(async () => (await exportResponse(user, fileId, 'txt')).status, {
			message: `file ${fileId} has no transcript for ${user.name} after ${TRANSCRIPT_WITHIN_MS / 60_000} min`,
			timeout: TRANSCRIPT_WITHIN_MS,
			intervals: [10_000],
		})
		.toBe(200);
}

/** The request token of the page, the way play.js reads it for the POST of the sidecar. */
export async function requestToken(page: Page): Promise<string> {
	return page.evaluate(() => document.head.dataset.requesttoken ?? '');
}

/** A width and a colour scheme: one picture of a page without loading it again. */
export type Variant = readonly [number, 'light' | 'dark'];
export const ALL_VARIANTS: readonly Variant[] = [
	[375, 'light'],
	[375, 'dark'],
	[768, 'light'],
	[768, 'dark'],
	[1280, 'light'],
	[1280, 'dark'],
];

/**
 * Pictures of the whole page as it stands in the given widths and schemes (the
 * pattern of preview.spec.ts shots()), waiting for the anchor before each, and
 * when a part is given a picture of that part as well (<partName>-w<width>-<scheme>);
 * the page goes back to 1280 px light afterwards.
 */
export async function screenshotVariants(
	page: Page,
	name: string,
	testInfo: TestInfo,
	variants: readonly Variant[],
	anchor: Locator,
	part?: readonly [string, Locator],
): Promise<void> {
	for (const [width, colorScheme] of variants) {
		await page.setViewportSize({ width, height: 900 });
		await page.emulateMedia({ colorScheme });
		await expect(anchor).toBeVisible();
		await wholePage(page, name, testInfo, `w${width}-${colorScheme}`);
		if (part !== undefined) {
			await screenshotPart(part[1], part[0], testInfo, `w${width}-${colorScheme}`);
		}
	}
	await page.setViewportSize({ width: 1280, height: 900 });
	await page.emulateMedia({ colorScheme: 'light' });
}

/** Sign in as another user in the same page; leave the app first, so its background requests start no new session. */
export async function switchUser(page: Page, user: User): Promise<void> {
	await page.goto('about:blank');
	await page.context().clearCookies();
	await login(page, user);
}

/** WebDAV DELETE of a file of the user; answers the status (204 deleted, 404 not there). */
export async function deleteFile(user: User, path: string): Promise<number> {
	const api = await apiAs(user);
	try {
		const encoded = path.split('/').map(encodeURIComponent).join('/');
		const response = await api.delete(`/remote.php/dav/files/${encodeURIComponent(user.name)}/${encoded}`);
		return response.status();
	} finally {
		await api.dispose();
	}
}

/** Upload a file by WebDAV into a folder of the user (made when missing) and answer its file id. */
export async function uploadTo(user: User, folder: string, name: string, data: Buffer, contentType: string): Promise<string> {
	const api = await apiAs(user);
	try {
		const base = `/remote.php/dav/files/${encodeURIComponent(user.name)}/${encodeURIComponent(folder)}`;
		const made = await api.fetch(base, { method: 'MKCOL' });
		// 201 created, 405 when the folder is already there.
		expect([201, 405]).toContain(made.status());
		const target = `${base}/${encodeURIComponent(name)}`;
		const put = await api.put(target, { data, headers: { 'Content-Type': contentType }, timeout: 120_000 });
		expect([201, 204]).toContain(put.status());
		const found = await api.fetch(target, {
			method: 'PROPFIND',
			headers: { Depth: '0', 'Content-Type': 'application/xml' },
			data:
				'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">' +
				'<d:prop><oc:fileid/></d:prop></d:propfind>',
		});
		expect(found.status()).toBe(207);
		const fileId = /<oc:fileid>(\d+)<\/oc:fileid>/.exec(await found.text())?.[1];
		expect(fileId, 'PROPFIND answers oc:fileid').toBeDefined();
		return fileId as string;
	} finally {
		await api.dispose();
	}
}

// -- shares of the owner, over the sharing API ------------------------------------------

const SHARES_API = '/ocs/v2.php/apps/files_sharing/api/v1/shares';
const OCS_HEADERS = { 'OCS-APIRequest': 'true', Accept: 'application/json' };

/** The id of the share of path to shareWith that the owner made, or null. */
export async function findShare(owner: User, path: string, shareWith: string): Promise<string | null> {
	const api = await apiAs(owner);
	try {
		const response = await api.get(`${SHARES_API}?path=${encodeURIComponent(path)}`, { headers: OCS_HEADERS });
		expect(response.status(), `shares of ${path}`).toBe(200);
		const body = await response.json();
		const shares: Array<{ id: string | number; share_with: string }> = body.ocs.data;
		const share = shares.find((item) => item.share_with === shareWith);
		return share === undefined ? null : String(share.id);
	} finally {
		await api.dispose();
	}
}

/** The share of path to shareWith, made by the owner when it is not there yet; answers its id. */
export async function ensureShare(owner: User, path: string, shareWith: string, shareType: 0 | 1, permissions: number): Promise<string> {
	const found = await findShare(owner, path, shareWith);
	if (found !== null) {
		return found;
	}
	const api = await apiAs(owner);
	try {
		const response = await api.post(SHARES_API, {
			headers: OCS_HEADERS,
			form: { path, shareWith, shareType: String(shareType), permissions: String(permissions) },
		});
		expect(response.status(), `share of ${path} with ${shareWith}`).toBe(200);
		const body = await response.json();
		return String(body.ocs.data.id);
	} finally {
		await api.dispose();
	}
}

/** Change one share of the owner: permissions and/or the download attribute (OCS PUT). */
export async function updateShare(owner: User, id: string, change: { permissions?: number; download?: boolean }): Promise<void> {
	const form: Record<string, string> = {};
	if (change.permissions !== undefined) {
		form.permissions = String(change.permissions);
	}
	if (change.download !== undefined) {
		form.attributes = JSON.stringify([{ scope: 'permissions', key: 'download', value: change.download }]);
	}
	const api = await apiAs(owner);
	try {
		const response = await api.put(`${SHARES_API}/${encodeURIComponent(id)}`, { headers: OCS_HEADERS, form });
		expect(response.status(), `update of share ${id}`).toBe(200);
	} finally {
		await api.dispose();
	}
}

/** Read, update, create, delete: the right of carol on alice's folder Ablage from ci/seed.sh. */
export const ABLAGE_PERMISSIONS = 15;
export const READ_ONLY = 1;

/** The share of alice's folder Ablage with carol from ci/seed.sh. */
export async function ablageShare(): Promise<string> {
	const id = await findShare(users.alice(), `/${ABLAGE_FOLDER}`, 'carol');
	expect(id, 'ci/seed.sh shared the folder Ablage with carol').not.toBeNull();
	return id as string;
}

/** Exclude a user from the app by occ, or take the rule away again (T-04-52: always in finally). */
export function excludeUser(uid: string, on: boolean): void {
	occ('audio_video_search:exclude', `--user=${uid}`, ...(on ? [] : ['--remove']));
}

// -- the container of the backend (the way of the @unreachable step) ---------------------

const HARP_URL = process.env.AVS_HARP_URL ?? 'http://localhost:8090';
const BACKEND_APP_ID = process.env.BACKEND_APP_ID ?? 'audio_video_search_backend';
/** The container is back within this time, or the run fails (the @unreachable step waits 120 s). */
const CONTAINER_BACK_MS = 3 * 60_000;

/** Stop the container of the backend; docker stop returns once it is down. */
export function stopContainer(): void {
	execFileSync('docker', ['stop', env('EXAPP_CONTAINER')], { encoding: 'utf8', timeout: 120_000 });
}

/**
 * Start the container again and wait for its heartbeat: the status route of
 * HaRP answers 200 once AppAPI reaches the backend (the loop of the
 * @unreachable step of deploy-harp.yml, as expect.poll instead of sleep).
 */
export async function startContainer(): Promise<void> {
	execFileSync('docker', ['start', env('EXAPP_CONTAINER')], { encoding: 'utf8', timeout: 120_000 });
	const admin = users.admin();
	const api = await request.newContext({
		baseURL: HARP_URL,
		httpCredentials: { username: admin.name, password: admin.password, send: 'always' },
	});
	try {
		await expect
			.poll(
				async () => {
					try {
						return (await api.get(`/exapps/${BACKEND_APP_ID}/status`)).status();
					} catch {
						return 0;
					}
				},
				{ message: 'the backend container did not come back', timeout: CONTAINER_BACK_MS, intervals: [2_000] },
			)
			.toBe(200);
	} finally {
		await api.dispose();
	}
}

/**
 * Run body with the container stopped and start it again in finally (T-04-52),
 * then wait until the export of a file answers 200 again, so the next test
 * meets a backend that serves.
 */
export async function withContainerStopped(body: () => Promise<void>, readyAs: User, readyFileId: string): Promise<void> {
	stopContainer();
	try {
		await body();
	} finally {
		await startContainer();
		await expect
			.poll(async () => (await exportResponse(readyAs, readyFileId, 'txt')).status, {
				message: 'the export did not answer again after the container came back',
				timeout: CONTAINER_BACK_MS,
				intervals: [2_000],
			})
			.toBe(200);
	}
}

/**
 * The HTML of the playback column from the excerpt block on (the excerpt
 * block and everything after it, text nodes included) and the tail after the
 * excerpt block alone: X4 compares these byte for byte.
 */
export async function columnFromExcerpt(page: Page): Promise<{ fromExcerpt: string; tail: string }> {
	return page.locator('section.avs-excerpt').evaluate((excerpt) => {
		let tail = '';
		for (let node = excerpt.nextSibling; node !== null; node = node.nextSibling) {
			tail += node.nodeType === Node.ELEMENT_NODE ? (node as Element).outerHTML : (node.textContent ?? '');
		}
		return { fromExcerpt: excerpt.outerHTML + tail, tail };
	});
}

/** The first cue of a WebVTT text: start in seconds and text, after the header and the NOTE block. */
export function firstCue(vtt: string): { start: number; text: string } {
	const blocks = vtt.replace(/\r\n/g, '\n').split(/\n{2,}/);
	for (const block of blocks) {
		const lines = block.split('\n');
		const timing = lines.findIndex((line) => line.includes('-->'));
		if (timing === -1) {
			continue;
		}
		const start = /^\s*(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})\s+-->/.exec(lines[timing]);
		if (start === null) {
			throw new Error(`cue timing not readable: ${lines[timing]}`);
		}
		const seconds = Number(start[1] ?? '0') * 3600 + Number(start[2]) * 60 + Number(start[3]) + Number(start[4]) / 1000;
		return { start: seconds, text: lines.slice(timing + 1).join('\n') };
	}
	throw new Error('the VTT holds no cue');
}

/** The lines of the NOTE block of a WebVTT text (empty without one). */
export function noteLines(vtt: string): string[] {
	const blocks = vtt.replace(/\r\n/g, '\n').split(/\n{2,}/);
	const note = blocks.find((block) => block.startsWith('NOTE'));
	return note === undefined ? [] : note.split('\n').slice(1);
}

// -- axe (plan 04-17, Owner 16.11.2026: @axe-core/playwright 4.14.0, exact pin) --

/** The rules axe runs: WCAG 2.0, 2.1 and 2.2 on levels A and AA. */
export const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
// 04-17: no finding of these weights on X1 to X5, E1 to E7 and D2.
const AXE_BLOCKING = new Set(['serious', 'critical']);
// The content of the app on the playback page and on the error page of the
// download; the frame of Nextcloud around it is not ours to judge.
const AXE_SCOPE = '#app-content.avs-play';

type AxeFinding = { id: string; impact?: string | null; nodes: { target: unknown[] }[] };

/** The serious and critical findings of an axe run, one line each: rule, weight and the elements. */
export function blockingAxeFindings(violations: readonly AxeFinding[]): string[] {
	return violations
		.filter((violation) => violation.impact != null && AXE_BLOCKING.has(violation.impact))
		.map((violation) => `${violation.id} (${violation.impact}): ${violation.nodes.map((node) => node.target.map(String).join(' ')).join(', ')}`);
}

/** One axe run over the content of the app; the whole list of findings goes into the report. */
async function runAxe(page: Page, id: string, testInfo: TestInfo): Promise<{ violations: AxeFinding[]; passes: number }> {
	const results = await new AxeBuilder({ page }).include(AXE_SCOPE).withTags(AXE_TAGS).analyze();
	await testInfo.attach(`axe-${id}-${testInfo.project.name}.json`, {
		body: JSON.stringify({ url: results.url, violations: results.violations, incomplete: results.incomplete.map((item) => item.id) }, null, 2),
		contentType: 'application/json',
	});
	return { violations: results.violations, passes: results.passes.length };
}

/**
 * axe on the state the page shows now: no serious or critical finding. The
 * run must have looked at something (rules passed), so an empty scope can
 * never pass as clean.
 */
export async function expectAxeClean(page: Page, id: string, testInfo: TestInfo): Promise<void> {
	await expect(page.locator(AXE_SCOPE)).toBeAttached();
	const { violations, passes } = await runAxe(page, id, testInfo);
	expect(passes, `axe ${id}: the run checked no rule on ${AXE_SCOPE}`).toBeGreaterThan(0);
	expect(blockingAxeFindings(violations), `axe ${id}: serious or critical findings`).toEqual([]);
}

/**
 * Positive control of the axe gate: a button without a name and an image
 * without alt, put into the scope of the page shown now, must come back as
 * critical findings through the same filter expectAxeClean uses. Removes
 * both again, so the page is unchanged afterwards.
 */
export async function expectAxeSelfTest(page: Page, testInfo: TestInfo): Promise<void> {
	await page.locator(AXE_SCOPE).evaluate((scope) => {
		const button = document.createElement('button');
		button.id = 'avs-axe-probe-button';
		const image = document.createElement('img');
		image.id = 'avs-axe-probe-image';
		image.src = 'data:image/gif;base64,R0lGODlhAQABAAAAACw=';
		scope.append(button, image);
	});
	try {
		const { violations } = await runAxe(page, 'self-test', testInfo);
		const found = blockingAxeFindings(violations);
		expect(found.some((line) => line.startsWith('button-name ') && line.includes('#avs-axe-probe-button')), 'axe finds the button without a name').toBe(true);
		expect(found.some((line) => line.startsWith('image-alt ') && line.includes('#avs-axe-probe-image')), 'axe finds the image without alt').toBe(true);
	} finally {
		await page.evaluate(() => {
			document.getElementById('avs-axe-probe-button')?.remove();
			document.getElementById('avs-axe-probe-image')?.remove();
		});
	}
}
