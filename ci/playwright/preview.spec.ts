// The core path of phase 3 as an end-to-end contract (plan 03-02): a spoken
// clip that alice uploads is found through the Unified Search within minutes,
// marked as preliminary, the hit jumps to the time of the word, and a user
// without access finds nothing.
//
// The clip comes from ci/media/fetch_speech.py (FLEURS, Google, CC-BY-4.0):
// CI sets AVS_SPEECH_DE to the path of speech_de.wav and AVS_SPEECH_WORD to
// its EXPECTED_WORD. The path fails today on purpose (there are no real hits
// yet); CI switches it on with AVS_PREVIEW_E2E=1 from plan 03-18 on.
//
// No fixed waits: only web-first assertions and expect.poll.
import { readFileSync } from 'node:fs';
import { expect, request, test, type APIRequestContext } from '@playwright/test';
import { expectMediaSettled, login, position, users, type User } from './helpers';

test.skip(process.env.AVS_PREVIEW_E2E !== '1', 'phase 3 core path runs from plan 03-18 on');

const BASE_URL = process.env.NC_URL ?? 'http://localhost:8080';
const FOLDER = 'phase3';
const FILE_NAME = 'speech_de.wav';
// The preview mark of the subline (UI-SPEC T1) in the three languages.
const PRELIMINARY_SUBLINE = /^\d+:\d{2} · (Vorläufig|Preliminary|Provisoire) · /;
// The preview note under the excerpt (UI-SPEC T2) in the three languages.
const PREVIEW_NOTE =
	/^(Vorläufiges Transkript\. Es kann Fehler enthalten\.|Preliminary transcript\. It may contain errors\.|Transcription provisoire\. Elle peut contenir des erreurs\.)$/;
// The jump lands at most 0.2 s before and 0.05 s after the time of the link.
const BEFORE_SECONDS = 0.2;
const AFTER_SECONDS = 0.05;
const FOUND_WITHIN_MS = 15 * 60_000;
const POLL_EVERY_MS = 10_000;

type Entry = { subline: string; resourceUrl: string; attributes: Record<string, string> };

function required(name: string): string {
	const value = process.env[name];
	if (value === undefined || value === '') {
		throw new Error(`${name} is not set; CI sets it from ci/media/fetch_speech.py`);
	}
	return value;
}

function escapeRegExp(text: string): string {
	return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function apiAs(user: User): Promise<APIRequestContext> {
	return request.newContext({
		baseURL: BASE_URL,
		httpCredentials: { username: user.name, password: user.password, send: 'always' },
	});
}

/** The entries of this provider for one term, as one user, through OCS. */
async function searchAs(user: User, term: string): Promise<Entry[]> {
	const api = await apiAs(user);
	try {
		const response = await api.get(
			`/ocs/v2.php/search/providers/audio_video_search/search?term=${encodeURIComponent(term)}&limit=5`,
			{ headers: { 'OCS-APIRequest': 'true', Accept: 'application/json' } },
		);
		expect(response.status()).toBe(200);
		const body = await response.json();
		return body.ocs.data.entries;
	} finally {
		await api.dispose();
	}
}

/** Upload the clip to alice's folder phase3 by WebDAV and answer its file id. */
async function upload(user: User, clipPath: string): Promise<string> {
	const api = await apiAs(user);
	try {
		const folder = `/remote.php/dav/files/${user.name}/${FOLDER}`;
		const made = await api.fetch(folder, { method: 'MKCOL' });
		// 201 created, 405 when the folder is already there from an earlier run.
		expect([201, 405]).toContain(made.status());
		const put = await api.put(`${folder}/${FILE_NAME}`, {
			data: readFileSync(required('AVS_SPEECH_DE')),
			headers: { 'Content-Type': 'audio/wav' },
		});
		expect([201, 204]).toContain(put.status());
		const found = await api.fetch(`${folder}/${FILE_NAME}`, {
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

function hitOf(entries: Entry[], fileId: string): Entry | undefined {
	return entries.find((entry) => String(entry.attributes?.fileId) === fileId);
}

test.describe.serial('phase 3 core path @preview', () => {
	let fileId = '';
	let hit: Entry | undefined;

	test.beforeEach(({}, testInfo) => {
		// One upload per run: the path changes the instance, the grid would repeat it six times.
		test.skip(testInfo.project.name !== 'w1280-light', 'the core path runs in one project');
	});

	test('upload is found as preliminary within minutes @preview', async () => {
		test.setTimeout(FOUND_WITHIN_MS + 2 * 60_000);
		const word = required('AVS_SPEECH_WORD');
		fileId = await upload(users.alice(), required('AVS_SPEECH_DE'));

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

		await expect(page.locator('blockquote.avs-excerpt__text')).toContainText(
			new RegExp(escapeRegExp(word), 'i'),
		);
		await expect(page.locator('p.avs-excerpt__note')).toHaveText(PREVIEW_NOTE);

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
		expect(entries.map((entry) => String(entry.attributes?.fileId))).not.toContain(fileId);
	});
});
