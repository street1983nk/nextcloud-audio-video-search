// End-to-end tests against a throwaway Nextcloud test instance in CI.
// The instance, its passwords and the test media exist only inside the CI run
// (NC_URL, the *_PASS variables and the FILEID_* values of ci/fileids.env as
// job variables, never repository secrets). ci/seed.sh creates all of them.
//
// The projects are the screenshot grid of the owner's review (UI-SPEC): three
// widths in light and dark, plus high contrast at 1280 px. The high contrast
// project logs in as the review user dora, whose theme ci/seed.sh switched to
// light-highcontrast, and runs only the tests tagged @screenshot.
//
// German and French get two projects each, again @screenshot only, with the
// review users elke (de_DE) and fleur (fr_FR): 375 px light, where longer
// words and the non-breaking spaces of French decide the wrapping, and
// 1280 px dark for the wide layout. Colour pairs do not depend on the
// language, the English grid covers them at every width; four projects keep
// the extra CI time at a fraction of a full second grid. The language is in
// the project name and so in every file name (play-de-w375-light.png).
//
// One worker: several tests switch state of the one instance (the test result
// switch in the admin section), so nothing may run beside them.
import { defineConfig, devices } from '@playwright/test';

const WIDTHS = [375, 768, 1280] as const;
const SCHEMES = ['light', 'dark'] as const;

const grid = WIDTHS.flatMap((width) =>
	SCHEMES.map((colorScheme) => ({
		name: `w${width}-${colorScheme}`,
		use: {
			...devices['Desktop Chrome'],
			viewport: { width, height: 900 },
			colorScheme,
		},
		metadata: { highContrast: false },
	})),
);

const LANGUAGE_SHOTS = [
	{ width: 375, colorScheme: 'light' },
	{ width: 1280, colorScheme: 'dark' },
] as const;

const languages = (['de', 'fr'] as const).flatMap((language) =>
	LANGUAGE_SHOTS.map(({ width, colorScheme }) => ({
		name: `${language}-w${width}-${colorScheme}`,
		grep: /@screenshot/,
		use: {
			...devices['Desktop Chrome'],
			viewport: { width, height: 900 },
			colorScheme,
		},
		metadata: { highContrast: false, language },
	})),
);

export default defineConfig({
	testDir: '.',
	testMatch: '*.spec.ts',
	outputDir: 'test-results',
	retries: 0,
	workers: 1,
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	reporter: [['list'], ['html', { open: 'never' }]],
	use: {
		baseURL: process.env.NC_URL ?? 'http://localhost:8080',
		screenshot: 'only-on-failure',
		trace: 'retain-on-failure',
	},
	projects: [
		...grid,
		{
			name: 'hc-1280',
			grep: /@screenshot/,
			use: {
				...devices['Desktop Chrome'],
				viewport: { width: 1280, height: 900 },
				colorScheme: 'light',
			},
			metadata: { highContrast: true },
		},
		...languages,
	],
});
