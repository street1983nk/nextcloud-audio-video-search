// Shared pieces of the end-to-end specs: the users and file ids of ci/seed.sh,
// the login, the OCS search as a user, the Unified Search dialog, the media
// position, the screenshots, occ of the test instance and the contrast
// measurement of plan 03-18, and the pieces of phase 4 (plan 04-14): the admin
// switch for viewing without download, sha256 of a file over WebDAV, a
// download into a folder, the export as text and the measured S7 forms.
//
// No fixed waits anywhere: web-first assertions, waitForResponse and
// expect.poll only.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { expect, request, test, type APIRequestContext, type Locator, type Page, type TestInfo } from '@playwright/test';

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
	const colours = await page.locator('section.avs-excerpt p.avs-excerpt__note').evaluate((note) => {
		const backgrounds: string[] = [];
		for (let element: Element | null = note; element !== null; element = element.parentElement) {
			backgrounds.push(getComputedStyle(element).backgroundColor);
		}
		return { fg: getComputedStyle(note).color, backgrounds };
	});
	let background = parseColor('#ffffff');
	for (const layer of [...colours.backgrounds].reverse()) {
		background = composite(parseColor(layer), background);
	}
	return { ratio: contrastRatio(colours.fg, background), ...colours };
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

async function apiAs(user: User): Promise<APIRequestContext> {
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
