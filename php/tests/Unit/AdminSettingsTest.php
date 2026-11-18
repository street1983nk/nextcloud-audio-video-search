<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ResourceFormat;
use OCA\AudioVideoSearch\Settings\Admin;
use OCP\AppFramework\Services\IInitialState;
use OCP\IAppConfig;
use OCP\IConfig;
use OCP\IDateTimeFormatter;
use OCP\IL10N;
use OCP\IUser;
use OCP\IUserSession;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The admin page with profile, computing time and models (plan 05-09,
 * 05-UI-SPEC surface 3): what getForm() hands to the page and what the
 * template renders of it, read out of the markup.
 *
 * The assertions look at ids, attributes and numbers, not at sentences: the
 * template translates with the language of the server under test, the
 * numbers come from the IL10N handed to Admin (a point as decimal sign).
 */
#[CoversClass(Admin::class)]
final class AdminSettingsTest extends TestCase {
	/** @var array<string, mixed> what was handed to the initial state */
	private array $provided = [];

	/** @var list<string> every log line with its context as one text */
	private array $logged = [];

	protected function setUp(): void {
		parent::setUp();

		$this->provided = [];
		$this->logged = [];
	}

	/** @return array<string, mixed> the contract shape of GET /resources: R1, quality locked */
	private static function resourcesAnswer(): array {
		return [
			'availableBytes' => 3328599654,
			'minimumBytes' => 2362232012,
			'proposed' => 'balanced',
			'chosen' => null,
			'effective' => 'balanced',
			'profiles' => [
				['id' => 'fast', 'locked' => false, 'needBytes' => 2362232012],
				['id' => 'balanced', 'locked' => false, 'needBytes' => 3221225472],
				['id' => 'quality', 'locked' => true, 'needBytes' => 5368709120],
			],
			'threads' => ['cpus' => 8, 'standard' => 4, 'admin' => null, 'effective' => 4],
			'window' => ['start' => null, 'end' => null, 'zone' => null, 'openNow' => true, 'changeAt' => null],
			'models' => [
				['id' => 'parakeet', 'state' => 'in_image', 'doneBytes' => 0, 'totalBytes' => 670000000, 'needFreeBytes' => null],
				['id' => 'silero', 'state' => 'in_image', 'doneBytes' => 0, 'totalBytes' => 640000, 'needFreeBytes' => null],
				['id' => 'whisper-turbo', 'state' => 'waiting', 'doneBytes' => 0, 'totalBytes' => 1621665983, 'needFreeBytes' => null],
				['id' => 'whisper-large-v3', 'state' => 'not_needed', 'doneBytes' => 0, 'totalBytes' => 3090835702, 'needFreeBytes' => null],
			],
			'offline' => ['value' => false, 'forcedByEnv' => false],
		];
	}

	private function l10n(): IL10N {
		$l = $this->createMock(IL10N::class);
		$l->method('getLanguageCode')->willReturn('en');
		$l->method('t')->willReturnCallback(
			static fn (string $text, array|string $parameters = []): string => vsprintf($text, (array)$parameters),
		);

		return $l;
	}

	/**
	 * The form with a container that answers $resources (null: silent), or
	 * that throws $failure.
	 *
	 * @param array<string, mixed>|null $resources
	 */
	private function admin(?array $resources, ?\Throwable $failure = null): Admin {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('backendState')->willReturn([
			'state' => ExAppService::STATE_OK,
			'own' => '0.1.0',
			'backend' => '0.1.0',
			'companion' => 'ok',
			'sampleCount' => 0,
			'checkedAt' => 1_800_000_000,
		]);
		// Once per page view, never a second time for the template.
		$asked = $exApp->expects(self::once())->method('resources');
		if ($failure !== null) {
			$asked->willThrowException($failure);
		} else {
			$asked->willReturn($resources);
		}

		$config = $this->createMock(IConfig::class);
		$config->method('getSystemValueBool')->willReturn(false);
		$config->method('getUserValue')->willReturn('Europe/Berlin');
		$config->method('getSystemValueString')->willReturnCallback(
			static fn (string $key, string $default = ''): string => $default,
		);

		$initialState = $this->createMock(IInitialState::class);
		$initialState->method('provideInitialState')->willReturnCallback(
			function (string $key, mixed $data): void {
				$this->provided[$key] = $data;
			},
		);

		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn('root');
		$session = $this->createMock(IUserSession::class);
		$session->method('getUser')->willReturn($user);

		$formatter = $this->createMock(IDateTimeFormatter::class);
		$formatter->method('formatTime')->willReturn('12:00:00');

		$logger = $this->createMock(LoggerInterface::class);
		$logger->method('error')->willReturnCallback(
			function (string|\Stringable $message, array $context = []): void {
				$this->logged[] = $message . ' ' . json_encode($context, JSON_THROW_ON_ERROR);
			},
		);

		return new Admin(
			$exApp,
			$this->createMock(IAppConfig::class),
			$config,
			$initialState,
			$session,
			$formatter,
			$logger,
			$this->l10n(),
		);
	}

	/**
	 * The page as the template renders it (getForm() answers without the layout).
	 *
	 * @param array<string, mixed>|null $resources
	 */
	private function page(?array $resources, ?\Throwable $failure = null): string {
		return $this->admin($resources, $failure)->getForm()->render();
	}

	/** The opening tag of the radio of one profile. */
	private static function profileRadio(string $html, string $id): string {
		self::assertSame(1, preg_match('#<input type="radio" class="radio" id="avs-profile-' . $id . '"[^>]*>#', $html, $match), 'no radio for ' . $id);

		return $match[0];
	}

	/** The element with this id, from its opening tag to the end of its line. */
	private static function line(string $html, string $id): string {
		self::assertSame(1, preg_match('#<[a-z0-9]+ (?:[^>\n]* )?id="' . preg_quote($id, '#') . '"[^\n]*#', $html, $match), 'no element ' . $id);

		return $match[0];
	}

	/** True when the opening tag of the element with this id carries hidden. */
	private static function isHidden(string $html, string $id): bool {
		self::assertSame(1, preg_match('#<[a-z0-9]+ (?:[^>]* )?id="' . preg_quote($id, '#') . '"[^>]*>#', $html, $match), 'no element ' . $id);

		return preg_match('#\shidden>$#', $match[0]) === 1;
	}

	/**
	 * The texts of the number spans in a piece of markup, in their order.
	 *
	 * @return list<string>
	 */
	private static function numbers(string $markup): array {
		preg_match_all('#<span class="avs-res__number" data-value="[a-z0-9-]+">([^<]*)</span>#', $markup, $found);

		return $found[1];
	}

	// -- the contract handed to the page -------------------------------------------

	public function testThePageGetsTheAnswerOfTheContainerWithTheZonesOfTheRoutes(): void {
		$response = $this->admin(self::resourcesAnswer())->getForm();

		$expected = self::resourcesAnswer() + [
			'zones' => \DateTimeZone::listIdentifiers(),
			'defaultZone' => 'Europe/Berlin',
		];
		self::assertSame($expected, $this->provided['resources']);
		self::assertSame($expected, $response->getParams()['resources']);
		// The same shape the route GET admin/resources answers.
		self::assertSame(
			ExAppService::withZones(self::resourcesAnswer(), $this->configWithZone('Europe/Berlin'), 'root'),
			$this->provided['resources'],
		);
	}

	private function configWithZone(string $zone): IConfig {
		$config = $this->createMock(IConfig::class);
		$config->method('getUserValue')->willReturn($zone);
		$config->method('getSystemValueString')->willReturn('UTC');

		return $config;
	}

	public function testTheZoneOfTheWindowFallsBackFromTheAccountToTheSystemToUtc(): void {
		$config = $this->createMock(IConfig::class);
		$config->method('getUserValue')->willReturn('Mars/Base');
		$config->method('getSystemValueString')->willReturn('Europe/Paris');
		self::assertSame('Europe/Paris', ExAppService::defaultZone($config, 'root'));

		$nowhere = $this->createMock(IConfig::class);
		$nowhere->method('getUserValue')->willReturn('');
		$nowhere->method('getSystemValueString')->willReturn('Nowhere/Land');
		self::assertSame('UTC', ExAppService::defaultZone($nowhere, 'root'));
	}

	public function testEveryAmountIsFormattedByItsMeaning(): void {
		$text = $this->admin(self::resourcesAnswer())->getForm()->getParams()['resourceText'];

		// Available rounded down, a need rounded up, sizes half up.
		self::assertSame('3.3 GB', $text['available']);
		self::assertSame('2.4 GB', $text['minimum']);
		self::assertSame(['fast' => '2.4 GB', 'balanced' => '3.3 GB', 'quality' => '5.4 GB'], $text['need']);
		self::assertSame(['size' => '1.6 GB', 'done' => '0.0 GB', 'free' => 'unknown'], $text['models']['whisper-turbo']);
		self::assertSame('3.1 GB', $text['models']['whisper-large-v3']['size']);
		self::assertSame('%s GB', $text['unit']);
		self::assertSame('.', $text['decimal']);
	}

	// -- R9: the backend does not answer ---------------------------------------------

	public function testASilentBackendRendersOneWarningNoComputeSectionAndStillTheLicences(): void {
		$html = $this->page(null);

		self::assertNull($this->provided['resources']);
		self::assertSame(1, substr_count($html, 'id="avs-resources-unavailable"'));
		self::assertSame(1, substr_count($html, 'id="avs-profile"'));
		self::assertSame(1, substr_count($html, 'id="avs-models"'));
		self::assertStringNotContainsString('id="avs-compute"', $html);
		self::assertStringNotContainsString('id="avs-profile-options"', $html);
		self::assertStringNotContainsString('name="avs-profile"', $html);
		// No state, no size, no offline switch, but origin and licences.
		self::assertStringNotContainsString('avs-models__state', $html);
		self::assertStringNotContainsString('data-value="size-', $html);
		self::assertStringNotContainsString('id="avs-offline"', $html);
		foreach (['Parakeet TDT 0.6B v3', 'Silero VAD', 'Whisper large-v3-turbo', 'Whisper large-v3'] as $model) {
			self::assertStringContainsString($model, $html);
		}
		self::assertStringContainsString('href="https://creativecommons.org/licenses/by/4.0/" rel="noreferrer noopener">CC-BY-4.0</a>', $html);
		self::assertStringContainsString('href="https://github.com/street1983nk/nextcloud-audio-video-search/blob/main/THIRD-PARTY.md"', $html);
	}

	public function testAThrowingBackendReadsLikeASilentOneAndLogsOnlyTheClass(): void {
		$html = $this->page(null, new \RuntimeException('/var/www/data/alice'));

		self::assertNull($this->provided['resources']);
		self::assertSame(1, substr_count($html, 'id="avs-resources-unavailable"'));
		self::assertStringNotContainsString('id="avs-compute"', $html);
		self::assertCount(1, $this->logged);
		self::assertStringContainsString('RuntimeException', $this->logged[0]);
		self::assertStringNotContainsString('alice', $this->logged[0]);
	}

	// -- R1: normal, one profile locked ----------------------------------------------

	public function testTheThreeSectionsFollowTheConnectionInTheirOrder(): void {
		$html = $this->page(self::resourcesAnswer());

		$order = array_map(
			static fn (string $id): int|false => strpos($html, 'id="' . $id . '"'),
			['avs-admin', 'avs-profile', 'avs-compute', 'avs-models'],
		);
		self::assertNotContains(false, $order);
		$sorted = $order;
		sort($sorted);
		self::assertSame($sorted, $order);
		self::assertStringNotContainsString('id="avs-resources-unavailable"', $html);
	}

	public function testALockedProfileIsDisabledAndItsReasonShowsTwoDifferentNumbers(): void {
		$html = $this->page(self::resourcesAnswer());

		self::assertStringNotContainsString(' disabled', self::profileRadio($html, 'fast'));
		self::assertStringNotContainsString(' disabled', self::profileRadio($html, 'balanced'));
		$quality = self::profileRadio($html, 'quality');
		self::assertStringContainsString(' disabled', $quality);
		// The reason is tied to the radio, so a screen reader reads it.
		self::assertStringContainsString('aria-describedby="avs-profile-quality-desc avs-profile-quality-lock"', $quality);
		self::assertStringContainsString('aria-describedby="avs-profile-fast-desc avs-profile-fast-need"', self::profileRadio($html, 'fast'));

		self::assertFalse(self::isHidden($html, 'avs-profile-quality-lock'));
		self::assertTrue(self::isHidden($html, 'avs-profile-quality-need'));
		self::assertTrue(self::isHidden($html, 'avs-profile-fast-lock'));
		self::assertFalse(self::isHidden($html, 'avs-profile-fast-need'));
		self::assertSame(['5.4 GB', '3.3 GB'], self::numbers(self::line($html, 'avs-profile-quality-lock')));
	}

	public function testALockNeverShowsTheSameNumberTwice(): void {
		// The need is one byte above what is available.
		$answer = self::resourcesAnswer();
		$answer['availableBytes'] = 3000000000;
		$answer['profiles'][2]['needBytes'] = 3000000001;

		$numbers = self::numbers(self::line($this->page($answer), 'avs-profile-quality-lock'));

		self::assertSame(['3.1 GB', '3.0 GB'], $numbers);
		self::assertNotSame($numbers[0], $numbers[1]);
	}

	public function testWithoutAStoredChoiceTheProfileInUseIsCheckedAndTheProposalIsMarkedOnce(): void {
		$html = $this->page(self::resourcesAnswer());

		self::assertStringContainsString(' checked', self::profileRadio($html, 'balanced'));
		self::assertStringNotContainsString(' checked', self::profileRadio($html, 'fast'));
		self::assertStringNotContainsString(' checked', self::profileRadio($html, 'quality'));
		self::assertSame(1, preg_match_all('#data-badge="[a-z]+">#', $html));
		self::assertSame(1, substr_count($html, 'data-badge="balanced">'));
		self::assertTrue(self::isHidden($html, 'avs-profile-low'));
		self::assertTrue(self::isHidden($html, 'avs-profile-fallback'));
		self::assertFalse(self::isHidden($html, 'avs-profile-intro'));
	}

	// -- R2: below the minimum memory ------------------------------------------------

	public function testBelowTheMinimumEveryRadioIsDisabledAndTheStoredChoiceStaysChecked(): void {
		$answer = self::resourcesAnswer();
		$answer['availableBytes'] = 2000000000;
		$answer['proposed'] = 'none';
		$answer['effective'] = 'none';
		$answer['chosen'] = 'fast';
		foreach ([0, 1, 2] as $index) {
			$answer['profiles'][$index]['locked'] = true;
		}

		$html = $this->page($answer);

		foreach (['fast', 'balanced', 'quality'] as $id) {
			self::assertStringContainsString(' disabled', self::profileRadio($html, $id), $id);
			self::assertFalse(self::isHidden($html, 'avs-profile-' . $id . '-lock'), $id);
			self::assertTrue(self::isHidden($html, 'avs-profile-' . $id . '-need'), $id);
		}
		self::assertStringContainsString(' checked', self::profileRadio($html, 'fast'));
		self::assertStringNotContainsString(' checked', self::profileRadio($html, 'balanced'));
		// The error banner with both numbers, no proposal, the minimum stays.
		self::assertFalse(self::isHidden($html, 'avs-profile-low'));
		self::assertStringContainsString('role="alert"', self::line($html, 'avs-profile-low'));
		self::assertTrue(self::isHidden($html, 'avs-profile-intro'));
		self::assertFalse(self::isHidden($html, 'avs-profile-minimum'));
		self::assertSame(0, preg_match_all('#data-badge="[a-z]+">#', $html));
		self::assertStringNotContainsString('aria-describedby="avs-profile-intro"', $html);
	}

	public function testAProfileTheContainerLeftFreeIsStillLockedBelowTheMinimum(): void {
		// The lock of R2 does not depend on the container marking each profile.
		$answer = self::resourcesAnswer();
		$answer['availableBytes'] = 2000000000;

		$html = $this->page($answer);

		foreach (['fast', 'balanced', 'quality'] as $id) {
			self::assertStringContainsString(' disabled', self::profileRadio($html, $id), $id);
		}
		self::assertFalse(self::isHidden($html, 'avs-profile-low'));
	}

	public function testAnUnknownAmountLocksEveryProfileAndReadsUnknown(): void {
		$answer = self::resourcesAnswer();
		$answer['availableBytes'] = null;

		$html = $this->page($answer);

		foreach (['fast', 'balanced', 'quality'] as $id) {
			self::assertStringContainsString(' disabled', self::profileRadio($html, $id), $id);
		}
		self::assertFalse(self::isHidden($html, 'avs-profile-low'));
		self::assertTrue(self::isHidden($html, 'avs-profile-intro'));
		self::assertSame(0, preg_match_all('#data-badge="[a-z]+">#', $html));
		self::assertSame(['2.4 GB', 'unknown'], self::numbers(self::line($html, 'avs-profile-fast-lock')));
	}

	// -- R3: the stored choice no longer fits ------------------------------------------

	public function testAChoiceThatNoLongerFitsStaysCheckedAndDisabledUnderTheFallbackBanner(): void {
		$answer = self::resourcesAnswer();
		$answer['chosen'] = 'quality';

		$html = $this->page($answer);

		$quality = self::profileRadio($html, 'quality');
		self::assertStringContainsString(' checked', $quality);
		self::assertStringContainsString(' disabled', $quality);
		self::assertStringNotContainsString(' checked', self::profileRadio($html, 'balanced'));
		self::assertFalse(self::isHidden($html, 'avs-profile-fallback'));
		self::assertTrue(self::isHidden($html, 'avs-profile-low'));
		// Need of the choice, then what is available.
		self::assertSame(1, preg_match('#<div id="avs-profile-fallback".*?</div>\s*</div>#s', $html, $banner));
		self::assertSame(['5.4 GB', '3.3 GB'], self::numbers($banner[0]));
		self::assertSame(1, substr_count($banner[0], 'data-value="chosen-name"'));
		self::assertSame(1, substr_count($banner[0], 'data-value="effective-name"'));
	}

	// -- computing time ----------------------------------------------------------------

	public function testWithoutAWindowAlwaysIsCheckedAndTheFieldsAreHidden(): void {
		$html = $this->page(self::resourcesAnswer());

		self::assertStringContainsString('id="avs-threads" min="1" max="4" step="1" inputmode="numeric" value="4"', $html);
		self::assertStringContainsString('id="avs-window-always" name="avs-window" value="always" checked>', $html);
		self::assertStringContainsString('id="avs-window-set" name="avs-window" value="window">', $html);
		self::assertTrue(self::isHidden($html, 'avs-window-fields'));
		self::assertTrue(self::isHidden($html, 'avs-window-state'));
		// The zone of the admin is the one the field starts with.
		self::assertSame(1, preg_match_all('#<option value="[^"]+" selected>#', $html));
		self::assertStringContainsString('<option value="Europe/Berlin" selected>', $html);
		// The button is shown by admin.js only.
		self::assertTrue(self::isHidden($html, 'avs-compute-save'));
	}

	public function testAStoredWindowAndALoweredThreadCountAreShown(): void {
		$answer = self::resourcesAnswer();
		$answer['threads'] = ['cpus' => 8, 'standard' => 4, 'admin' => 2, 'effective' => 2];
		$answer['window'] = ['start' => '22:00', 'end' => '06:00', 'zone' => 'Europe/Paris', 'openNow' => false, 'changeAt' => '22:00'];

		$html = $this->page($answer);

		self::assertStringContainsString('max="4" step="1" inputmode="numeric" value="2"', $html);
		self::assertStringContainsString('id="avs-window-set" name="avs-window" value="window" checked>', $html);
		self::assertFalse(self::isHidden($html, 'avs-window-fields'));
		self::assertStringContainsString('id="avs-window-start" step="60" value="22:00"', $html);
		self::assertStringContainsString('id="avs-window-end" step="60" value="06:00"', $html);
		self::assertStringContainsString('<option value="Europe/Paris" selected>', $html);
		$state = self::line($html, 'avs-window-state');
		self::assertFalse(self::isHidden($html, 'avs-window-state'));
		self::assertStringContainsString('<span data-window="open" hidden>', $state);
		self::assertStringContainsString('<span data-window="closed">', $state);
		self::assertSame(['22:00', '22:00'], self::numbers($state));
	}

	// -- models and licences -----------------------------------------------------------

	public function testEachModelShowsExactlyOneStateAndTheBarOnlyWhileDownloading(): void {
		$answer = self::resourcesAnswer();
		$answer['models'][2] = ['id' => 'whisper-turbo', 'state' => 'downloading', 'doneBytes' => 500000000, 'totalBytes' => 1621665983, 'needFreeBytes' => null];

		$html = $this->page($answer);

		// Eleven states per model, one of them visible.
		self::assertSame(44, preg_match_all('#<p class="avs-models__line[^"]*" data-state="[a-z_]+"#', $html));
		self::assertSame(4, preg_match_all('#<p class="avs-models__line[^"]*" data-state="[a-z_]+">#', $html));
		self::assertSame(2, preg_match_all('#data-state="in_image">#', $html));
		self::assertSame(1, preg_match_all('#data-state="downloading">#', $html));
		self::assertSame(1, preg_match_all('#data-state="not_needed">#', $html));
		// One bar per model, only the one of the download visible, with its numbers.
		self::assertSame(4, substr_count($html, '<progress '));
		self::assertSame(3, preg_match_all('#<progress [^>]* hidden>#', $html));
		self::assertStringContainsString('<progress class="avs-models__progress" max="1621665983" value="500000000" aria-labelledby="avs-model-whisper-turbo-name" aria-describedby="avs-model-whisper-turbo-text">', $html);
		self::assertSame(1, preg_match('#<span id="avs-model-whisper-turbo-text">.*?</span></p>#s', $html, $text));
		self::assertSame(['0.5 GB', '1.6 GB'], self::numbers($text[0]));
	}

	public function testOfflineSetByTheDeployOptionIsCheckedAndNotOperable(): void {
		$free = $this->page(self::resourcesAnswer());
		self::assertStringContainsString('id="avs-offline" class="checkbox" aria-describedby="avs-offline-hint">', $free);
		self::assertTrue(self::isHidden($free, 'avs-offline-forced'));

		$answer = self::resourcesAnswer();
		$answer['offline'] = ['value' => false, 'forcedByEnv' => true];
		$forced = $this->page($answer);

		self::assertStringContainsString('id="avs-offline" class="checkbox" aria-describedby="avs-offline-hint avs-offline-forced" checked disabled>', $forced);
		self::assertFalse(self::isHidden($forced, 'avs-offline-forced'));
	}

	public function testThePageCarriesNoPathAndOnlyTheFixedAddresses(): void {
		$html = $this->page(self::resourcesAnswer());

		foreach (['/models/', 'APP_PERSISTENT_STORAGE', '/nc_app_', 'huggingface', 'hf.co'] as $needle) {
			self::assertStringNotContainsString($needle, $html, $needle);
		}
		preg_match_all('#https?://[^"<\s]+#', $html, $found);
		$allowed = [
			'https://creativecommons.org/licenses/by/4.0/',
			'https://opensource.org/license/mit',
			'https://www.apache.org/licenses/LICENSE-2.0',
			'https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html',
			'https://www.gnu.org/licenses/old-licenses/gpl-2.0.html',
			'https://github.com/street1983nk/nextcloud-audio-video-search#offline',
			'https://github.com/street1983nk/nextcloud-audio-video-search/blob/main/THIRD-PARTY.md',
		];
		self::assertSame([], array_values(array_diff(array_unique($found[0]), $allowed)));
		// The occ command: in the state "wrong checksum, placed" of each model and in the offline hint.
		self::assertSame(5, substr_count($html, '<code class="avs-admin__command">occ audio_video_search:models --verify</code>'));
	}

	// -- the rounding rule, on the numbers admin.js is held to ---------------------------

	/**
	 * The same rows backend/tests/test_admin_phase5_assets.py runs through the
	 * rule of admin.js (it reads this list): on the boundary, just below, just
	 * above and zero, for each meaning.
	 *
	 * @return list<array{int, string, string}>
	 */
	public static function gigabyteRows(): array {
		return [
			[0, 'need', '0.0 GB'],
			[1, 'need', '0.1 GB'],
			[2999999999, 'need', '3.0 GB'],
			[3000000000, 'need', '3.0 GB'],
			[3000000001, 'need', '3.1 GB'],
			[0, 'available', '0.0 GB'],
			[2999999999, 'available', '2.9 GB'],
			[3000000000, 'available', '3.0 GB'],
			[3000000001, 'available', '3.0 GB'],
			[0, 'size', '0.0 GB'],
			[3049999999, 'size', '3.0 GB'],
			[3050000000, 'size', '3.1 GB'],
			[3050000001, 'size', '3.1 GB'],
			[1617884929, 'size', '1.6 GB'],
			[3087284237, 'size', '3.1 GB'],
		];
	}

	#[DataProvider('gigabyteRows')]
	public function testTheRoundingRuleOnTheSharedRows(int $bytes, string $mode, string $expected): void {
		self::assertSame($expected, ResourceFormat::gigabytes($bytes, $mode, $this->l10n()));
	}
}
