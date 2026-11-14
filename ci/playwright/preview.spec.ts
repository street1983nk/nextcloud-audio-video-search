// Phase 3 as an end-to-end contract (plans 03-02 and 03-18): the core path (a
// spoken clip that alice uploads is found through the Unified Search within
// minutes, marked as preliminary, the hit jumps to the time of the word, and
// a user without access finds nothing) and the states of the acceptance in
// UI-SPEC 03: S1 to S5 in the search, P1 to P13 on the playback page, the
// contrast of the preview note and the leak probes.
//
// The clip comes from ci/media/fetch_speech.py (FLEURS, Google, CC-BY-4.0):
// CI sets AVS_SPEECH_DE to the path of speech_de.wav and AVS_SPEECH_WORD to
// its EXPECTED_WORD. ci/make-testmedia.sh made the media of the states out of
// the clips, ci/seed.sh put them in place (who owns and reads what is written
// there). The step @preview of deploy-harp.yml switches this file on with
// AVS_PREVIEW_E2E=1 and hands in AVS_OCC, AVS_MEDIA_DIR and AVS_LEAK_PROBE.
//
// Two kinds of tests:
// - the states that stay once the preview is done run in the projects of the
//   grid (and in the review projects where the UI-SPEC wants high contrast or
//   French), each test in the projects its row of the UI-SPEC names;
// - the paths that change the instance (an upload, the partial window of a
//   long file, the limit of A10, the leak probe) run once, in w1280-light, and
//   take their pictures in several widths and schemes on the same page.
//
// No fixed waits: only web-first assertions, waitForResponse and expect.poll.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, request, test, type APIRequestContext, type Locator, type Page, type TestInfo } from '@playwright/test';
import {
	contrastRatio,
	excerptNoteContrast,
	expectMediaSettled,
	fileIds,
	login,
	occ,
	position,
	reviewer,
	SAMPLE_MARK,
	screenshot,
	searchInDialog,
	users,
	type User,
} from './helpers';

test.skip(process.env.AVS_PREVIEW_E2E !== '1', 'phase 3 runs in the step @preview of deploy-harp.yml');

const BASE_URL = process.env.NC_URL ?? 'http://localhost:8080';
const BACKEND_APP_ID = 'audio_video_search_backend';
const PLAY_PATH = '/index.php/apps/audio_video_search/play';
const FOLDER = 'phase3';
const FILE_NAME = 'speech_de.wav';
const LONG_FILE = 'lang-40min.ogg';
// The preview mark of the subline (UI-SPEC T1) in the three languages.
const MARK = '(Vorläufig|Preliminary|Provisoire)';
const PRELIMINARY_MARK = new RegExp(MARK);
const PRELIMINARY_SUBLINE = new RegExp(`^\\d+:\\d{2} · ${MARK} · `);
// Time, mark, excerpt in this order, and a non-empty excerpt (UI-SPEC surface 1).
const ORDERED_SUBLINE = new RegExp(`^\\d+(:\\d{2}){1,2} · ${MARK} · \\S`);
// The jump lands at most 0.2 s before and 0.05 s after the time of the link.
const BEFORE_SECONDS = 0.2;
const AFTER_SECONDS = 0.05;
const FOUND_WITHIN_MS = 15 * 60_000;
const POLL_EVERY_MS = 10_000;
// A state of the playback page shows once the preview of its file is done.
const STATE_WITHIN_MS = 10 * 60_000;
const STATE_POLL_MS = 5_000;
// The partial window of the 40 min file lasts minutes; look every 2 s.
const PARTIAL_WITHIN_MS = 10 * 60_000;
const PARTIAL_POLL_MS = 2_000;
// A point in the last piece of the 40 min file (39 min), and one in its first.
const LATE_SECONDS = 2340;
const EARLY_SECONDS = 6;
// The worker reads the longest recording every 300 s (SETTINGS_REFRESH_SECONDS).
const LIMIT_WITHIN_MS = 300_000 + 3 * 60_000;
const DEFAULT_LIMIT_HOURS = 12;

const GRID = ['w375-light', 'w375-dark', 'w768-light', 'w768-dark', 'w1280-light', 'w1280-dark'];
const ONCE = 'w1280-light';
type Variant = readonly [number, 'light' | 'dark'];
const ALL_VARIANTS: readonly Variant[] = [
	[375, 'light'],
	[375, 'dark'],
	[768, 'light'],
	[768, 'dark'],
	[1280, 'light'],
	[1280, 'dark'],
];

type Language = 'en' | 'de' | 'fr';
type Texts = Record<Language, string>;

// The texts of UI-SPEC 03, copied from its table (Copywriting Contract), never
// from the catalogues: the test has to see what the owner approved.
const T: Record<string, Texts> = {
	A5: {
		en: 'There is no transcript for this file yet.',
		de: 'Für diese Datei gibt es noch kein Transkript.',
		fr: "Il n'y a pas encore de transcription pour ce fichier.",
	},
	T2: {
		en: 'Preliminary transcript. It may contain errors.',
		de: 'Vorläufiges Transkript. Es kann Fehler enthalten.',
		fr: 'Transcription provisoire. Elle peut contenir des erreurs.',
	},
	T3: {
		en: 'Preliminary transcript. The file is still being transcribed, later passages will follow.',
		de: 'Vorläufiges Transkript. Die Datei wird noch transkribiert, spätere Stellen folgen.',
		fr: 'Transcription provisoire. Le fichier est encore en cours de transcription, la suite suivra.',
	},
	T4: {
		en: 'This point has not been transcribed yet. The file is being transcribed right now.',
		de: 'Diese Stelle ist noch nicht transkribiert. Die Datei wird gerade transkribiert.',
		fr: "Ce passage n'est pas encore transcrit. Le fichier est en cours de transcription.",
	},
	T5: {
		en: 'No speech was found in this file, for example because it only contains music, silence or noise.',
		de: 'In dieser Datei wurde keine Sprache erkannt, etwa weil sie nur Musik, Stille oder Rauschen enthält.',
		fr: "Aucune parole n'a été détectée dans ce fichier, par exemple parce qu'il ne contient que de la musique, du silence ou du bruit.",
	},
	T6: {
		en: 'This file was not transcribed because it is damaged or incomplete. If it is replaced, transcription starts again automatically.',
		de: 'Diese Datei wurde nicht transkribiert, weil sie beschädigt oder unvollständig ist. Wird sie ersetzt, startet die Transkription automatisch neu.',
		fr: "Ce fichier n'a pas été transcrit car il est endommagé ou incomplet. S'il est remplacé, la transcription redémarre automatiquement.",
	},
	T7: {
		en: 'This file was not transcribed because it is protected, for example by copy protection. An unprotected copy is transcribed automatically.',
		de: 'Diese Datei wurde nicht transkribiert, weil sie geschützt ist, etwa durch einen Kopierschutz. Eine ungeschützte Fassung wird automatisch transkribiert.',
		fr: "Ce fichier n'a pas été transcrit car il est protégé, par exemple contre la copie. Une version non protégée sera transcrite automatiquement.",
	},
	T8: {
		en: 'The language of this recording is not supported. Transcription covers German, English and French.',
		de: 'Die Sprache dieser Aufnahme wird nicht unterstützt. Transkribiert werden Deutsch, Englisch und Französisch.',
		fr: "La langue de cet enregistrement n'est pas prise en charge. Sont transcrits l'allemand, l'anglais et le français.",
	},
	T9a: {
		en: 'This file is longer than %n hour and was therefore not transcribed.',
		de: 'Diese Datei ist länger als %n Stunde und wurde deshalb nicht transkribiert.',
		fr: "Ce fichier dure plus de %n heure et n'a donc pas été transcrit.",
	},
	T9b: {
		en: 'This file is longer than %n hours and was therefore not transcribed.',
		de: 'Diese Datei ist länger als %n Stunden und wurde deshalb nicht transkribiert.',
		fr: "Ce fichier dure plus de %n heures et n'a donc pas été transcrit.",
	},
	T10: {
		en: 'The administrators of this instance can raise the limit.',
		de: 'Die Verwaltung dieser Instanz kann die Grenze anheben.',
		fr: "L'administration de cette instance peut relever cette limite.",
	},
	T11: {
		en: 'This file was not transcribed. The administrators of this instance can see why.',
		de: 'Diese Datei wurde nicht transkribiert. Den Grund sieht die Verwaltung dieser Instanz.',
		fr: "Ce fichier n'a pas été transcrit. L'administration de cette instance en connaît la raison.",
	},
};

/** A10: T9 in singular or plural and T10 in one paragraph, joined by one space. */
function tooLong(language: Language, hours: number): string {
	const sentence = (hours === 1 ? T.T9a : T.T9b)[language].replace('%n', String(hours));
	return `${sentence} ${T.T10[language]}`;
}

type Entry = { title: string; subline: string; resourceUrl: string; attributes: Record<string, string> };
type Page1 = { entries: Entry[]; cursor: unknown };

function required(name: string): string {
	const value = process.env[name];
	if (value === undefined || value === '') {
		throw new Error(`${name} is not set; the step @preview of deploy-harp.yml sets it`);
	}
	return value;
}

function escapeRegExp(text: string): string {
	return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** The language of a project: the review projects name theirs, the grid and dora read English. */
function languageOf(testInfo: TestInfo): Language {
	const language = testInfo.project.metadata?.language;
	return language === 'de' || language === 'fr' ? language : 'en';
}

/** The test runs in exactly these projects (one row of the UI-SPEC). */
function only(testInfo: TestInfo, projects: readonly string[]): void {
	test.skip(!projects.includes(testInfo.project.name), `this state is pictured in ${projects.join(', ')}`);
}

async function apiAs(user: User): Promise<APIRequestContext> {
	return request.newContext({
		baseURL: BASE_URL,
		httpCredentials: { username: user.name, password: user.password, send: 'always' },
	});
}

/** One page of this provider for one term, as one user, through OCS. */
async function searchPage(user: User, term: string, limit: number, cursor?: unknown): Promise<Page1> {
	const api = await apiAs(user);
	try {
		const next = cursor === undefined || cursor === null ? '' : `&cursor=${encodeURIComponent(String(cursor))}`;
		const response = await api.get(
			`/ocs/v2.php/search/providers/audio_video_search/search?term=${encodeURIComponent(term)}&limit=${limit}${next}`,
			{ headers: { 'OCS-APIRequest': 'true', Accept: 'application/json' } },
		);
		expect(response.status()).toBe(200);
		const body = await response.json();
		return { entries: body.ocs.data.entries, cursor: body.ocs.data.cursor };
	} finally {
		await api.dispose();
	}
}

async function searchAs(user: User, term: string): Promise<Entry[]> {
	return (await searchPage(user, term, 5)).entries;
}

function idOf(entry: Entry): string {
	return String(entry.attributes?.fileId);
}

function hitOf(entries: Entry[], fileId: string): Entry | undefined {
	return entries.find((entry) => idOf(entry) === fileId);
}

/** Upload a file by WebDAV into the user's folder phase3 and answer its file id. */
async function upload(user: User, source: string, name: string, contentType: string): Promise<string> {
	const api = await apiAs(user);
	try {
		const folder = `/remote.php/dav/files/${user.name}/${FOLDER}`;
		const made = await api.fetch(folder, { method: 'MKCOL' });
		// 201 created, 405 when the folder is already there.
		expect([201, 405]).toContain(made.status());
		const put = await api.put(`${folder}/${name}`, {
			data: readFileSync(source),
			headers: { 'Content-Type': contentType },
			timeout: 120_000,
		});
		expect([201, 204]).toContain(put.status());
		const found = await api.fetch(`${folder}/${name}`, {
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

function playAt(fileId: string, seconds: number): string {
	return `${PLAY_PATH}/${fileId}?t=${seconds}`;
}

const excerptBlock = (page: Page): Locator => page.locator('section.avs-excerpt');
const excerptHint = (page: Page): Locator => page.locator('section.avs-excerpt p.avs-excerpt__hint');
const excerptNote = (page: Page): Locator => page.locator('section.avs-excerpt p.avs-excerpt__note');
const excerptQuote = (page: Page): Locator => page.locator('section.avs-excerpt blockquote.avs-excerpt__text');

/** The sentence of the excerpt block right now: the hint, else the note, else ''. */
async function excerptSentence(page: Page): Promise<string> {
	for (const part of [excerptHint(page), excerptNote(page)]) {
		if ((await part.count()) > 0) {
			return ((await part.first().textContent()) ?? '').trim();
		}
	}
	return '';
}

/** Open the page again and again until the excerpt block carries the expected sentence. */
async function expectState(page: Page, path: string, expected: string, timeout = STATE_WITHIN_MS): Promise<void> {
	await expect
		.poll(
			async () => {
				await page.goto(path);
				return excerptSentence(page);
			},
			{ timeout, intervals: [STATE_POLL_MS], message: `the playback page never showed "${expected}"` },
		)
		.toBe(expected);
}

/**
 * The medium is at rest for a picture, or it gave up: metadata there, no
 * seek, no loading; or an error; or play.js hid it behind a banner. Files
 * with a reason may never play (damaged, protected, a codec Chromium lacks).
 */
async function expectMediaQuiet(page: Page): Promise<void> {
	await expect
		.poll(
			() =>
				page.evaluate(() => {
					const medium = document.getElementById('avs-media') as HTMLMediaElement | null;
					if (medium === null || medium.hidden || medium.error !== null) {
						return true;
					}
					return (
						medium.readyState >= HTMLMediaElement.HAVE_METADATA &&
						!medium.seeking &&
						medium.networkState !== HTMLMediaElement.NETWORK_LOADING
					);
				}),
			{ timeout: 15_000 },
		)
		.toBe(true);
}

/** Pictures of the page as it stands, in the given widths and schemes, without loading it again. */
async function shots(page: Page, name: string, testInfo: TestInfo, variants: readonly Variant[]): Promise<void> {
	for (const [width, colorScheme] of variants) {
		await page.setViewportSize({ width, height: 900 });
		await page.emulateMedia({ colorScheme });
		await expect(excerptBlock(page)).toBeVisible();
		await screenshot(page, name, testInfo, `w${width}-${colorScheme}`);
	}
	await page.setViewportSize({ width: 1280, height: 900 });
	await page.emulateMedia({ colorScheme: 'light' });
}

/** Sign in as another user in the same page. */
async function switchUser(page: Page, user: User): Promise<void> {
	// Leave the app first, so its background requests start no new session.
	await page.goto('about:blank');
	await page.context().clearCookies();
	await login(page, user);
}

/**
 * The measurement passes its self test first (T-03-60): black on white is
 * 21:1, #767676 on white is just above 4.5:1 and #999999 on white below.
 */
function expectContrastSelfTest(): void {
	expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 6);
	const justEnough = contrastRatio('#767676', '#ffffff');
	expect(justEnough).toBeGreaterThanOrEqual(4.5);
	expect(justEnough).toBeLessThanOrEqual(4.6);
	expect(contrastRatio('#999999', '#ffffff')).toBeLessThan(4.5);
	expect(contrastRatio('rgb(255, 255, 255)', 'rgb(0, 0, 0)')).toBeCloseTo(21, 6);
}

// ---------------------------------------------------------------------------
// The measurement itself, no instance needed.

test('Kontrast-Selbsttest: 21:1, #767676 knapp über und #999999 unter 4,5:1 @preview', async ({}, testInfo) => {
	only(testInfo, [ONCE]);
	expectContrastSelfTest();
});

// ---------------------------------------------------------------------------
// Search: S1 to S5 (UI-SPEC surface 1). bob reads exactly two files with
// speech, viele-stellen.ogg (four places) and zwei-stellen.ogg (two), so the
// first page of five is fixed: three places of the first file in tier 1, both
// of the second, the fourth place of the first file in tier 2.

test('S1 Datei mit vier Stellen: genau drei Zeilen auf Seite 1, je Zeit · Vorläufig · Ausschnitt @preview', async ({ page }, testInfo) => {
	only(testInfo, GRID);
	test.setTimeout(STATE_WITHIN_MS + 2 * 60_000);
	const word = required('AVS_SPEECH_WORD');
	const bob = users.bob();

	// All six places of both files are in the index before anything is counted.
	await expect
		.poll(async () => (await searchPage(bob, word, 10)).entries.length, {
			timeout: STATE_WITHIN_MS,
			intervals: [STATE_POLL_MS],
			message: 'bob never found the six places of viele-stellen.ogg and zwei-stellen.ogg',
		})
		.toBe(6);
	const first = await searchPage(bob, word, 5);
	expect(first.entries).toHaveLength(5);
	expect(first.entries.filter((entry) => idOf(entry) === fileIds.viele())).toHaveLength(3);
	expect(first.entries.filter((entry) => idOf(entry) === fileIds.zwei())).toHaveLength(2);
	for (const entry of first.entries) {
		expect(entry.subline).toMatch(ORDERED_SUBLINE);
		expect(entry.subline).not.toMatch(SAMPLE_MARK);
	}

	await login(page, bob);
	const group = await searchInDialog(page, word);
	const many = group.locator('a[href]').filter({ hasText: 'viele-stellen.ogg' });
	await expect(many.first()).toBeVisible();
	// The dialog asks with its own page size; never more than three places of one file on its first page.
	expect(await many.count()).toBeLessThanOrEqual(3);
	await expect(many.first()).toContainText(PRELIMINARY_MARK);
	await screenshot(page, 'search-s1', testInfo);
});

test('S2 Mehr laden: die vierte Stelle kommt, keine Dublette, Seite 1 bleibt gleich @preview', async ({ page }, testInfo) => {
	only(testInfo, ['w1280-light', 'w1280-dark']);
	const word = required('AVS_SPEECH_WORD');
	const bob = users.bob();

	const five = await searchPage(bob, word, 5);
	const ten = await searchPage(bob, word, 10);
	const urls = ten.entries.map((entry) => entry.resourceUrl);
	expect(new Set(urls).size).toBe(urls.length);
	expect(urls.slice(0, 5)).toEqual(five.entries.map((entry) => entry.resourceUrl));
	expect(ten.entries.filter((entry) => idOf(entry) === fileIds.viele())).toHaveLength(4);

	// API clients page with the cursor: page 2 brings the fourth place, no repeat of page 1.
	expect(five.cursor, 'a full first page carries a cursor').not.toBeNull();
	const second = await searchPage(bob, word, 5, five.cursor);
	const paged = [...five.entries, ...second.entries].map((entry) => entry.resourceUrl);
	expect(new Set(paged).size).toBe(paged.length);
	expect([...five.entries, ...second.entries].filter((entry) => idOf(entry) === fileIds.viele())).toHaveLength(4);

	// The web dialog: "Load more" shows the fourth place of the first file.
	await login(page, bob);
	const group = await searchInDialog(page, word);
	const more = page.getByRole('button', { name: /load more/i }).or(page.getByRole('link', { name: /load more/i })).first();
	await expect(more).toBeVisible();
	await more.click();
	await expect(group.locator('a[href]').filter({ hasText: 'viele-stellen.ogg' })).toHaveCount(4);
	await screenshot(page, 'search-s2', testInfo);
});

test('S3 langer Ausschnitt bei 375 px: das Kennzeichen bleibt sichtbar @preview', async ({ page }, testInfo) => {
	only(testInfo, ['w375-light', 'w375-dark']);
	const word = required('AVS_SPEECH_WORD');
	await login(page, users.bob());
	const group = await searchInDialog(page, word);
	const hit = group.locator('a[href]').filter({ hasText: PRELIMINARY_MARK }).first();
	await expect(hit).toBeVisible();

	// The client cuts the subline at its end; the mark stands before the excerpt
	// and has to lie inside every box that clips it.
	const place = await hit.evaluate((anchor, pattern) => {
		const re = new RegExp(pattern);
		const walker = document.createTreeWalker(anchor, NodeFilter.SHOW_TEXT);
		for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
			const found = re.exec(node.textContent ?? '');
			if (found === null) {
				continue;
			}
			const range = document.createRange();
			range.setStart(node, found.index);
			range.setEnd(node, found.index + found[0].length);
			const mark = range.getBoundingClientRect();
			let clip = window.innerWidth;
			for (let element = node.parentElement; element !== null; element = element.parentElement) {
				const style = getComputedStyle(element);
				if (style.overflowX !== 'visible' || style.textOverflow === 'ellipsis') {
					clip = Math.min(clip, element.getBoundingClientRect().right - Number.parseFloat(style.paddingRight || '0'));
				}
				if (element === anchor) {
					break;
				}
			}
			return { width: mark.width, right: mark.right, clip };
		}
		return null;
	}, MARK);
	expect(place, 'the hit carries the mark in its text').not.toBeNull();
	expect(place?.width ?? 0).toBeGreaterThan(0);
	expect(place?.right ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual((place?.clip ?? 0) + 1);
	await screenshot(page, 'search-s3', testInfo);
});

// The test results (debug on, switch sample_visible on, ci/seed.sh) carry the
// fixed sample text, which shares no indexed word with the speech clip (the
// index drops stop words and joins terms with AND), so a single term never
// brings both into one list. Two searches of the same user instead: bob
// receives tone-90s.webm with its test result and owns the speech files.
test('S4 Testtreffer ohne Vorläufig, echter Treffer mit @preview', async ({ page }, testInfo) => {
	only(testInfo, ['w1280-light']);
	const bob = users.bob();
	const samples = await searchAs(bob, 'Audiosuche');
	expect(samples.length).toBeGreaterThanOrEqual(1);
	for (const entry of samples) {
		expect(entry.subline).toMatch(SAMPLE_MARK);
		expect(entry.subline).not.toMatch(PRELIMINARY_MARK);
	}
	const real = await searchAs(bob, required('AVS_SPEECH_WORD'));
	expect(real.length).toBeGreaterThanOrEqual(1);
	for (const entry of real) {
		expect(entry.subline).toMatch(PRELIMINARY_SUBLINE);
		expect(entry.subline).not.toMatch(SAMPLE_MARK);
	}

	await login(page, bob);
	const group = await searchInDialog(page, 'Audiosuche');
	await expect(group.locator('a[href]').filter({ hasText: SAMPLE_MARK }).first()).toBeVisible();
	await expect(group.locator('a[href]').filter({ hasText: PRELIMINARY_MARK })).toHaveCount(0);
	await screenshot(page, 'search-s4', testInfo);
});

test('S5 Datei mit Grund no_speech erscheint nie in der Suche @preview', async ({ page }, testInfo) => {
	only(testInfo, ['w1280-light']);
	test.setTimeout(STATE_WITHIN_MS + 2 * 60_000);
	const alice = users.alice();
	await login(page, alice);
	// First the file is done (its page names the reason), then nothing finds it.
	await expectState(page, playAt(fileIds.stille(), 0), T.T5.en);
	for (const term of [required('AVS_SPEECH_WORD'), 'Audiosuche', 'stille']) {
		expect((await searchAs(alice, term)).map(idOf)).not.toContain(fileIds.stille());
	}
	await page.goto('/index.php/apps/files');
	await searchInDialog(page, required('AVS_SPEECH_WORD'));
	await screenshot(page, 'search-s5', testInfo);
});

// ---------------------------------------------------------------------------
// Playback page, states that stay (UI-SPEC surface 2), in the projects of
// their row. The English grid opens the file as its owner, the review
// projects as dora (high contrast), elke (German) or fleur (French), who
// received the files from ci/seed.sh.

test('P1 Abspielseite eines Treffers: Ausschnitt, danach Hinweis T2, Kontrast mindestens 4,5:1 @preview @screenshot', async ({ page }, testInfo) => {
	only(testInfo, [...GRID, 'hc-1280']);
	test.setTimeout(STATE_WITHIN_MS + 2 * 60_000);
	const word = required('AVS_SPEECH_WORD');
	let hit: Entry | undefined;
	await expect
		.poll(
			async () => {
				hit = hitOf(await searchAs(users.bob(), word), fileIds.viele());
				return hit !== undefined;
			},
			{ timeout: STATE_WITHIN_MS, intervals: [STATE_POLL_MS] },
		)
		.toBe(true);
	const target = new URL((hit as Entry).resourceUrl, BASE_URL);

	await login(page, reviewer(testInfo) ?? users.bob());
	await page.goto(target.pathname + target.search);
	await expect(excerptQuote(page)).toContainText(new RegExp(escapeRegExp(word), 'i'));
	// The note stands after the excerpt in the DOM (UI-SPEC accessibility), once.
	await expect(page.locator('section.avs-excerpt > blockquote.avs-excerpt__text + p.avs-excerpt__note')).toHaveCount(1);
	await expect(excerptNote(page)).toHaveCount(1);
	await expect(excerptNote(page)).toHaveText(T.T2[languageOf(testInfo)]);

	expectContrastSelfTest();
	const measured = await excerptNoteContrast(page);
	testInfo.annotations.push({
		type: 'contrast',
		description: `${testInfo.project.name}: ${measured.ratio.toFixed(2)}:1, text ${measured.fg}, backgrounds ${measured.backgrounds.join(' | ')}`,
	});
	expect(measured.ratio, 'note contrast below 4.5:1: use --color-main-text (UI-SPEC)').toBeGreaterThanOrEqual(4.5);

	await expectMediaQuiet(page);
	await screenshot(page, 'play-p1', testInfo);
});

const REASON_STATES = [
	{ id: 'P5', title: 'keine Sprache', text: T.T5, file: fileIds.stille, projects: [...GRID, 'hc-1280'] },
	{ id: 'P6', title: 'beschädigt', text: T.T6, file: fileIds.kaputt, projects: ['w1280-light', 'w1280-dark', 'w375-light', 'fr-w375-light'] },
	{ id: 'P7', title: 'geschützt', text: T.T7, file: fileIds.geschuetzt, projects: ['w1280-light', 'w1280-dark', 'w375-light', 'fr-w375-light'] },
	{ id: 'P8', title: 'Sprache nicht unterstützt', text: T.T8, file: fileIds.tuerkisch, projects: ['w1280-light', 'w1280-dark', 'w375-light'] },
	{ id: 'P10', title: 'anderer Grund (no_audio)', text: T.T11, file: fileIds.ohneTon, projects: ['w1280-light'] },
] as const;

for (const state of REASON_STATES) {
	test(`${state.id} Abspielseite: ${state.title} @preview @screenshot`, async ({ page }, testInfo) => {
		only(testInfo, state.projects);
		test.setTimeout(STATE_WITHIN_MS + 2 * 60_000);
		await login(page, reviewer(testInfo) ?? users.alice());
		await expectState(page, playAt(state.file(), 0), state.text[languageOf(testInfo)]);
		// A reason is a sentence in the grey block, never a text of its own (no blockquote, no note).
		await expect(excerptQuote(page)).toHaveCount(0);
		await expect(excerptNote(page)).toHaveCount(0);
		await expect(excerptHint(page)).toBeVisible();
		await expectMediaQuiet(page);
		// A7 and a playback error of the browser can come together (UI-SPEC):
		// the format banner shows, the medium goes, the block stays below it.
		const banner = page.locator('#avs-banner-format');
		if (await banner.isVisible()) {
			await expect(excerptHint(page)).toBeVisible();
			testInfo.annotations.push({ type: 'format banner', description: `${state.id} with the format banner` });
		}
		if (state.id === 'P10') {
			// The raw reason never reaches the page.
			expect(await page.content()).not.toContain('no_audio');
		}
		await screenshot(page, `play-${state.id.toLowerCase()}`, testInfo);
	});
}

// ---------------------------------------------------------------------------
// The core path (plan 03-02), once.

test.describe.serial('phase 3 core path @preview', () => {
	let fileId = '';
	let hit: Entry | undefined;

	test.beforeEach(({}, testInfo) => {
		// One upload per run: the path changes the instance, the grid would repeat it six times.
		only(testInfo, [ONCE]);
	});

	test('upload is found as preliminary within minutes @preview', async () => {
		test.setTimeout(FOUND_WITHIN_MS + 2 * 60_000);
		const word = required('AVS_SPEECH_WORD');
		fileId = await upload(users.alice(), required('AVS_SPEECH_DE'), FILE_NAME, 'audio/wav');

		await expect
			.poll(
				async () => {
					const entry = hitOf(await searchAs(users.alice(), word), fileId);
					return entry !== undefined && PRELIMINARY_SUBLINE.test(entry.subline);
				},
				{ timeout: FOUND_WITHIN_MS, intervals: [POLL_EVERY_MS] },
			)
			.toBe(true);
		hit = hitOf(await searchAs(users.alice(), word), fileId);
		expect(hit?.subline).toMatch(PRELIMINARY_SUBLINE);
	});

	test('click jumps to the word @preview', async ({ page }) => {
		const word = required('AVS_SPEECH_WORD');
		expect(hit, 'the first test found the hit').toBeDefined();
		const target = new URL((hit as Entry).resourceUrl, BASE_URL);
		const t = Number(target.searchParams.get('t'));
		expect(Number.isFinite(t)).toBe(true);

		await login(page, users.alice());
		await page.goto(target.pathname + target.search);

		await expect(excerptQuote(page)).toContainText(new RegExp(escapeRegExp(word), 'i'));
		await expect(excerptNote(page)).toHaveText(T.T2.en);

		await expectMediaSettled(page);
		const at = await position(page)();
		expect(at).toBeGreaterThanOrEqual(t - BEFORE_SECONDS);
		expect(at).toBeLessThanOrEqual(t + AFTER_SECONDS);
		const duration = await page
			.locator('#avs-media')
			.evaluate((element: HTMLMediaElement) => element.duration);
		expect(t).toBeLessThan(duration);
	});

	test('a user without access finds nothing @preview', async () => {
		const word = required('AVS_SPEECH_WORD');
		expect(fileId, 'the first test uploaded the clip').not.toBe('');
		// Counter check: the owner still finds the clip, so an empty list below is about access.
		expect(hitOf(await searchAs(users.alice(), word), fileId)).toBeDefined();
		const entries = await searchAs(users.mallory(), word);
		expect(entries.map(idOf)).not.toContain(fileId);
	});
});

// ---------------------------------------------------------------------------
// A long file in work and the leak probes, once. lang-40min.ogg carries
// speech in all four pieces of 10 min, so the window in which it is partial
// lasts minutes; it is uploaded here and not by the seed, because by now the
// seeded files are long done.

test.describe.serial('phase 3 partial transcript and leak probes @preview', () => {
	let longId = '';
	let unknownBlock = '';

	test.beforeEach(({}, testInfo) => {
		only(testInfo, [ONCE]);
	});

	test('P4 Datei ohne fertiges Stück: A5, Referenz der Leck-Proben @preview', async ({ page }, testInfo) => {
		longId = await upload(users.alice(), join(required('AVS_MEDIA_DIR'), LONG_FILE), LONG_FILE, 'audio/ogg');
		await login(page, users.alice());
		// Right after the upload no piece of 10 min is done: unknown, queued or
		// running all answer A5, the text of the stock (UI-SPEC A5).
		await page.goto(playAt(longId, EARLY_SECONDS));
		await expect(excerptHint(page)).toHaveText(T.A5.en);
		await expect(excerptQuote(page)).toHaveCount(0);
		unknownBlock = await excerptBlock(page).evaluate((element) => element.outerHTML);
		await expectMediaQuiet(page);
		await shots(page, 'play-p4', testInfo, [[1280, 'light'], [1280, 'dark']]);
	});

	test('P3 und P2 Teiltranskript: hinter dem fertigen Stück T4, davor Ausschnitt mit T3 statt T2 @preview', async ({ page }, testInfo) => {
		test.setTimeout(PARTIAL_WITHIN_MS + 3 * 60_000);
		expect(longId, 'P4 uploaded the long file').not.toBe('');
		await login(page, users.alice());

		// A4 at 39 min shows only while a piece is done and the last is not, so
		// it also proves that the file is still in work for P2 right after.
		let seen = 'nothing';
		await expect
			.poll(
				async () => {
					await page.goto(playAt(longId, LATE_SECONDS));
					const sentence = await excerptSentence(page);
					if (sentence === T.T4.en) {
						seen = 'partial';
					} else if ((await excerptQuote(page).count()) > 0) {
						seen = 'done';
					} else {
						seen = 'not yet';
					}
					return seen;
				},
				{ timeout: PARTIAL_WITHIN_MS, intervals: [PARTIAL_POLL_MS] },
			)
			.not.toBe('not yet');
		expect(seen, 'the file was done before a look caught it partial').toBe('partial');
		await expect(excerptHint(page)).toHaveText(T.T4.en);
		await expectMediaQuiet(page);
		await shots(page, 'play-p3', testInfo, [[1280, 'light'], [1280, 'dark'], [375, 'light']]);

		await page.goto(playAt(longId, EARLY_SECONDS));
		await expect(excerptQuote(page)).toBeVisible();
		await expect(excerptNote(page)).toHaveCount(1);
		await expect(excerptNote(page)).toHaveText(T.T3.en);
		await expect(excerptNote(page)).not.toHaveText(T.T2.en);
		await expectMediaQuiet(page);
		await shots(page, 'play-p2', testInfo, ALL_VARIANTS);
	});

	test('P11 ausgeschlossener Nutzer mit Grund-Datei: Block byte-gleich zu P4, keine /excerpt-Anfrage @preview', async ({ page }, testInfo) => {
		test.setTimeout(STATE_WITHIN_MS + 3 * 60_000);
		expect(unknownBlock, 'P4 kept the block of a file without transcript').not.toBe('');
		const stille = fileIds.stille();

		// Positive control of the log probe: the owner opens the same file, the
		// page asks the container, and its access log has a POST /excerpt.
		await login(page, users.alice());
		await expectState(page, playAt(stille, 0), T.T5.en);
		const control = { from: new Date().toISOString(), to: '' };
		await page.goto(playAt(stille, 0));
		await expect(excerptHint(page)).toHaveText(T.T5.en);
		control.to = new Date().toISOString();

		// oskar reads the file through a share and is excluded: A5 without asking the container.
		await switchUser(page, users.oskar());
		const probe = { from: new Date().toISOString(), to: '' };
		await page.goto(playAt(stille, 0));
		await expect(excerptBlock(page)).toBeVisible();
		probe.to = new Date().toISOString();
		const block = await excerptBlock(page).evaluate((element) => element.outerHTML);
		expect(block, 'the block of an excluded user with a reason equals the one of a file without transcript').toBe(unknownBlock);
		writeFileSync(required('AVS_LEAK_PROBE'), JSON.stringify({ fileId: stille, probe, control }));
		await expectMediaQuiet(page);
		await screenshot(page, 'play-p11', testInfo);
	});

	// deploy-harp cannot reach P12: the container keeps one reference per file
	// id and reads it as the owner (file_ref.reader_uid); a revoked share does
	// not touch it, and a file whose reference is not active cannot be read by
	// the user either in this topology. The real probe on the play page runs
	// in discovery-e2e.yml, phase play-leak (ci/discovery/playpage.sh, plan
	// 03-18b, D-03-24): Samba with DENY READ before the first read (never
	// active) and the revoked Samba copy after reconcile --reprove, each with a
	// positive control and the block compared byte for byte and by structure.
	// The unit evidence stays: 03-14 (known false for every reference that is
	// not active) and 03-16 (known false is A5, byte-equal).
	const playLeak = 'discovery-e2e.yml phase play-leak, ci/discovery/playpage.sh (plan 03-18b, D-03-24)';
	test(
		'P12 Verweis nicht active, Datei über anderen Weg lesbar: Block gleich P4 @preview',
		{ annotation: { type: 'covered by', description: playLeak } },
		() => {
			test.skip(true, playLeak);
		},
	);

	// disk_full needs a full disk in the container, which CI cannot make
	// without an intervention into the running ExApp. Covered by unit tests:
	// 03-13 (the worker defers with disk_full and retries after
	// DISK_FULL_RETRY_SECONDS) and 03-16/03-16b (the page maps disk_full to
	// A13 and shows T12 in DE, EN and FR).
	test.fixme('P13 Abspielseite A13 zu wenig Speicherplatz: T12 @preview', () => {});
});

// ---------------------------------------------------------------------------
// A10 with the number of hours, once: lang-12h01.flac is longer than the
// default of 12 hours (plural). Lowering the limit to 1 queues nothing again
// (only a higher limit does, plan 03-15), and the page names the limit of now:
// the same file then reads 1 hour (singular). The limit goes back to 12 at the end.

test.describe.serial('phase 3 too long with the limit of the instance @preview', () => {
	test.beforeEach(({}, testInfo) => {
		only(testInfo, [ONCE]);
	});

	test('P9 überlang: Plural bei 12, Singular bei 1, T10 im selben Absatz @preview', async ({ page }, testInfo) => {
		test.setTimeout(STATE_WITHIN_MS + LIMIT_WITHIN_MS + 5 * 60_000);
		const lang = fileIds.lang();
		await login(page, users.alice());
		await expectState(page, playAt(lang, 0), tooLong('en', DEFAULT_LIMIT_HOURS));
		await expect(excerptHint(page)).toHaveCount(1);
		await expectMediaQuiet(page);
		await shots(page, 'play-p9', testInfo, ALL_VARIANTS);

		await switchUser(page, users.elke());
		await page.goto(playAt(lang, 0));
		await expect(excerptHint(page)).toHaveText(tooLong('de', DEFAULT_LIMIT_HOURS));
		await switchUser(page, users.fleur());
		await page.setViewportSize({ width: 375, height: 900 });
		await page.goto(playAt(lang, 0));
		await expect(excerptHint(page)).toHaveText(tooLong('fr', DEFAULT_LIMIT_HOURS));
		await expectMediaQuiet(page);
		await screenshot(page, 'play-p9', testInfo, 'fr-w375-light');
		await page.setViewportSize({ width: 1280, height: 900 });

		try {
			occ('app_api:app:config:set', BACKEND_APP_ID, 'max_duration_hours', '--value=1');
			await switchUser(page, users.alice());
			await expectState(page, playAt(lang, 0), tooLong('en', 1), LIMIT_WITHIN_MS);
			await expectMediaQuiet(page);
			await screenshot(page, 'play-p9-singular', testInfo);
			await switchUser(page, users.elke());
			await page.goto(playAt(lang, 0));
			await expect(excerptHint(page)).toHaveText(tooLong('de', 1));
			await switchUser(page, users.fleur());
			await page.goto(playAt(lang, 0));
			await expect(excerptHint(page)).toHaveText(tooLong('fr', 1));
		} finally {
			occ('app_api:app:config:set', BACKEND_APP_ID, 'max_duration_hours', `--value=${DEFAULT_LIMIT_HOURS}`);
		}
	});
});
