// Phase 4, search quality in the real stack (plan 04-14, UI-SPEC 04 S6 and S7,
// SRCH-04, success criteria 1, 2 and the search part of 5).
//
// The S7 clips of ci/media/fetch_speech.py were transcribed beforehand with
// the engine chain of the container (two equal runs, plan 04-14 SUMMARY), and
// their target forms reach this spec only through AVS_S7_TARGETS
// (s7Expectations()): no sentence of a clip is typed in here. ci/seed.sh puts
// both clips into alice's files (AVS_PHASE4_MEDIA=1). Before any search the
// spec checks that the transcript in the stack carries the measured forms; if
// it does not, the run fails with "Vorbedingung S7" and not with a search error.
//
// The literal examples of the criterion (zwölf, Häuser, Haushaltsplanberatung)
// are proven on the index in plans 04-01 and 04-06; FLEURS has no compound
// with the head "Haushalt", so S7 takes the measured compound of the clip.
//
// No fixed waits: web-first assertions, waitForResponse and expect.poll only.
import { expect, request, test, type Locator, type Page, type TestInfo } from '@playwright/test';
import {
	expectFinalSearchDone,
	fold,
	foldedTokens,
	exportResponse,
	GROUP_NAME,
	login,
	openUnifiedSearch,
	s7Expectations,
	screenshotPart,
	searchField,
	searchInDialog,
	users,
	watchProviderSearches,
	wholePage,
	withLanguage,
	type S7Clip,
	type User,
} from './helpers';

test.skip(process.env.AVS_PHASE4_E2E !== '1', 'phase 4 runs in the step @phase4 of deploy-harp.yml');

const BASE_URL = process.env.NC_URL ?? 'http://localhost:8080';
const PROVIDER_SEARCH = '/search/providers/audio_video_search/search?';
// A 8 to 23 s clip is one piece; its transcript comes within minutes of the upload.
const TRANSCRIPT_WITHIN_MS = 15 * 60_000;
const POLL_EVERY_MS = 10_000;
const ONCE = 'w1280-light';
const S6_PROJECTS = ['w1280-light', 'w1280-dark'];
// The person of the person filter: carol receives s7-ziffer.wav from alice (ci/seed.sh).
const PERSON = 'carol';
// The pictures of the review are German (04-UI-SPEC, owner 16.11.2026): alice
// owns the clips and reads English elsewhere, so the dialog tests switch her.
const REVIEW_LANGUAGE = 'de' as const;
// The labels of the filters of the core search dialog, from the catalogues of
// nextcloud/server core/l10n (en source strings, de_DE.json and de.json, the
// same on stable33, stable34 and master, checked 16.11.2026).
const CORE_TEXTS = {
	thisYear: { en: /This year/, de: /Dieses Jahr/ },
	searchPeople: { en: /Search people/, de: /Personen suchen/ },
} as const;
// The term of 04-UI-SPEC S7 that has to come back without an error, hit or not.
const CLOCK_TERM = '12:30';

/** A file name part for a search term: letters and digits without accents, the rest a dash. */
function termSlug(term: string): string {
	return term
		.normalize('NFKD')
		.replace(/[̀-ͯ]/g, '')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-|-$/g, '');
}

type Entry = { title: string; subline: string; resourceUrl: string; attributes: Record<string, string> };

function only(testInfo: TestInfo, projects: readonly string[]): void {
	test.skip(!projects.includes(testInfo.project.name), `this check runs in ${projects.join(', ')}`);
}

/** The OCS search of this provider as one user; any status but 200 fails the test. */
async function search(user: User, term: string): Promise<Entry[]> {
	const api = await request.newContext({
		baseURL: BASE_URL,
		httpCredentials: { username: user.name, password: user.password, send: 'always' },
	});
	try {
		const response = await api.get(`/ocs/v2.php${PROVIDER_SEARCH}term=${encodeURIComponent(term)}&limit=20`, {
			headers: { 'OCS-APIRequest': 'true', Accept: 'application/json' },
		});
		expect(response.status(), `search for "${term}"`).toBe(200);
		const body = await response.json();
		return body.ocs.data.entries;
	} finally {
		await api.dispose();
	}
}

function ids(entries: Entry[]): string[] {
	return entries.map((entry) => String(entry.attributes?.fileId));
}

async function expectFound(user: User, term: string, clip: S7Clip): Promise<void> {
	expect(ids(await search(user, term)), `"${term}" finds ${clip.key} as ${user.name}`).toContain(clip.fileId);
}

/** The measured forms that must stand in the transcript: number word, compound and plural. */
function wantedForms(clip: S7Clip): string[] {
	return [clip.numberWord, clip.compound, ...(clip.plural === null ? [] : [clip.plural])];
}

/** The group of this provider in the main part of the dialog, not under "Partial matches". */
function mainGroup(page: Page): Locator {
	const main = page.locator('.result:not(.result--unfiltered)');
	return main.getByRole('list', { name: GROUP_NAME }).or(main.getByRole('listbox', { name: GROUP_NAME }));
}

function partialGroup(page: Page): Locator {
	const partial = page.locator('.result--unfiltered');
	return partial.getByRole('list', { name: GROUP_NAME }).or(partial.getByRole('listbox', { name: GROUP_NAME }));
}

/** Set a filter with the action and wait for the search of this provider that carries it. */
async function filtered(page: Page, parameter: 'since' | 'person', action: () => Promise<void>): Promise<void> {
	const answered = page.waitForResponse((response) => {
		if (!response.url().includes(PROVIDER_SEARCH)) {
			return false;
		}
		return new URL(response.url()).searchParams.has(parameter);
	});
	await action();
	expect((await answered).status()).toBe(200);
}

async function expectInMainPart(page: Page, fileId: string): Promise<void> {
	await expect(mainGroup(page)).toBeVisible();
	await expect(mainGroup(page).locator(`a[href*="/play/${fileId}"]`).first()).toBeVisible();
	await expect(partialGroup(page)).toHaveCount(0);
}

test.describe.serial('phase 4 search quality @phase4', () => {
	test('Vorbedingung S7: das Transkript im Stack trägt die vorab gemessenen Zielformen @phase4', async ({}, testInfo) => {
		only(testInfo, [ONCE]);
		test.setTimeout(TRANSCRIPT_WITHIN_MS + 2 * 60_000);
		for (const clip of s7Expectations()) {
			// First the transcript has to exist at all: the export answers 200 once it does.
			await expect
				.poll(async () => (await exportResponse(users.alice(), clip.fileId, 'txt')).status, {
					message: `Vorbedingung S7: ${clip.key} has no transcript after ${TRANSCRIPT_WITHIN_MS / 60_000} min`,
					timeout: TRANSCRIPT_WITHIN_MS,
					intervals: [POLL_EVERY_MS],
				})
				.toBe(200);
			const { body } = await exportResponse(users.alice(), clip.fileId, 'txt');
			const tokens = foldedTokens(body);
			const absent = wantedForms(clip).filter((form) => !tokens.has(fold(form)));
			expect(
				absent,
				`Vorbedingung S7: Transkript weicht von der Vorabmessung ab (${clip.key}, es fehlen: ${absent.join(', ')})`,
			).toEqual([]);
		}
	});

	test('S7 Zahlklasse: Ziffer, DE, EN und FR finden die Datei, gleich welche Form Parakeet schrieb @phase4', async ({}, testInfo) => {
		only(testInfo, [ONCE]);
		for (const clip of s7Expectations()) {
			for (const form of clip.numberForms) {
				await expectFound(users.alice(), form, clip);
			}
		}
	});

	test('S7 Wortformen: Singular findet den Plural und umgekehrt @phase4', async ({}, testInfo) => {
		only(testInfo, [ONCE]);
		const withPlural = s7Expectations().filter((clip) => clip.plural !== null && clip.singular !== null);
		expect(withPlural.length, 'one measured clip carries a plural').toBeGreaterThan(0);
		for (const clip of withPlural) {
			await expectFound(users.alice(), clip.singular as string, clip);
			await expectFound(users.alice(), clip.plural as string, clip);
		}
	});

	test('S7 Kompositum: der Kopf findet die Datei über die Präfix-Klausel @phase4', async ({}, testInfo) => {
		only(testInfo, [ONCE]);
		for (const clip of s7Expectations()) {
			// The head itself is not a word of the clip (fetch_speech tests), so only the prefix clause can find it.
			await expectFound(users.alice(), clip.head, clip);
			await expectFound(users.alice(), clip.compound, clip);
		}
	});

	test('S7 "12:30" liefert keinen Fehler @phase4', async ({}, testInfo) => {
		only(testInfo, [ONCE]);
		// Status 200 is checked inside search(); the group may be empty.
		expect(Array.isArray(await search(users.alice(), '12:30'))).toBe(true);
	});

	test('S7 Suche im Dialog mit dem Zahlwort zur Ziffer @phase4', async ({ page }, testInfo) => {
		only(testInfo, [ONCE]);
		const clip = s7Expectations().find((item) => /^\d+$/.test(item.numberWord)) ?? s7Expectations()[0];
		const alice = users.alice();
		await withLanguage(alice, REVIEW_LANGUAGE, async () => {
			await login(page, alice);
			// The German word of the number, where Parakeet wrote the digit: the widening in the real dialog.
			const group = await searchInDialog(page, clip.numberForms[1]);
			await expect(group.locator(`a[href*="/play/${clip.fileId}"]`).first()).toBeVisible();
			await wholePage(page, 's7-number', testInfo);
		});
	});

	test('S7 Trefferliste je Suchbegriff im Dialog, als Bild für die Abnahme @phase4', async ({ page }, testInfo) => {
		only(testInfo, [ONCE]);
		const clips = s7Expectations();
		// Every term of 04-UI-SPEC S7 as the clips measured it: the four forms of
		// the number, singular and plural, head and compound; then "12:30".
		const terms = [
			...new Set(
				clips.flatMap((clip) => [
					...clip.numberForms,
					...(clip.singular === null ? [] : [clip.singular]),
					...(clip.plural === null ? [] : [clip.plural]),
					clip.head,
					clip.compound,
				]),
			),
		];
		const alice = users.alice();
		await withLanguage(alice, REVIEW_LANGUAGE, async () => {
			await login(page, alice);
			await watchProviderSearches(page);
			await openUnifiedSearch(page);
			const input = searchField(page);
			await expect(input).toBeVisible();
			for (const [index, term] of [...terms, CLOCK_TERM].entries()) {
				await input.fill(term);
				await expectFinalSearchDone(page);
				const group = page.getByRole('list', { name: GROUP_NAME }).or(page.getByRole('listbox', { name: GROUP_NAME }));
				const name = `s7-term-${String(index + 1).padStart(2, '0')}-${termSlug(term)}`;
				if (term === CLOCK_TERM) {
					// "12:30" may find nothing; the picture shows the dialog without an error.
					await wholePage(page, name, testInfo);
				} else {
					// The OCS checks above prove the file among the hits; the dialog shows the group of the term.
					await expect(group, `the dialog shows the group for "${term}"`).toBeVisible();
					await screenshotPart(group, name, testInfo);
				}
				console.log(`S7-TERM ${name} "${term}" hits in the dialog: ${await group.locator('a[href*="/play/"]').count()}`);
			}
		});
	});

	test('S6 Datumsfilter: die Gruppe steht im Hauptteil, nicht unter Partial matches @phase4', async ({ page }, testInfo) => {
		only(testInfo, S6_PROJECTS);
		const clip = s7Expectations()[s7Expectations().length - 1];
		const alice = users.alice();
		await withLanguage(alice, REVIEW_LANGUAGE, async () => {
			await login(page, alice);
			await searchInDialog(page, clip.numberForms[1]);
			await filtered(page, 'since', async () => {
				await page.locator('[data-cy-unified-search-filter="date"]').getByRole('button').first().click();
				await page.getByRole('menuitem', { name: CORE_TEXTS.thisYear[REVIEW_LANGUAGE] }).click();
			});
			await expectInMainPart(page, clip.fileId);
			await wholePage(page, 's6-date', testInfo);
		});
	});

	test('S6 Personenfilter: die Gruppe steht im Hauptteil, nicht unter Partial matches @phase4', async ({ page }, testInfo) => {
		only(testInfo, S6_PROJECTS);
		// s7-ziffer.wav is the clip alice shared with carol (ci/seed.sh), so the share rows tie it to her.
		const clip = s7Expectations().find((item) => item.key === 'S7_DE_DIGIT');
		expect(clip, 'AVS_S7_TARGETS holds S7_DE_DIGIT').toBeDefined();
		const shared = clip as S7Clip;
		const alice = users.alice();
		await withLanguage(alice, REVIEW_LANGUAGE, async () => {
			await login(page, alice);
			await searchInDialog(page, shared.numberForms[1]);
			await filtered(page, 'person', async () => {
				await page.locator('[data-cy-unified-search-filter="people"]').getByRole('button').first().click();
				await page.getByRole('textbox', { name: CORE_TEXTS.searchPeople[REVIEW_LANGUAGE] }).fill(PERSON);
				await page.locator('.searchable-list__list li', { hasText: PERSON }).getByRole('button').first().click();
			});
			await expectInMainPart(page, shared.fileId);
			await wholePage(page, 's6-person', testInfo);
		});
	});

	test('SRCH-04 Empfänger einer Freigabe mit Download-Sperre findet Treffer @phase4', async ({}, testInfo) => {
		only(testInfo, [ONCE]);
		const clip = s7Expectations().find((item) => item.key === 'S7_DE');
		expect(clip, 'AVS_S7_TARGETS holds S7_DE').toBeDefined();
		const locked = clip as S7Clip;
		const recipient = users.dora();
		// Positive control of the lock: the recipient cannot fetch the file over WebDAV.
		const api = await request.newContext({
			baseURL: BASE_URL,
			httpCredentials: { username: recipient.name, password: recipient.password, send: 'always' },
		});
		try {
			const response = await api.get(`/remote.php/dav/files/${recipient.name}/s7-zahlwort.wav`);
			expect(response.status(), 'the share of s7-zahlwort.wav carries the download lock').toBe(403);
		} finally {
			await api.dispose();
		}
		for (const term of [locked.numberWord, locked.head]) {
			await expectFound(recipient, term, locked);
		}
	});
});
