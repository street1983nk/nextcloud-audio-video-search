// End-to-end tests against a throwaway Nextcloud test instance in CI.
// The instance, its admin password and the test media exist only inside the CI
// run (NC_URL, NC_USER, NC_PASSWORD as job variables, never repository secrets).
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
	testDir: '.',
	testMatch: '*.spec.ts',
	outputDir: 'test-results',
	retries: 0,
	forbidOnly: !!process.env.CI,
	reporter: [['list'], ['html', { open: 'never' }]],
	use: {
		baseURL: process.env.NC_URL ?? 'http://localhost:8080',
		screenshot: 'only-on-failure',
		trace: 'retain-on-failure',
	},
	projects: [
		{
			name: 'chromium-light',
			use: { ...devices['Desktop Chrome'], colorScheme: 'light' },
		},
		{
			name: 'chromium-dark',
			use: { ...devices['Desktop Chrome'], colorScheme: 'dark' },
		},
	],
});
