// Phase 4, the sidecar, the subtitle track and the contrast of the export
// section in the real stack (plan 04-17, 04-UI-SPEC "Prüfvertrag": E1 to E7,
// T1 track, contrast gate; success criterion 4).
//
// The selectors come from php/templates/play.php and php/js/play.js: the
// button #avs-sidecar, the seven banners #avs-sidecar-e1 to -e7 inside
// #avs-sidecar-result (E1 role status, the others role alert with the
// focus), span.avs-export__name for the checked name, <track kind="subtitles">
// on the video. Every visible text is one of the approved texts of
// 04-UI-SPEC (EXPORT_TEXTS in helpers.ts); every case is reached the way a
// user meets it (rights taken away after the page was built, the container
// stopped), only E5 is answered by the test (see there).
//
// Everything that changes the instance (the rights or the download switch of
// carol's share, the stopped container) goes back in a finally block
// (T-04-52). No fixed waits: web-first assertions, waitForResponse and
// expect.poll only. The test of the rate limit runs last, so no other POST of
// the same user lands in its minute.
import { expect, test, type Locator, type Page, type Response, type TestInfo } from '@playwright/test';
import {
	ABLAGE_FILE,
	ABLAGE_FOLDER,
	ABLAGE_PERMISSIONS,
	ablageShare,
	ALL_VARIANTS,
	apiAs,
	deleteFile,
	EXPORT_TEXTS as T,
	expectContrastSelfTest,
	exportName,
	exportRoutes,
	exportText,
	expectTranscript,
	fileIds,
	fill,
	firstCue,
	login,
	phase4User,
	playAt,
	READ_ONLY,
	requestToken,
	S7_VIDEO_NAME,
	screenshot,
	screenshotVariants,
	sha256OfFile,
	textContrast,
	TRANSCRIPT_WITHIN_MS,
	updateShare,
	users,
	withContainerStopped,
	type User,
} from './helpers';

test.skip(process.env.AVS_PHASE4_E2E !== '1', 'phase 4 runs in the step @phase4 of deploy-harp.yml');

const GRID = ['w375-light', 'w375-dark', 'w768-light', 'w768-dark', 'w1280-light', 'w1280-dark'];
const ONCE = 'w1280-light';
const CONTRAST_PROJECTS = [...GRID, 'hc-1280'];
// 04-UI-SPEC T1: the track in Chromium and in Firefox.
const TRACK_PROJECTS = ['w1280-light', 'firefox-w1280-light'];
const START_SECONDS = 1;
// The track shows the cue at the time of the VTT within 100 ms (04-UI-SPEC T1).
const CUE_TOLERANCE_SECONDS = 0.1;
// UserRateLimit(limit: 10, period: 60) of the sidecar route: the eleventh POST is refused.
const RATE_LIMIT_POSTS = 11;
const PREPARED_MS = TRANSCRIPT_WITHIN_MS + 5 * 60_000;

function only(testInfo: TestInfo, projects: readonly string[]): void {
	test.skip(!projects.includes(testInfo.project.name), `this state is pictured in ${projects.join(', ')}`);
}

const sidecarButton = (page: Page): Locator => page.locator('#avs-sidecar');
const resultBanner = (page: Page, number: number): Locator => page.locator(`#avs-sidecar-result #avs-sidecar-e${number}`);

/** Click the sidecar button and answer the response of its POST. */
async function clickSidecar(page: Page, fileId: string): Promise<Response> {
	const answered = page.waitForResponse(
		(response) => response.url().includes(`/sidecar/${fileId}`) && response.request().method() === 'POST',
	);
	await sidecarButton(page).click();
	return answered;
}

/** A banner says what happened in words: no raw status code, no JSON (04-UI-SPEC E3 to E7). */
async function expectPlainWords(banner: Locator): Promise<void> {
	const text = await banner.innerText();
	expect(text, 'a banner shows a raw status code').not.toMatch(/\b(201|400|403|404|409|429|503)\b/);
	expect(text, 'a banner shows JSON').not.toMatch(/[{}]|"reason"|name_too_long|not_writable/);
}

/** An error banner of the sidecar: visible, an alert with the focus, title T29b and the sentence of its case. */
async function expectErrorBanner(page: Page, number: number, sentence: string, title: string): Promise<Locator> {
	const banner = resultBanner(page, number);
	await expect(banner).toBeVisible();
	await expect(banner).toHaveAttribute('role', 'alert');
	await expect(banner.locator('p.avs-banner__title')).toHaveText(title);
	await expect(banner.locator('p.avs-banner__text')).toHaveText(sentence);
	await expect(banner).toBeFocused();
	await expect(sidecarButton(page)).toBeEnabled();
	await expect(sidecarButton(page)).not.toHaveAttribute('aria-busy', 'true');
	await expectPlainWords(banner);
	return banner;
}

/** The WebDAV status of a path of the user: 200 when the file is there, 404 when not. */
async function davStatus(user: User, path: string): Promise<number> {
	const api = await apiAs(user);
	try {
		const encoded = path.split('/').map(encodeURIComponent).join('/');
		return (await api.get(`/remote.php/dav/files/${encodeURIComponent(user.name)}/${encoded}`)).status();
	} finally {
		await api.dispose();
	}
}

/** The text of a file of the user over WebDAV. */
async function davText(user: User, path: string): Promise<string> {
	const api = await apiAs(user);
	try {
		const encoded = path.split('/').map(encodeURIComponent).join('/');
		const response = await api.get(`/remote.php/dav/files/${encodeURIComponent(user.name)}/${encoded}`);
		expect(response.status(), `WebDAV GET of ${path}`).toBe(200);
		return response.text();
	} finally {
		await api.dispose();
	}
}

/** The medium shows a decoded frame and is not seeking: a picture of the track never catches a half frame. */
async function expectFrameShown(page: Page): Promise<void> {
	await expect
		.poll(
			() =>
				page.locator('#avs-media').evaluate(
					(element: HTMLMediaElement) => element.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && !element.seeking,
				),
			{ timeout: 15_000 },
		)
		.toBe(true);
}

// ---------------------------------------------------------------------------
// E1 and E2: the sidecar is laid down once, the second click never touches it.

test('E1 und E2 Ablage legt die VTT an, der zweite Klick zeigt die Kollision und die Datei bleibt byte-gleich @phase4', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const { user, language } = phase4User(testInfo);
	const video = fileIds.s7Video();
	const name = exportName(S7_VIDEO_NAME, 'vtt');
	await expectTranscript(user, video);
	// The recipient's sidecar lands in the recipient's home; one of an earlier attempt would turn E1 into E2.
	expect([204, 404]).toContain(await deleteFile(user, name));
	await login(page, user);
	await page.goto(playAt(video, START_SECONDS));
	await expect(sidecarButton(page)).toBeVisible();

	// E1: created, a status banner with the name, the focus stays on the button.
	expect((await clickSidecar(page, video)).status()).toBe(201);
	const created = resultBanner(page, 1);
	await expect(created).toBeVisible();
	await expect(created).toHaveAttribute('role', 'status');
	await expect(created.locator('p.avs-banner__title')).toHaveText(fill(T.T21[language], name));
	await expect(created.locator('.avs-export__name')).toHaveText(name);
	await expect(created.getByRole('link', { name: T.SHOW_IN_FILES[language] })).toBeVisible();
	await expect(sidecarButton(page)).toBeFocused();
	await expect(sidecarButton(page)).toBeEnabled();
	// The file is there under the name of T21, as the VTT with the draft note.
	const content = await davText(user, name);
	expect(content.startsWith(`WEBVTT\n\nNOTE\n${T.T35[language]}\n`), 'the sidecar is the VTT with T35 in its NOTE').toBe(true);
	const before = await sha256OfFile(user, name);
	await screenshotVariants(page, 'e1', testInfo, ALL_VARIANTS, created);

	// E2: the same click again is a collision, nothing is written.
	expect((await clickSidecar(page, video)).status()).toBe(409);
	const collision = await expectErrorBanner(page, 2, fill(T.T22b[language], name), T.T22a[language]);
	await expect(created).toBeHidden();
	expect(await sha256OfFile(user, name), 'the second click left the sidecar byte for byte as it was').toBe(before);
	await screenshotVariants(page, 'e2', testInfo, ALL_VARIANTS, collision);
});

test('E2 Kollision in Hochkontrast und Französisch @phase4 @screenshot', async ({ page }, testInfo) => {
	only(testInfo, ['hc-1280', 'fr-w375-light']);
	test.setTimeout(PREPARED_MS);
	const { user, language } = phase4User(testInfo);
	const video = fileIds.s7Video();
	const name = exportName(S7_VIDEO_NAME, 'vtt');
	await expectTranscript(user, video);
	await login(page, user);
	await page.goto(playAt(video, START_SECONDS));
	await expect(sidecarButton(page)).toBeVisible();
	// The first click lays the sidecar down, unless an earlier attempt already did.
	expect([201, 409]).toContain((await clickSidecar(page, video)).status());
	const before = await sha256OfFile(user, name);
	expect((await clickSidecar(page, video)).status()).toBe(409);
	await expectErrorBanner(page, 2, fill(T.T22b[language], name), T.T22a[language]);
	expect(await sha256OfFile(user, name)).toBe(before);
	await screenshot(page, 'e2', testInfo);
});

// ---------------------------------------------------------------------------
// E3 and E4: carol's rights change after the page was built.

test('E3 Schreibrecht nach dem Seitenaufbau entzogen: T29b und T23, nichts angelegt @phase4', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const alice = users.alice();
	const carol = users.carol();
	const ablage = fileIds.ablage();
	const shareId = await ablageShare();
	const target = `${ABLAGE_FOLDER}/${exportName(ABLAGE_FILE, 'vtt')}`;
	await expectTranscript(carol, ablage);
	await login(page, carol);
	await page.goto(playAt(ablage, START_SECONDS));
	await expect(sidecarButton(page)).toBeVisible();

	await updateShare(alice, shareId, { permissions: READ_ONLY });
	try {
		const answer = await clickSidecar(page, ablage);
		expect(answer.status()).toBe(403);
		await expectErrorBanner(page, 3, T.T23.en, T.T29b.en);
		expect(await davStatus(alice, target), 'no sidecar was written into the folder').toBe(404);
		await screenshot(page, 'e3', testInfo);
	} finally {
		await updateShare(alice, shareId, { permissions: ABLAGE_PERMISSIONS });
	}
});

test('E4 Download-Sperre nach dem Seitenaufbau gesetzt: T29b und T24, nichts angelegt @phase4', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const alice = users.alice();
	const carol = users.carol();
	const ablage = fileIds.ablage();
	const shareId = await ablageShare();
	const target = `${ABLAGE_FOLDER}/${exportName(ABLAGE_FILE, 'vtt')}`;
	await expectTranscript(carol, ablage);
	await login(page, carol);
	await page.goto(playAt(ablage, START_SECONDS));
	await expect(sidecarButton(page)).toBeVisible();

	await updateShare(alice, shareId, { download: false });
	try {
		const answer = await clickSidecar(page, ablage);
		expect(answer.status()).toBe(403);
		await expectErrorBanner(page, 4, T.T24.en, T.T29b.en);
		expect(await davStatus(alice, target), 'no sidecar was written into the folder').toBe(404);
		await screenshot(page, 'e4', testInfo);
	} finally {
		await updateShare(alice, shareId, { download: true });
	}
});

// ---------------------------------------------------------------------------
// E5: the name would be too long.

// The real stack cannot make this answer: Nextcloud refuses a file name of
// more than 250 bytes (OC\Files\FilenameValidator, "oc_filecache has a 250
// char length limit", stable33), and the sidecar name of a medium with an
// audio or video extension is at most 3 bytes longer (".wav" becomes
// ".de.vtt"), so it never passes the 255 bytes of SidecarWriter::MAX_NAME_BYTES.
// The server side of 400 name_too_long is proven by ExportControllerTest
// (259 bytes, positive control at 255, plan 04-12). Here the browser gets
// the answer of the route from the test, so the page proves its part: the
// banner E5 with T26 in words.
test(
	'E5 Name zu lang: Banner T29b und T26 aus der Antwort 400 name_too_long @phase4',
	{ annotation: { type: 'answered by the test', description: 'a 400 name_too_long cannot happen with a real file name (250-byte limit of Nextcloud); ExportControllerTest proves the server side' } },
	async ({ page }, testInfo) => {
		only(testInfo, [ONCE]);
		test.setTimeout(PREPARED_MS);
		const { user, language } = phase4User(testInfo);
		const video = fileIds.s7Video();
		await expectTranscript(user, video);
		await login(page, user);
		await page.goto(playAt(video, START_SECONDS));
		await expect(sidecarButton(page)).toBeVisible();
		const route = `**${exportRoutes(video).sidecar}`;
		await page.route(route, (intercepted) =>
			intercepted.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ reason: 'name_too_long' }) }),
		);
		try {
			expect((await clickSidecar(page, video)).status()).toBe(400);
			await expectErrorBanner(page, 5, T.T26[language], T.T29b[language]);
			await screenshot(page, 'e5', testInfo);
		} finally {
			await page.unroute(route);
		}
	},
);

// ---------------------------------------------------------------------------
// E7: the container is stopped after the page was built.

test('E7 Container nach dem Seitenaufbau gestoppt: T29b und T25 @phase4', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS + 10 * 60_000);
	const { user, language } = phase4User(testInfo);
	const video = fileIds.s7Video();
	await expectTranscript(user, video);
	await login(page, user);
	await page.goto(playAt(video, START_SECONDS));
	await expect(sidecarButton(page)).toBeVisible();
	await withContainerStopped(
		async () => {
			expect((await clickSidecar(page, video)).status()).toBe(503);
			await expectErrorBanner(page, 7, T.T25[language], T.T29b[language]);
			await screenshot(page, 'e7', testInfo);
		},
		user,
		video,
	);
});

// ---------------------------------------------------------------------------
// The draft track in the player, in Chromium and Firefox.

test('Spur im Player: Label "Deutsch, Untertitel-Entwurf", standardmäßig aus, nach Einschalten der Cue zur Zeit der VTT @phase4 @firefox', async ({ page }, testInfo) => {
	only(testInfo, TRACK_PROJECTS);
	test.setTimeout(PREPARED_MS);
	const { user } = phase4User(testInfo);
	const video = fileIds.s7Video();
	await expectTranscript(user, video);
	// Cue text and time come out of the export of the same file, never typed in.
	const cue = firstCue(await exportText(user, video, 'vtt'));
	await login(page, user);
	await page.goto(playAt(video, 0));

	const media = page.locator('video#avs-media');
	const track = media.locator('track[kind="subtitles"]');
	await expect(track).toHaveCount(1);
	await expect(track).toHaveAttribute('label', fill(T.T31.de, T.T32.de));
	await expect(track).toHaveAttribute('srclang', 'de');
	await expect(media.locator('track[default]')).toHaveCount(0);
	const mode = await media.evaluate((element: HTMLMediaElement) => element.textTracks[0]?.mode ?? 'missing');
	expect(['disabled', 'hidden'], 'the draft track is off by default').toContain(mode);
	const label = await media.evaluate((element: HTMLMediaElement) => element.textTracks[0]?.label ?? '');
	expect(label, 'the menu of the player names the track').toBe(fill(T.T31.de, T.T32.de));

	// What the user does in the menu of the native controls: switch it on.
	await media.evaluate((element: HTMLMediaElement) => {
		element.textTracks[0].mode = 'showing';
	});
	await expect
		.poll(() => media.evaluate((element: HTMLMediaElement) => element.textTracks[0].cues?.length ?? 0), { timeout: 15_000 })
		.toBeGreaterThan(0);
	const loaded = await media.evaluate((element: HTMLMediaElement) => {
		const first = element.textTracks[0].cues?.[0] as VTTCue;
		return { start: first.startTime, text: first.text };
	});
	expect(Math.abs(loaded.start - cue.start), 'the first cue starts at the time of the VTT').toBeLessThanOrEqual(CUE_TOLERANCE_SECONDS);
	expect(loaded.text).toBe(cue.text);

	const at = cue.start + CUE_TOLERANCE_SECONDS / 2;
	await media.evaluate((element: HTMLMediaElement, time: number) => {
		element.currentTime = time;
	}, at);
	await expect
		.poll(
			() =>
				media.evaluate((element: HTMLMediaElement) =>
					Array.from(element.textTracks[0].activeCues ?? [], (active) => (active as VTTCue).text),
				),
			{ timeout: 15_000 },
		)
		.toContain(cue.text);
	const position = await media.evaluate((element: HTMLMediaElement) => element.currentTime);
	expect(Math.abs(position - at)).toBeLessThanOrEqual(CUE_TOLERANCE_SECONDS);
	await expectFrameShown(page);
	await screenshot(page, 'track', testInfo);
});

// ---------------------------------------------------------------------------
// The contrast gate of the export section (04-UI-SPEC, Kontrast-Gate).

test('Kontrast: Erklärsatz, Ablage-Satz und Knöpfe mindestens 4,5:1 in hell, dunkel und Hochkontrast @phase4 @screenshot', async ({ page }, testInfo) => {
	only(testInfo, CONTRAST_PROJECTS);
	test.setTimeout(PREPARED_MS);
	expectContrastSelfTest();
	const { user } = phase4User(testInfo);
	const video = fileIds.s7Video();
	await expectTranscript(user, video);
	await login(page, user);
	await page.goto(playAt(video, START_SECONDS));
	await expect(sidecarButton(page)).toBeVisible();
	const parts: Array<[string, Locator]> = [
		['.avs-export__note', page.locator('section.avs-export p.avs-export__note')],
		['.avs-export__hint', page.locator('section.avs-export .avs-export__sidecar > p.avs-export__hint')],
		['download button', page.locator('section.avs-export a.avs-export__download').first()],
		['sidecar button', sidecarButton(page)],
	];
	for (const [label, locator] of parts) {
		await expect(locator).toBeVisible();
		const measured = await textContrast(locator);
		testInfo.annotations.push({
			type: 'contrast',
			description: `${testInfo.project.name} ${label}: ${measured.ratio.toFixed(2)}:1, text ${measured.fg}, backgrounds ${measured.backgrounds.join(' | ')}`,
		});
		expect(measured.ratio, `${label} below 4.5:1: use --color-main-text (04-UI-SPEC)`).toBeGreaterThanOrEqual(4.5);
	}
});

// ---------------------------------------------------------------------------
// E6 last: after it the sidecar route of this user stays refused for a minute.

test('E6 Rate-Limit nach schnellen POSTs: T29b und T27 @phase4', async ({ page }, testInfo) => {
	only(testInfo, [ONCE]);
	test.setTimeout(PREPARED_MS);
	const { user, language } = phase4User(testInfo);
	const video = fileIds.s7Video();
	await expectTranscript(user, video);
	await login(page, user);
	await page.goto(playAt(video, START_SECONDS));
	await expect(sidecarButton(page)).toBeVisible();
	const token = await requestToken(page);
	expect(token).not.toBe('');
	const statuses: number[] = [];
	for (let attempt = 0; attempt < RATE_LIMIT_POSTS; attempt += 1) {
		const answer = await page.request.post(exportRoutes(video).sidecar, { headers: { requesttoken: token, Accept: 'application/json' } });
		statuses.push(answer.status());
		if (answer.status() === 429) {
			break;
		}
	}
	expect(statuses, `the sidecar route refuses within ${RATE_LIMIT_POSTS} quick POSTs`).toContain(429);
	// Before the limit the sidecar of E1 is there: every earlier answer is the collision.
	expect(statuses.filter((status) => status !== 429 && status !== 409)).toEqual([]);
	expect((await clickSidecar(page, video)).status()).toBe(429);
	await expectErrorBanner(page, 6, T.T27[language], T.T29b[language]);
	await screenshot(page, 'e6', testInfo);
});
