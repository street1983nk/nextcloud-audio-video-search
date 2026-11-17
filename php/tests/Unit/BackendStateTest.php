<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCP\App\IAppManager;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\Http\Client\IResponse;
use OCP\IAppConfig;
use OCP\IGroup;
use OCP\IGroupManager;
use OCP\IUser;
use OCP\IUserManager;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The state of the other half as the admin page shows it and the search obeys
 * it (research decision 6, pattern 1, plan 07).
 *
 * Two seams are doubled and nothing else: exAppInfo, which reads the
 * registration out of AppAPI, and proxyRequest, which carries GET /status.
 * Both belong to an app that is absent from the autoload space of this suite.
 * The order of the checks, the version comparison, the field checks of the
 * status answer and the memory of the last verdict are the real code.
 */
#[CoversClass(ExAppService::class)]
final class BackendStateTest extends TestCase {
	private const NOW = 1_800_000_000;

	/** @var array<string, string> the stored string keys of the app */
	private array $stored = [];

	/** @var list<string> the routes the transport was asked for */
	private array $routes = [];

	private int $infoCalls = 0;
	private int $now = self::NOW;

	protected function setUp(): void {
		parent::setUp();

		$this->stored = [];
		$this->routes = [];
		$this->infoCalls = 0;
		$this->now = self::NOW;
	}

	/**
	 * The service with app_api, the registration and the status answer scripted.
	 *
	 * @param array<mixed>|false|null $info what AppAPI knows about the backend
	 * @param array<mixed>|IResponse|null $status what GET /status brings back
	 * @param list<string> $admins uids of the admin group, all enabled
	 */
	private function service(
		array|false|null $info,
		array|IResponse|null $status = null,
		bool $appApi = true,
		string $ownVersion = '0.1.0',
		array $admins = ['root'],
		?LoggerInterface $logger = null,
	): ExAppService&MockObject {
		$appConfig = $this->createMock(IAppConfig::class);
		$appConfig->method('getValueString')->willReturnCallback(
			fn (string $app, string $key, string $default = ''): string => $this->stored[$key] ?? $default,
		);
		$appConfig->method('setValueString')->willReturnCallback(
			function (string $app, string $key, string $value): bool {
				self::assertSame(Application::APP_ID, $app);
				$this->stored[$key] = $value;

				return true;
			},
		);

		$appManager = $this->createMock(IAppManager::class);
		$appManager->method('getAppVersion')->willReturn($ownVersion);
		$appManager->method('isEnabledForUser')->willReturnCallback(
			static fn (string $app): bool => $app === 'app_api' && $appApi,
		);

		$userManager = $this->createMock(IUserManager::class);
		$userManager->method('get')->willReturnCallback(
			fn (string $uid): ?IUser => $uid === 'ghost' ? null : $this->user($uid),
		);

		$group = $this->createMock(IGroup::class);
		$group->method('getUsers')->willReturn(array_map(fn (string $uid): IUser => $this->user($uid), $admins));
		$groupManager = $this->createMock(IGroupManager::class);
		$groupManager->method('get')->willReturnCallback(
			static fn (string $gid): ?IGroup => $gid === 'admin' ? $group : null,
		);

		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturnCallback(fn (): int => $this->now);

		$service = $this->getMockBuilder(ExAppService::class)
			->setConstructorArgs([
				$appManager,
				$userManager,
				$appConfig,
				$logger ?? $this->createMock(LoggerInterface::class),
				$groupManager,
				$time,
			])
			->onlyMethods(['proxyRequest', 'exAppInfo'])
			->getMock();
		$service->method('exAppInfo')->willReturnCallback(
			function () use ($info): array|false|null {
				$this->infoCalls++;

				return $info;
			},
		);
		$service->method('proxyRequest')->willReturnCallback(
			function (string $route, string $userId, string $method) use ($status): array|IResponse|null {
				$this->routes[] = $method . ' ' . $route;

				return $status;
			},
		);

		return $service;
	}

	private function user(string $uid): IUser&MockObject {
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn($uid);
		$user->method('isEnabled')->willReturn(true);

		return $user;
	}

	/** @param array<mixed> $value */
	private function statusResponse(array $value, int $code = 200): IResponse&MockObject {
		$encoded = json_encode($value);
		self::assertIsString($encoded);
		$response = $this->createMock(IResponse::class);
		$response->method('getStatusCode')->willReturn($code);
		$response->method('getBody')->willReturn($encoded);

		return $response;
	}

	/** @return array<string,mixed> */
	private static function registered(string $version, mixed $enabled = true): array {
		return ['appid' => Application::BACKEND_APP_ID, 'version' => $version, 'name' => 'Audio & Video Search Backend', 'enabled' => $enabled];
	}

	// -- the seven states, in the order of pattern 1 ----------------------------

	public function testAppApiSwitchedOffIsNoAppApiWithoutAskingAnything(): void {
		$service = $this->service(self::registered('0.1.0'), appApi: false);

		$state = $service->backendState('root');

		self::assertSame(ExAppService::STATE_NO_APP_API, $state['state']);
		self::assertSame('0.1.0', $state['own']);
		self::assertNull($state['backend']);
		self::assertSame(0, $this->infoCalls);
		self::assertSame([], $this->routes);
	}

	public function testAnUnknownUserIsNoAppApi(): void {
		$state = $this->service(self::registered('0.1.0'))->backendState('ghost');

		self::assertSame(ExAppService::STATE_NO_APP_API, $state['state']);
		self::assertSame([], $this->routes);
	}

	public function testUnresolvablePublicFunctionsAreNoAppApi(): void {
		$state = $this->service(false)->backendState('root');

		self::assertSame(ExAppService::STATE_NO_APP_API, $state['state']);
		self::assertSame([], $this->routes);
	}

	public function testAnUnregisteredBackendIsMissing(): void {
		$state = $this->service(null)->backendState('root');

		self::assertSame(ExAppService::STATE_BACKEND_MISSING, $state['state']);
		self::assertNull($state['backend']);
		self::assertSame([], $this->routes);
	}

	/** @return array<string, array{mixed}> */
	public static function disabledFlags(): array {
		return [
			'false' => [false],
			'zero from the database' => [0],
			'string zero' => ['0'],
			'missing' => [null],
		];
	}

	#[DataProvider('disabledFlags')]
	public function testADisabledBackendIsDisabledAndNamesItsVersion(mixed $enabled): void {
		$state = $this->service(self::registered('0.1.0', $enabled))->backendState('root');

		self::assertSame(ExAppService::STATE_BACKEND_DISABLED, $state['state']);
		self::assertSame('0.1.0', $state['backend']);
		self::assertSame([], $this->routes);
	}

	public function testAnotherMinorInTheRegistryIsDriftBeforeTheReachabilityCheck(): void {
		$state = $this->service(self::registered('0.2.0'), status: null)->backendState('root');

		self::assertSame(ExAppService::STATE_VERSION_DRIFT, $state['state']);
		self::assertSame('0.1.0', $state['own']);
		self::assertSame('0.2.0', $state['backend']);
		// Drift is decided out of the registration; the container is not asked.
		self::assertSame([], $this->routes);
	}

	public function testAFailingStatusCallIsUnreachable(): void {
		$state = $this->service(self::registered('0.1.0'), ['error' => 'timeout'])->backendState('root');

		self::assertSame(ExAppService::STATE_BACKEND_UNREACHABLE, $state['state']);
		self::assertSame('0.1.0', $state['backend']);
		self::assertSame(['GET /status'], $this->routes);
	}

	public function testAnErrorStatusOrNoAnswerIsUnreachable(): void {
		self::assertSame(
			ExAppService::STATE_BACKEND_UNREACHABLE,
			$this->service(self::registered('0.1.0'), $this->statusResponse([], 503))->backendState('root')['state'],
		);
		self::assertSame(
			ExAppService::STATE_BACKEND_UNREACHABLE,
			$this->service(self::registered('0.1.0'), null)->backendState('root')['state'],
		);
	}

	public function testOnlyThePatchDiffersAndTheBackendAnswersIsPatchDiffers(): void {
		$state = $this->service(
			self::registered('0.1.3'),
			$this->statusResponse(['appVersion' => '0.1.3', 'companion' => 'ok', 'sampleCount' => 0]),
		)->backendState('root');

		self::assertSame(ExAppService::STATE_VERSION_PATCH_DIFFERS, $state['state']);
		self::assertSame('0.1.0', $state['own']);
		self::assertSame('0.1.3', $state['backend']);
	}

	public function testTheSameVersionIsOkWithTheStatusFields(): void {
		$state = $this->service(
			self::registered('0.1.0'),
			$this->statusResponse(['appVersion' => '0.1.0', 'companion' => 'ok', 'sampleCount' => 2]),
		)->backendState('root');

		self::assertSame([
			'state' => ExAppService::STATE_OK,
			'own' => '0.1.0',
			'backend' => '0.1.0',
			'companion' => 'ok',
			'sampleCount' => 2,
			'checkedAt' => self::NOW,
		], $state);
	}

	public function testTheVersionTheContainerReportsWinsAndCanDrift(): void {
		// Registered as 0.1.0, but the container that answers runs 0.2.1.
		$state = $this->service(
			self::registered('0.1.0'),
			$this->statusResponse(['appVersion' => '0.2.1']),
		)->backendState('root');

		self::assertSame(ExAppService::STATE_VERSION_DRIFT, $state['state']);
		self::assertSame('0.2.1', $state['backend']);
	}

	public function testMalformedStatusFieldsAreDroppedNotTrusted(): void {
		$state = $this->service(
			self::registered('0.1.0'),
			$this->statusResponse(['appVersion' => '<b>9.9</b>', 'companion' => 'great', 'sampleCount' => -1]),
		)->backendState('root');

		self::assertSame(ExAppService::STATE_OK, $state['state']);
		self::assertSame('0.1.0', $state['backend']);
		self::assertNull($state['companion']);
		self::assertNull($state['sampleCount']);

		$state = $this->service(
			self::registered('0.1.0'),
			$this->statusResponse(['companion' => 'missing', 'sampleCount' => '3']),
		)->backendState('root');
		self::assertSame('missing', $state['companion']);
		self::assertNull($state['sampleCount']);
	}

	public function testAMalformedRegisteredVersionIsUnknownAndNeverOk(): void {
		$state = $this->service(self::registered('../etc/passwd'), $this->statusResponse([]))->backendState('root');

		self::assertSame(ExAppService::STATE_VERSION_PATCH_DIFFERS, $state['state']);
		self::assertNull($state['backend']);
	}

	public function testAThrowingRegistryLookupIsUnreachableAndLogsTheClassOnly(): void {
		$logger = $this->createMock(LoggerInterface::class);
		$logger->expects(self::once())->method('warning')->with(
			self::stringContains('registration'),
			self::callback(static fn (array $context): bool => array_keys($context) === ['class']),
		);
		$appConfig = $this->createMock(IAppConfig::class);
		$appManager = $this->createMock(IAppManager::class);
		$appManager->method('getAppVersion')->willReturn('0.1.0');
		$appManager->method('isEnabledForUser')->willReturn(true);
		$userManager = $this->createMock(IUserManager::class);
		$userManager->method('get')->willReturn($this->user('root'));

		$service = $this->getMockBuilder(ExAppService::class)
			->setConstructorArgs([
				$appManager,
				$userManager,
				$appConfig,
				$logger,
				$this->createMock(IGroupManager::class),
				$this->createMock(ITimeFactory::class),
			])
			->onlyMethods(['proxyRequest', 'exAppInfo'])
			->getMock();
		$service->method('exAppInfo')->willThrowException(new \RuntimeException('/data/secret/path'));

		self::assertSame(ExAppService::STATE_BACKEND_UNREACHABLE, $service->backendState('root')['state']);
	}

	public function testTheResultCarriesCodesVersionsAndNumbersOnly(): void {
		$state = $this->service(
			self::registered('0.1.0'),
			$this->statusResponse(['appVersion' => '0.1.0', 'path' => '/files/alice/talk.mp4', 'name' => 'talk.mp4']),
		)->backendState('root');

		self::assertSame(['state', 'own', 'backend', 'companion', 'sampleCount', 'checkedAt'], array_keys($state));
		$encoded = json_encode($state);
		self::assertIsString($encoded);
		self::assertStringNotContainsString('talk.mp4', $encoded);
		self::assertStringNotContainsString('alice', $encoded);
	}

	// -- memory and the search ----------------------------------------------------

	public function testTheVerdictIsRememberedAsJsonWithItsTime(): void {
		$this->service(self::registered('0.1.0'), ['error' => 'refused'])->backendState('root');

		$remembered = json_decode($this->stored[ExAppService::KEY_BACKEND_STATE] ?? '', true);
		self::assertIsArray($remembered);
		self::assertSame(ExAppService::STATE_BACKEND_UNREACHABLE, $remembered['state']);
		self::assertSame(self::NOW, $remembered['checkedAt']);
	}

	/** @return array<string, array{array<mixed>|false|null, array<mixed>|IResponse|null, bool}> */
	public static function errorStates(): array {
		return [
			'no_app_api' => [self::registered('0.1.0'), null, false],
			'backend_missing' => [null, null, true],
			'backend_disabled' => [self::registered('0.1.0', false), null, true],
			'version_drift' => [self::registered('0.3.0'), null, true],
			'backend_unreachable' => [self::registered('0.1.0'), ['error' => 'timeout'], true],
		];
	}

	/**
	 * @param array<mixed>|false|null $info
	 * @param array<mixed>|null $status
	 */
	#[DataProvider('errorStates')]
	public function testEveryErrorStateClosesTheSearch(array|false|null $info, ?array $status, bool $appApi): void {
		self::assertFalse($this->service($info, $status, $appApi)->searchAllowed());
	}

	public function testOkAndPatchDiffersKeepTheSearchOpen(): void {
		self::assertTrue($this->service(self::registered('0.1.0'), $this->statusResponse(['appVersion' => '0.1.0']))->searchAllowed());

		$this->stored = [];
		self::assertTrue($this->service(self::registered('0.1.4'), $this->statusResponse(['appVersion' => '0.1.4']))->searchAllowed());
	}

	public function testAFreshVerdictIsUsedWithoutAskingAgain(): void {
		$this->stored[ExAppService::KEY_BACKEND_STATE] = (string)json_encode(['state' => ExAppService::STATE_BACKEND_MISSING, 'checkedAt' => self::NOW - 59]);
		$service = $this->service(self::registered('0.1.0'), $this->statusResponse(['appVersion' => '0.1.0']));

		self::assertFalse($service->searchAllowed());
		self::assertSame(0, $this->infoCalls);
		self::assertSame([], $this->routes);
	}

	public function testAVerdictOlderThanSixtySecondsIsDeterminedAgainUnderTheFirstAdmin(): void {
		$this->stored[ExAppService::KEY_BACKEND_STATE] = (string)json_encode(['state' => ExAppService::STATE_BACKEND_MISSING, 'checkedAt' => self::NOW - 61]);
		$service = $this->service(self::registered('0.1.0'), $this->statusResponse(['appVersion' => '0.1.0']));

		self::assertTrue($service->searchAllowed());
		self::assertSame(1, $this->infoCalls);
		self::assertSame(['GET /status'], $this->routes);

		$remembered = json_decode($this->stored[ExAppService::KEY_BACKEND_STATE], true);
		self::assertIsArray($remembered);
		self::assertSame(ExAppService::STATE_OK, $remembered['state']);
	}

	public function testAVerdictFromTheFutureOrOfUnknownShapeIsNotTrusted(): void {
		// Both remembered values would answer differently from the fresh
		// verdict; a fresh lookup is what proves they were not taken.
		$this->stored[ExAppService::KEY_BACKEND_STATE] = (string)json_encode(['state' => ExAppService::STATE_BACKEND_MISSING, 'checkedAt' => self::NOW + 600]);
		self::assertTrue($this->service(self::registered('0.1.0'), $this->statusResponse(['appVersion' => '0.1.0']))->searchAllowed());
		self::assertSame(1, $this->infoCalls);

		$this->stored[ExAppService::KEY_BACKEND_STATE] = (string)json_encode(['state' => 'fine', 'checkedAt' => self::NOW]);
		self::assertFalse($this->service(null)->searchAllowed());
		self::assertSame(2, $this->infoCalls);

		$this->stored[ExAppService::KEY_BACKEND_STATE] = 'not json';
		self::assertFalse($this->service(null)->searchAllowed());
		self::assertSame(3, $this->infoCalls);
	}

	public function testADriftOnRecordStillClosesTheSearchWithoutACall(): void {
		$this->stored[ExAppService::KEY_BACKEND_VERSION] = '0.4.0';
		$this->stored[ExAppService::KEY_BACKEND_STATE] = (string)json_encode(['state' => ExAppService::STATE_OK, 'checkedAt' => self::NOW]);

		self::assertFalse($this->service(self::registered('0.1.0'))->searchAllowed());
		self::assertSame([], $this->routes);
	}

	public function testANewVerdictReplacesAnOldDriftOnRecord(): void {
		$this->stored[ExAppService::KEY_BACKEND_VERSION] = '0.4.0';
		$service = $this->service(self::registered('0.1.0'), $this->statusResponse(['appVersion' => '0.1.0']));

		self::assertSame(ExAppService::STATE_OK, $service->backendState('root')['state']);
		self::assertNull($service->driftOnRecord());
		self::assertTrue($service->searchAllowed());
	}
}
