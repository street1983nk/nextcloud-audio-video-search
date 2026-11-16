// Phase 4, the export section of the playback page and the error page of the
// download in the real stack (plan 04-17, 04-UI-SPEC "Prüfvertrag": X1 to X6,
// D1, D2; success criteria 3 and the export part of 5).
//
// The selectors come from php/templates/play.php and export_error.php and the
// data contract of 04-UI-SPEC (section.avs-export, a.avs-export__download,
// p.avs-export__note, p.avs-export__hint, p.avs-export__partial with its
// <time>, #avs-sidecar, <track kind="subtitles">, the error banner with its
// action); the routes come from ExportController. Every visible text is one of
// the approved texts of 04-UI-SPEC (EXPORT_TEXTS in helpers.ts).
//
// The media come from ci/seed.sh (AVS_PHASE4_MEDIA=1): S7-Übung.webm (the
// S7_DE speech as a video, shared with the group "review" with download),
// s7-zahlwort.wav (shared with "review" with the download switched off),
// s7-ziffer.wav and the folder Ablage shared with carol. The partial window of
// X2 needs a file in work, so this spec uploads lang-40min-x2.ogg itself.
//
// Everything that changes the instance (the view-without-download switch, an
// exclusion, the rights of a share, the stopped container) is put back in a
// finally block (T-04-52). No fixed waits: web-first assertions,
// waitForResponse, waitForEvent and expect.poll only.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test';
import {
	ABLAGE_FILE,
	ABLAGE_PERMISSIONS,
	ablageShare,
	ALL_VARIANTS,
	columnFromExcerpt,
	downloadTo,
	ensureShare,
	expectAxeClean,
	EXPORT_TEXTS as T,
	excludeUser,
	exportName,
	exportRoutes,
	expectTranscript,
	fileIds,
	fill,
	login,
	noteLines,
	parseColor,
	phase4User,
	playAt,
	READ_ONLY,
	requestToken,
	S7_VIDEO_NAME,
	screenshot,
	screenshotVariants,
	switchUser,
	toggleViewWithoutDownload,
	TRANSCRIPT_WITHIN_MS,
	updateShare,
	uploadTo,
	users,
	withContainerStopped,
	type ExportFormat,
	type Language,
} from './helpers';

test.skip(process.env.AVS_PHASE4_E2E !== '1', 'phase 4 runs in the step @phase4 of deploy-harp.yml');

const GRID = ['w375-light', 'w375-dark', 'w768-light', 'w768-dark', 'w1280-light', 'w1280-dark'];
const ONCE = 'w1280-light';
// 04-UI-SPEC: X1 in the grid, French at 375 px and high contrast; X3 at 1280 light and dark and 375 light.
const X1_PROJECTS = [...GRID, 'hc-1280', 'fr-w375-light'];
const X3_PROJECTS = ['w1280-light', 'w1280-dark', 'w375-light'];
const FORMATS: readonly ExportFormat[] = ['srt', 'vtt', 'txt'];
// The media types of ExportController::MIME_TYPES (research: subtitles over HTTP).
const MIME: Record<ExportFormat, string> = {
	srt: 'application/x-subrip; charset=utf-8',
	vtt: 'text/vtt; charset=utf-8',
	txt: 'text/plain; charset=utf-8',
};
const DOWNLOAD_NAME = /^.+\.(de|en|fr)\.(srt|vtt|txt)$/;
// A mark inside the S7 clips (8 to 23 s): the page is a ready page with a medium.
const START_SECONDS = 1;
// The partial window of a 40 min file lasts minutes; look every 2 s (as in phase 3).
const PARTIAL_WITHIN_MS = 10 * 60_000;
const PARTIAL_POLL_MS = 2_000;
const X2_FOLDER = 'phase4';
const X2_FILE = 'lang-40min-x2.ogg';
const EARLY_SECONDS = 6;
// The time mark of D2: the way back of the error page keeps it.
const D2_MARK = '12.5';
const PREPARED_MS = TRANSCRIPT_WITHIN_MS + 5 * 60_000;

function only(testInfo: TestInfo, projects: readonly string[]): void {
	test.skip(!projects.includes(testInfo.project.name), `this state is pictured in ${projects.join(', ')}`);
}

function required(name: string): string {
	const value = process.env[name];
	if (value === undefined || value === '') {
		throw new Error(`${name} is not set; the step @phase4 of deploy-harp.yml sets it`);
	}
	return value;
}

const section = (page: Page): Locator => page.locator('section.avs-export');
const downloadLinks = (page: Page): Locator => section(page).locator('a.avs-export__download');
const sidecarHint = (page: Page): Locator => section(page).locator('.avs-export__sidecar > p.avs-export__hint');
const partialNote = (page: Page): Locator => section(page).locator('p.avs-export__partial');

/** The href of every download link, in the order of the page. */
async function hrefs(page: Page): Promise<string[]> {
	return downloadLinks(page).evaluateAll((links) => links.map((link) => link.getAttribute('href') ?? ''));
}

/** The format at the end of an export address. */
function formatOf(href: string): string {
	return new URL(href, 'http://local').pathname.split('/').pop() ?? '';
}

/** The clock of T15 on the page, or null when the section shows no partial note. */
async function partialClock(page: Page): Promise<string | null> {
	const time = partialNote(page).locator('time');
	return (await time.count()) > 0 ? ((await time.textContent()) ?? '').trim() : null;
}

/** The medium has its metadata, or gave up: a picture never shows a page in the middle of loading. */
async function expectMediaQuiet(page: Page): Promise<void> {
	await expect
		.poll(
			() =>
				page.evaluate(() => {
					const medium = document.getElementById('avs-media') as HTMLMediaElement | null;
					if (medium === null || medium.hidden || medium.error !== null) {
						return true;
					}
					return medium.readyState >= HTMLMediaElement.HAVE_METADATA && !medium.seeking;
				}),
			{ timeout: 15_000 },
		)
		.toBe(true);
}

/**
 * No button carries the accent (04-UI-SPEC, Color): the computed background
 * of each is not --color-primary-element of the theme.
 */
async function expectNoAccent(buttons: Locator): Promise<void> {
	const colours = await buttons.evaluateAll((elements) =>
		elements.map((element) => {
			const style = getComputedStyle(element);
			return { background: style.backgroundColor, accent: style.getPropertyValue('--color-primary-element').trim() };
		}),
	);
	expect(colours.length).toBeGreaterThan(0);
	for (const { background, accent } of colours) {
		expect(accent, 'the theme defines --color-primary-element').not.toBe('');
		const button = parseColor(background);
		const primary = parseColor(accent);
		const same = button.a === 1 && button.r === primary.r && button.g === primary.g && button.b === primary.b;
		expect(same, `a button has the accent ${accent} as its background ${background}`).toBe(false);
	}
}

/** The rendered heights of the buttons. */
async function heights(buttons: Locator): Promise<number[]> {
	return buttons.evaluateAll((elements) => elements.map((element) => element.getBoundingClientRect().height));
}

/** --default-clickable-area of the theme in px. */
async function clickableArea(page: Page): Promise<number> {
	const value = await page.evaluate(() => Number.parseFloat(getComputedStyle(document.body).getPropertyValue('--default-clickable-area')));
	expect(Number.isFinite(value) && value > 0, 'the theme defines --default-clickable-area').toBe(true);
	return value;
}

/** The export section fits the viewport: no horizontal scrolling of it (04-UI-SPEC, 375 px). */
async function expectSectionFits(page: Page): Promise<void> {
	const box = await section(page).evaluate((element) => ({
		scroll: element.scrollWidth,
		client: element.clientWidth,
		right: element.getBoundingClientRect().right,
		viewport: document.documentElement.clientWidth,
	}));
	expect(box.scroll, 'the export section scrolls sideways').toBeLessThanOrEqual(box.client + 1);
	expect(box.right, 'the export section reaches past the viewport').toBeLessThanOrEqual(box.viewport + 1);
}

/** Lower case, no blanks: the comparison of two Content-Type values. */
function compact(value: string | undefined): string {
	return (value ?? '').toLowerCase().replace(/\s+/g, '');
}

/**
 * The page is X3 (04-UI-SPEC): title T13 and sentence T24 only, no download,
 * sidecar, track or export address anywhere in the app content, and the export
 * routes, the track and the sidecar answer 403. Answers the outer HTML of the
 * section and, when asked, the body of the sidecar answer for the combined case.
 */
async function expectX3(page: Page, fileId: string, language: Language, withPost: boolean): Promise<{ section: string; sidecar: string }> {
	await page.goto(playAt(fileId, START_SECONDS));
	// Viewing is allowed: the page plays (state ready), unlike the Phase 3 page download_blocked.
	await expect(page.locator('#avs-media')).toBeAttached();
	await expect(page.locator('#avs-banner-download_blocked')).toBeHidden();
	await expect(section(page).locator('h3.avs-export__title')).toHaveText(T.T13[language]);
	await expect(section(page).locator('p.avs-export__hint')).toHaveText(T.T24[language]);
	await expect(section(page).locator('p.avs-export__note, .avs-export__downloads, .avs-export__sidecar')).toHaveCount(0);
	const app = await page.locator('#app-content').evaluate((element) => element.outerHTML);
	for (const needle of ['avs-export__download', 'avs-sidecar', '<track', '/export/', '/track/', '/sidecar/']) {
		expect(app, `X3 carries ${needle} in the DOM`).not.toContain(needle);
	}
	const routes = exportRoutes(fileId);
	for (const format of FORMATS) {
		expect((await page.request.get(routes[format])).status(), `GET of the ${format} export`).toBe(403);
	}
	expect((await page.request.get(routes.track)).status(), 'GET of the track').toBe(403);
	let sidecar = '';
	if (withPost) {
		const token = await requestToken(page);
		expect(token, 'the page carries a request token').not.toBe('');
		const answer = await page.request.post(routes.sidecar, { headers: { requesttoken: token, Accept: 'application/json' } });
		expect(answer.status(), 'POST of the sidecar').toBe(403);
		sidecar = await answer.text();
		expect(JSON.parse(sidecar)).toEqual({ reason: 'blocked' });
	}
	return { section: await section(page).evaluate((element) => element.outerHTML), sidecar };
}

/** The error page of the download (D2): T29, T25, the action T30, no medium, no JSON. */
async function expectErrorPage(page: Page, language: Language): Promise<Locator> {
	const banner = page.locator('.avs-banner--error[role="alert"]');
	await expect(banner).toBeVisible();
	await expect(banner.locator('p.avs-banner__title')).toHaveText(T.T29[language]);
	await expect(banner.locator('p.avs-banner__text')).toHaveText(T.T25[language]);
	const back = banner.getByRole('link', { name: T.T30[language] });
	await expect(back).toBeVisible();
	await expect(page.locator('#avs-media')).toHaveCount(0);
	expect((await page.locator('body').innerText()).trim().startsWith('{'), 'the error page is no JSON').toBe(false);
	return back;
}

// ---------------------------------------------------------------------------
// X1, X1a: the section of a finished transcript.

test('X1 Export am Video: Reihenfolge SRT, VTT, TXT, kein Akzent, Klickfläche, Spur ohne default @phase4 @axe @screenshot', async ({ page }, testInfo) => {
	only(testInfo, X1_PROJECTS);
	test.setTimeout(PREPARED_MS);
	const { user, language } = phase4User(testInfo);
	const video = fileIds.s7Video();
	await expectTranscript(user, video);
	await login(page, user);
	await page.goto(playAt(video, START_SECONDS));

	await expect(section(page).locator('h3.avs-export__title')).toHaveText(T.T13[language]);
	await expect(section(page).locator('p.avs-export__note')).toHaveText(T.T14[language]);
	await expect(partialNote(page)).toHaveCount(0);
	await expect(downloadLinks(page)).toHaveText([T.T16[language], T.T17[language], T.T18[language]]);
	expect((await hrefs(page)).map(formatOf)).toEqual(['srt', 'vtt', 'txt']);
	// The group carries the section title as its name.
	await expect(page.getByRole('group', { name: T.T13[language] })).toBeVisible();
	// The draft track on the video, never switched on by default (D-04-18).
	await expect(page.locator('video#avs-media > track[kind="subtitles"]')).toHaveCount(1);
	await expect(page.locator('#avs-media > track[default]')).toHaveCount(0);
	// The sidecar block names the real target name (T20) and play.js shows the button.
	const sidecarName = exportName(S7_VIDEO_NAME, 'vtt');
	await expect(sidecarHint(page)).toHaveText(fill(T.T20[language], sidecarName));
	await expect(page.locator('#avs-sidecar')).toBeVisible();
	await expect(page.locator('#avs-sidecar')).toHaveText(T.T19[language]);

	const buttons = downloadLinks(page).or(page.locator('#avs-sidecar'));
	await expectNoAccent(buttons);
	const area = await clickableArea(page);
	for (const height of await heights(buttons)) {
		expect(height, `a button is lower than --default-clickable-area (${area} px)`).toBeGreaterThanOrEqual(area - 0.5);
	}
	await expectSectionFits(page);
	await expectMediaQuiet(page);
	await screenshot(page, 'x1', testInfo);
	await expectAxeClean(page, 'x1', testInfo);
});

test('X1 grober Zeiger: Download- und Ablage-Knopf mindestens 44 px hoch @phase4', async ({ browser, page }, testInfo) => {
	only(testInfo, ['w375-light']);
	test.setTimeout(PREPARED_MS);
	const { user } = phase4User(testInfo);
	const video = fileIds.s7Video();
	await expectTranscript(user, video);
	await login(page, user);
	// A phone in Chromium: isMobile and touch make (pointer: coarse) true.
	const context = await browser.newContext({
		baseURL: testInfo.project.use.baseURL ?? process.env.NC_URL ?? 'http://localhost:8080',
		storageState: await page.context().storageState(),
		viewport: { width: 375, height: 900 },
		isMobile: true,
		hasTouch: true,
	});
	try {
		const phone = await context.newPage();
		await phone.goto(playAt(video, START_SECONDS));
		expect(await phone.evaluate(() => matchMedia('(pointer: coarse)').matches), 'the context has a coarse pointer').toBe(true);
		await expect(downloadLinks(phone)).toHaveCount(3);
		await expect(phone.locator('#avs-sidecar')).toBeVisible();
		for (const height of await heights(downloadLinks(phone).or(phone.locator('#avs-sidecar')))) {
			expect(height, 'a button is lower than 44 px under a coarse pointer').toBeGreaterThanOrEqual(43.5);
		}
	} finally {
		await context.close();
	}
});

test('X1a Export an einer Audiodatei: drei Downloads, keine Spur @phase4 @axe', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const alice = users.alice();
	const audio = fileIds.s7DeDigit();
	await expectTranscript(alice, audio);
	await login(page, alice);
	await page.goto(playAt(audio, START_SECONDS));
	await expect(page.locator('audio#avs-media')).toBeAttached();
	await expect(downloadLinks(page)).toHaveText([T.T16.en, T.T17.en, T.T18.en]);
	await expect(page.locator('track')).toHaveCount(0);
	await expectMediaQuiet(page);
	await screenshot(page, 'x1a', testInfo);
	await expectAxeClean(page, 'x1a', testInfo);
});

// ---------------------------------------------------------------------------
// X2: a file in work, in a controlled window.

/**
 * One reading of the triple: the clock of T15 on the page, the TXT and the VTT
 * of the same links, the clock again. 'retry' when a piece finished in
 * between (the clock moved) or a download did not answer, 'done' when the
 * file is no longer partial, 'ok' when the TXT header and the VTT NOTE carry
 * T15 with the clock of the page, else what differed.
 */
async function readTriple(page: Page, fileId: string): Promise<string> {
	await page.goto(playAt(fileId, EARLY_SECONDS));
	const before = await partialClock(page);
	if (before === null) {
		return 'done';
	}
	const byFormat = new Map((await hrefs(page)).map((href) => [formatOf(href), href]));
	const txt = await page.request.get(byFormat.get('txt') ?? '');
	const vtt = await page.request.get(byFormat.get('vtt') ?? '');
	if (txt.status() !== 200 || vtt.status() !== 200) {
		return 'retry';
	}
	const txtBody = await txt.text();
	const vttBody = await vtt.text();
	await page.goto(playAt(fileId, EARLY_SECONDS));
	const after = await partialClock(page);
	if (after === null) {
		return 'done';
	}
	if (after !== before) {
		return 'retry';
	}
	const expected = fill(T.T15.en, before);
	// TXT: name, T35, T15, blank line, text (04-UI-SPEC "Dateiinhalte").
	const txtLine = txtBody.replace(/\r\n/g, '\n').split('\n')[2] ?? '';
	const note = noteLines(vttBody);
	if (txtLine === expected && note.includes(expected)) {
		return 'ok';
	}
	return `page ${before}, TXT line 3 "${txtLine}", VTT NOTE ${JSON.stringify(note)}`;
}

test('X2 Teiltranskript: gleiche Zeit auf der Seite, im TXT-Kopf und in der VTT-NOTE @phase4 @axe', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(2 * PARTIAL_WITHIN_MS + 5 * 60_000);
	const alice = users.alice();
	const data = readFileSync(join(required('AVS_MEDIA_DIR'), X2_FILE));
	const fileId = await uploadTo(alice, X2_FOLDER, X2_FILE, data, 'audio/ogg');
	await login(page, alice);

	// Nothing finished: no section (X4). One piece finished: X2. All done: X1.
	let seen = 'not yet';
	await expect
		.poll(
			async () => {
				await page.goto(playAt(fileId, EARLY_SECONDS));
				if ((await partialNote(page).count()) > 0) {
					seen = 'partial';
				} else if ((await downloadLinks(page).count()) > 0) {
					seen = 'done';
				} else {
					seen = 'not yet';
				}
				return seen;
			},
			{ timeout: PARTIAL_WITHIN_MS, intervals: [PARTIAL_POLL_MS] },
		)
		.not.toBe('not yet');
	expect(seen, 'the file was done before a look caught it partial (X2)').toBe('partial');

	// The pictures first, while the window is surely open.
	const clock = await partialClock(page);
	expect(clock, 'T15 carries a time element').not.toBeNull();
	await expect(partialNote(page)).toHaveText(fill(T.T15.en, clock as string));
	await expect(partialNote(page).locator('time.avs-play__time')).toHaveAttribute('datetime', /^PT(\d+H)?(\d+M)?\d+S$/);
	await expect(downloadLinks(page)).toHaveCount(3);
	await screenshotVariants(page, 'x2', testInfo, ALL_VARIANTS, partialNote(page));
	await expectAxeClean(page, 'x2', testInfo);

	// French at 375 px: fleur receives the file for the picture.
	await ensureShare(alice, `/${X2_FOLDER}/${X2_FILE}`, 'fleur', 0, READ_ONLY);
	await switchUser(page, users.fleur());
	await page.setViewportSize({ width: 375, height: 900 });
	await page.goto(playAt(fileId, EARLY_SECONDS));
	const frenchClock = await partialClock(page);
	if (frenchClock !== null) {
		await expect(partialNote(page)).toHaveText(fill(T.T15.fr, frenchClock));
		await screenshot(page, 'x2', testInfo, 'fr-w375-light');
	} else {
		testInfo.annotations.push({ type: 'gap', description: 'X2 fr-w375-light: the file was no longer partial when fleur opened it' });
	}
	await page.setViewportSize({ width: 1280, height: 900 });
	await switchUser(page, alice);

	// The triple, read again whenever a piece finished in between.
	let verdict = 'retry';
	await expect
		.poll(async () => (verdict = await readTriple(page, fileId)), { timeout: PARTIAL_WITHIN_MS, intervals: [PARTIAL_POLL_MS] })
		.not.toBe('retry');
	expect(verdict, 'the file was done before page, TXT and VTT could be read with one clock (X2)').not.toBe('done');
	expect(verdict, 'the clock of T15 on the page, in the TXT header and in the VTT NOTE').toBe('ok');
});

// ---------------------------------------------------------------------------
// X3: a share with the download switched off while viewing is allowed.

test('X3 Freigabe mit Download-Sperre, Ansehen erlaubt: nur T13 und T24, Export, Spur und Ablage 403 @phase4 @axe @screenshot', async ({ page }, testInfo) => {
	only(testInfo, X3_PROJECTS);
	test.setTimeout(PREPARED_MS);
	const { user, language } = phase4User(testInfo);
	const locked = fileIds.s7De();
	// The owner has the transcript, so the recipient sees X3 for the block and not X4 for lack of a text.
	await expectTranscript(users.alice(), locked);
	toggleViewWithoutDownload(true);
	try {
		await login(page, user);
		// One POST per user in the grid is enough; the sidecar route allows 10 a minute.
		await expectX3(page, locked, language, testInfo.project.name === ONCE);
		await expectMediaQuiet(page);
		await screenshot(page, 'x3', testInfo);
		await expectAxeClean(page, 'x3', testInfo);
	} finally {
		toggleViewWithoutDownload(false);
	}
});

test('X3 Kombifall gesperrt und ausgeschlossen: derselbe Abschnitt, dieselben 403 wie ohne Ausschluss @phase4', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const { user, language } = phase4User(testInfo);
	const locked = fileIds.s7De();
	await expectTranscript(users.alice(), locked);
	toggleViewWithoutDownload(true);
	try {
		await login(page, user);
		const plain = await expectX3(page, locked, language, true);
		const excerptBefore = await page.locator('section.avs-excerpt p.avs-excerpt__hint').allTextContents();
		expect(excerptBefore, 'without the exclusion the excerpt block does not say A5').not.toContain(T.A5[language]);
		// occ has no rule for a single file in a home; the user rule is the
		// exclusion ExportController asks first (isExcludedUser || isExcludedFile).
		excludeUser(user.name, true);
		try {
			const excluded = await expectX3(page, locked, language, true);
			// Positive control: the exclusion is in force, the excerpt block answers A5.
			await expect(page.locator('section.avs-excerpt p.avs-excerpt__hint')).toHaveText(T.A5[language]);
			expect(excluded.section, 'the blocked section of an excluded user equals the one of a user who is not').toBe(plain.section);
			expect(excluded.sidecar, 'the 403 of the sidecar is byte for byte the same').toBe(plain.sidecar);
		} finally {
			excludeUser(user.name, false);
		}
	} finally {
		toggleViewWithoutDownload(false);
	}
});

// ---------------------------------------------------------------------------
// X4: no section at all, byte for byte the same for every reason.

test('X4 ohne Transkript und ausgeschlossen: kein Abschnitt, Hauptbereich ab dem Ausschnitt byte-gleich @phase4 @axe', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const video = fileIds.s7Video();
	const stille = fileIds.stille();
	// dora and oskar both read English, so their excerpt blocks can be compared byte for byte.
	const dora = users.dora();
	await expectTranscript(dora, video);

	// Positive control: dora sees the section on the video while she is not excluded.
	await login(page, dora);
	await page.goto(playAt(video, START_SECONDS));
	await expect(downloadLinks(page)).toHaveCount(3);

	let excludedVideo = { fromExcerpt: '', tail: '' };
	excludeUser(dora.name, true);
	try {
		await page.goto(playAt(video, START_SECONDS));
		await expect(page.locator('section.avs-excerpt')).toBeVisible();
		await expect(section(page)).toHaveCount(0);
		excludedVideo = await columnFromExcerpt(page);
	} finally {
		excludeUser(dora.name, false);
	}
	expect(excludedVideo.fromExcerpt).not.toContain('avs-export');
	expect(excludedVideo.fromExcerpt).not.toContain('<track');

	// oskar is excluded by the seed and reads stille-60s.ogg.
	await switchUser(page, users.oskar());
	await page.goto(playAt(stille, 0));
	await expect(page.locator('section.avs-excerpt')).toBeVisible();
	await expect(section(page)).toHaveCount(0);
	const excludedStille = await columnFromExcerpt(page);
	expect(excludedStille.fromExcerpt, 'two excluded users, a file with and one without transcript: same bytes from the excerpt on').toBe(
		excludedVideo.fromExcerpt,
	);

	// alice owns stille-60s.ogg, a file without a transcript (no speech): no section either.
	await switchUser(page, users.alice());
	await page.goto(playAt(stille, 0));
	await expect(page.locator('section.avs-excerpt')).toBeVisible();
	await expect(section(page)).toHaveCount(0);
	const withoutTranscript = await columnFromExcerpt(page);
	expect(withoutTranscript.tail, 'after the excerpt block a file without transcript equals an excluded user').toBe(excludedVideo.tail);
	await expectMediaQuiet(page);
	await screenshot(page, 'x4', testInfo);
	await expectAxeClean(page, 'x4', testInfo);
});

// ---------------------------------------------------------------------------
// X5: a share without the right to create files; X6: no JavaScript.

test('X5 Freigabe nur lesen mit Download: T23 statt Knopf, Downloads gehen @phase4 @axe', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const alice = users.alice();
	const carol = users.carol();
	const ablage = fileIds.ablage();
	const shareId = await ablageShare();
	await expectTranscript(carol, ablage);
	await login(page, carol);

	// Positive control: with the right to create files carol gets the button.
	await page.goto(playAt(ablage, START_SECONDS));
	await expect(page.locator('#avs-sidecar')).toBeVisible();

	await updateShare(alice, shareId, { permissions: READ_ONLY });
	try {
		await page.goto(playAt(ablage, START_SECONDS));
		await expect(sidecarHint(page)).toHaveText(T.T23.en);
		await expect(page.locator('#avs-sidecar')).toHaveCount(0);
		await expect(page.locator('#avs-sidecar-result')).toHaveCount(0);
		const links = downloadLinks(page);
		await expect(links).toHaveCount(3);
		for (const [index, format] of FORMATS.entries()) {
			const { name } = await downloadTo(page, links.nth(index), testInfo.outputPath('x5'));
			expect(name).toBe(exportName(ABLAGE_FILE, format));
		}
		await expectMediaQuiet(page);
		await screenshotVariants(page, 'x5', testInfo, [[1280, 'light'], [375, 'light']], section(page));
		await expectAxeClean(page, 'x5', testInfo);
	} finally {
		await updateShare(alice, shareId, { permissions: ABLAGE_PERMISSIONS });
	}
});

test('X6 ohne JavaScript: Downloads gehen, Ablage-Knopf unsichtbar, T20 steht @phase4', async ({ browser, page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const { user, language } = phase4User(testInfo);
	const video = fileIds.s7Video();
	await expectTranscript(user, video);
	// The login form needs JavaScript; the session moves into a context without it.
	await login(page, user);
	const context = await browser.newContext({
		baseURL: testInfo.project.use.baseURL ?? process.env.NC_URL ?? 'http://localhost:8080',
		storageState: await page.context().storageState(),
		viewport: { width: 1280, height: 900 },
		colorScheme: 'light',
		javaScriptEnabled: false,
	});
	try {
		const plain = await context.newPage();
		await plain.goto(playAt(video, START_SECONDS));
		await expect(sidecarHint(plain)).toHaveText(fill(T.T20[language], exportName(S7_VIDEO_NAME, 'vtt')));
		await expect(plain.locator('#avs-sidecar')).toBeHidden();
		await expect(plain.locator('#avs-sidecar')).toHaveAttribute('hidden', '');
		const links = downloadLinks(plain);
		await expect(links).toHaveCount(3);
		for (const [index, format] of FORMATS.entries()) {
			const { name } = await downloadTo(plain, links.nth(index), testInfo.outputPath('x6'));
			expect(name).toBe(exportName(S7_VIDEO_NAME, format));
		}
		await screenshot(plain, 'x6', testInfo);
	} finally {
		await context.close();
	}
});

// ---------------------------------------------------------------------------
// D1: the real downloads, kept for the parser proof (tests/test_downloaded_subtitles.py).

test('D1 Downloads SRT, VTT, TXT: Name mit Sprache, auch mit Umlaut, MIME, TXT-Zeile 2 = T35 @phase4', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const dir = required('AVS_DOWNLOADS_DIR');
	const cases = [
		{ user: users.elke(), language: 'de' as Language, fileId: fileIds.s7Video(), fileName: S7_VIDEO_NAME },
		{ user: users.alice(), language: 'en' as Language, fileId: fileIds.s7DeDigit(), fileName: 's7-ziffer.wav' },
	];
	for (const [position, item] of cases.entries()) {
		await expectTranscript(item.user, item.fileId);
		if (position === 0) {
			await login(page, item.user);
		} else {
			await switchUser(page, item.user);
		}
		await page.goto(playAt(item.fileId, START_SECONDS));
		const links = downloadLinks(page);
		await expect(links).toHaveCount(3);
		for (const [index, format] of FORMATS.entries()) {
			const { path, name } = await downloadTo(page, links.nth(index), dir);
			expect(name).toMatch(DOWNLOAD_NAME);
			expect(name).toBe(exportName(item.fileName, format));
			const href = await links.nth(index).getAttribute('href');
			const response = await page.request.get(href ?? '');
			expect(response.status()).toBe(200);
			expect(compact(response.headers()['content-type']), `Content-Type of ${format}`).toBe(compact(MIME[format]));
			expect(response.headers()['content-disposition'] ?? '').toContain('attachment');
			const text = readFileSync(path, 'utf8').replace(/\r\n/g, '\n');
			if (format === 'txt') {
				const lines = text.split('\n');
				expect(lines[0]).toBe(item.fileName);
				expect(lines[1], 'line 2 of the TXT is T35 in the display language').toBe(T.T35[item.language]);
			}
			if (format === 'vtt') {
				expect(text.startsWith('WEBVTT\n\nNOTE\n')).toBe(true);
				expect(noteLines(text)[0]).toBe(T.T35[item.language]);
			}
		}
	}
});

// ---------------------------------------------------------------------------
// D2: the error page of the download, with the container stopped.

test('D2 Fehlerseite bei gestopptem Container: T29, T25, T30 zurück mit gleichem ?t=, auch über den Link der Seite @phase4 @axe', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS + 10 * 60_000);
	const { user, language } = phase4User(testInfo);
	const video = fileIds.s7Video();
	await expectTranscript(user, video);
	await login(page, user);
	await page.goto(playAt(video, Number(D2_MARK)));
	await expect(downloadLinks(page)).toHaveCount(3);
	// The links carry the checked mark of the page (PageController::exportState).
	const links = await hrefs(page);
	expect(links.map(formatOf)).toEqual(['srt', 'vtt', 'txt']);
	for (const href of links) {
		expect(new URL(href, 'http://local').searchParams.get('t'), `the export link ${href} carries the mark of the page`).toBe(D2_MARK);
	}
	const srt = links[0];

	await withContainerStopped(
		async () => {
			// The way of a user: the link on the page while the container is down.
			const answered = page.waitForResponse((response) => response.url().includes(`/export/${video}/srt`));
			await downloadLinks(page).first().click();
			expect((await answered).status()).toBe(503);
			const back = await expectErrorPage(page, language);
			const backUrl = new URL((await back.getAttribute('href')) ?? '', 'http://local');
			expect(backUrl.pathname).toMatch(new RegExp(`/apps/audio_video_search/play/${video}$`));
			expect(backUrl.searchParams.get('t'), 'the way back of the error page reached by the link keeps the mark of the page').toBe(D2_MARK);

			// The route itself, opened again: the way back keeps the mark.
			const response = await page.goto(srt);
			expect(response?.status()).toBe(503);
			const action = await expectErrorPage(page, language);
			await screenshotVariants(page, 'd2', testInfo, [[1280, 'light'], [1280, 'dark'], [375, 'light']], page.locator('.avs-banner--error'));
			await expectAxeClean(page, 'd2', testInfo);
			await action.click();
			await expect(page).toHaveURL(new RegExp(`/apps/audio_video_search/play/${video}\\?t=${D2_MARK.replace('.', '\\.')}$`));
		},
		user,
		video,
	);
});
