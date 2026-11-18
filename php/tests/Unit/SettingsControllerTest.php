<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Controller\SettingsController;
use OCA\AudioVideoSearch\Search\Provider;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCP\AppFramework\Http;
use OCP\IAppConfig;
use OCP\IConfig;
use OCP\IRequest;
use OCP\IUser;
use OCP\IUserSession;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The two routes of the admin page: one reads the state of the other half,
 * one writes the test result switch, and that one only in debug mode.
 *
 * The protection of both routes is what they lack: no attribute that lifts the
 * admin requirement, the request token or the session (T-01-32). The last test
 * reads the attributes of the class and holds that.
 */
#[CoversClass(SettingsController::class)]
final class SettingsControllerTest extends TestCase {
	/** @var list<array{string,string,bool}> what was written to the app config */
	private array $written = [];

	private bool $debug = false;
	private bool $failOnWrite = false;
	private string $userZone = '';
	private string $systemZone = 'UTC';

	protected function setUp(): void {
		parent::setUp();

		$this->written = [];
		$this->debug = false;
		$this->failOnWrite = false;
		$this->userZone = '';
		$this->systemZone = 'UTC';
	}

	/**
	 * @param array<string, mixed> $params what the request carries, as getParams() returns it
	 */
	private function controller(?ExAppService $exApp = null, ?LoggerInterface $logger = null, array $params = []): SettingsController {
		$appConfig = $this->createMock(IAppConfig::class);
		$appConfig->method('setValueBool')->willReturnCallback(
			function (string $app, string $key, bool $value): bool {
				if ($this->failOnWrite) {
					throw new \RuntimeException('database is gone');
				}
				$this->written[] = [$app, $key, $value];

				return true;
			},
		);

		$config = $this->createMock(IConfig::class);
		$config->method('getSystemValueBool')->willReturnCallback(
			fn (string $key, bool $default = false): bool => $key === 'debug' ? $this->debug : $default,
		);
		$config->method('getUserValue')->willReturnCallback(
			fn (string $uid, string $app, string $key, mixed $default = ''): string => $this->userZone,
		);
		$config->method('getSystemValueString')->willReturnCallback(
			fn (string $key, string $default = ''): string => $key === 'default_timezone' ? $this->systemZone : $default,
		);

		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn('root');
		$session = $this->createMock(IUserSession::class);
		$session->method('getUser')->willReturn($user);

		$request = $this->createMock(IRequest::class);
		$request->method('getParams')->willReturn($params + ['_route' => 'audio_video_search.settings.saveResources']);

		return new SettingsController(
			$request,
			$exApp ?? $this->createMock(ExAppService::class),
			$appConfig,
			$config,
			$session,
			$logger ?? $this->createMock(LoggerInterface::class),
		);
	}

	// -- GET /admin/state ---------------------------------------------------------

	public function testTheStateRouteAnswersTheStateOfTheSignedInAdmin(): void {
		$state = [
			'state' => ExAppService::STATE_OK,
			'own' => '0.1.0',
			'backend' => '0.1.0',
			'companion' => 'ok',
			'sampleCount' => 1,
			'checkedAt' => 1_800_000_000,
		];
		$exApp = $this->createMock(ExAppService::class);
		$exApp->expects(self::once())->method('backendState')->with('root')->willReturn($state);

		$response = $this->controller($exApp)->state();

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame($state, $response->getData());
	}

	public function testAFailingStateIs500WithAStaticSentence(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('backendState')->willThrowException(new \RuntimeException('/var/www/data/alice'));
		$logger = $this->createMock(LoggerInterface::class);
		// Exactly the class, nothing else: the message of the exception holds a
		// server path, and no part of it may reach the log context (E-01).
		$logger->expects(self::once())->method('error')->with(
			self::stringContains('state'),
			self::identicalTo(['class' => \RuntimeException::class]),
		);

		$response = $this->controller($exApp, $logger)->state();

		self::assertSame(Http::STATUS_INTERNAL_SERVER_ERROR, $response->getStatus());
		self::assertSame(['error' => 'The state could not be checked.'], $response->getData());
	}

	// -- POST /admin/sample -------------------------------------------------------

	public function testTheSwitchIsRefusedWithoutDebugModeAndNothingIsStored(): void {
		$response = $this->controller()->setSample(true);

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame(['error' => 'Debug mode is off.'], $response->getData());
		self::assertSame([], $this->written);
	}

	/** @return array<string, array{mixed, bool}> */
	public static function booleans(): array {
		return [
			'true' => [true, true],
			'false' => [false, false],
			'form true' => ['true', true],
			'form false' => ['false', false],
		];
	}

	#[DataProvider('booleans')]
	public function testInDebugModeABooleanIsStored(mixed $sent, bool $stored): void {
		$this->debug = true;

		$response = $this->controller()->setSample($sent);

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame(['visible' => $stored], $response->getData());
		self::assertSame([[Application::APP_ID, Provider::KEY_SAMPLE_VISIBLE, $stored]], $this->written);
	}

	/** @return array<string, array{mixed}> */
	public static function notBooleans(): array {
		return [
			'yes' => ['yes'],
			'one' => [1],
			'string one' => ['1'],
			'missing' => [null],
			'list' => [[true]],
		];
	}

	#[DataProvider('notBooleans')]
	public function testAnythingButABooleanIs400AndStoresNothing(mixed $sent): void {
		$this->debug = true;

		$response = $this->controller()->setSample($sent);

		self::assertSame(Http::STATUS_BAD_REQUEST, $response->getStatus());
		self::assertSame(['error' => 'visible must be a boolean'], $response->getData());
		self::assertSame([], $this->written);
	}

	public function testAFailedWriteIs500WithAStaticSentence(): void {
		$this->debug = true;
		$this->failOnWrite = true;
		$logger = $this->createMock(LoggerInterface::class);
		$logger->expects(self::once())->method('error');

		$response = $this->controller(null, $logger)->setSample(true);

		self::assertSame(Http::STATUS_INTERNAL_SERVER_ERROR, $response->getStatus());
		self::assertSame(['error' => 'The switch could not be saved.'], $response->getData());
	}

	// -- GET and POST /admin/resources (plan 05-05) ----------------------------------

	/** @return array<string, mixed> the contract shape of GET /resources */
	private static function resourcesAnswer(int $standard = 4): array {
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
			'threads' => ['cpus' => 8, 'standard' => $standard, 'admin' => null, 'effective' => $standard],
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

	public function testTheResourcesRouteAddsTheZonesAndTheAdminZone(): void {
		$this->userZone = 'Europe/Berlin';
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('resources')->willReturn(self::resourcesAnswer());

		$response = $this->controller($exApp)->resources();

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		$data = $response->getData();
		self::assertSame('balanced', $data['proposed']);
		self::assertSame(\DateTimeZone::listIdentifiers(), $data['zones']);
		self::assertSame('Europe/Berlin', $data['defaultZone']);
	}

	public function testWithoutAnAccountZoneTheSystemZoneCounts(): void {
		$this->userZone = 'Mars/Base';
		$this->systemZone = 'Europe/Paris';
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('resources')->willReturn(self::resourcesAnswer());

		self::assertSame('Europe/Paris', $this->controller($exApp)->resources()->getData()['defaultZone']);
	}

	public function testWithoutAnyKnownZoneItIsUtc(): void {
		$this->userZone = '';
		$this->systemZone = 'Nowhere/Land';
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('resources')->willReturn(self::resourcesAnswer());

		self::assertSame('UTC', $this->controller($exApp)->resources()->getData()['defaultZone']);
	}

	public function testASilentBackendIs503(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('resources')->willReturn(null);

		$response = $this->controller($exApp)->resources();

		self::assertSame(Http::STATUS_SERVICE_UNAVAILABLE, $response->getStatus());
		self::assertSame(['error' => 'The backend did not answer.'], $response->getData());
	}

	/**
	 * A POST through the controller with the parameters the framework would
	 * hand in: the named arguments and the same keys in getParams().
	 *
	 * @param array<string, mixed> $params
	 */
	private function post(array $params, ExAppService $exApp): \OCP\AppFramework\Http\DataResponse {
		return $this->controller($exApp, null, $params)->saveResources(
			$params['profile'] ?? null,
			$params['threads'] ?? null,
			$params['window'] ?? null,
			$params['offline'] ?? null,
		);
	}

	/** @return array<string, array{array<string, mixed>, string}> */
	public static function refusedBodies(): array {
		return [
			'threads zero' => [['threads' => 0], 'threads'],
			'threads negative' => [['threads' => -1], 'threads'],
			'threads as text' => [['threads' => '2'], 'threads'],
			'threads as float' => [['threads' => 2.0], 'threads'],
			'same start and end' => [['window' => ['start' => '22:00', 'end' => '22:00', 'zone' => 'Europe/Berlin']], 'window_same'],
			'unknown zone' => [['window' => ['start' => '22:00', 'end' => '06:00', 'zone' => 'Mars/Base']], 'window_zone'],
			'missing zone' => [['window' => ['start' => '22:00', 'end' => '06:00']], 'window_zone'],
			'bad start' => [['window' => ['start' => '7:5', 'end' => '06:00', 'zone' => 'UTC']], 'window_start'],
			'start 24:00' => [['window' => ['start' => '24:00', 'end' => '06:00', 'zone' => 'UTC']], 'window_start'],
			'empty end' => [['window' => ['start' => '22:00', 'end' => '', 'zone' => 'UTC']], 'window_end'],
			'missing end' => [['window' => ['start' => '22:00', 'zone' => 'UTC']], 'window_end'],
			'window foreign key' => [['window' => ['start' => '22:00', 'end' => '06:00', 'zone' => 'UTC', 'x' => 1]], 'body'],
			'window as text' => [['window' => '22-06'], 'body'],
			'foreign key' => [['foo' => 1], 'body'],
			'foreign key beside a valid one' => [['profile' => 'fast', 'foo' => 1], 'body'],
			'empty body' => [[], 'body'],
			'unknown profile' => [['profile' => 'turbo'], 'profile'],
			'profile none' => [['profile' => 'none'], 'profile'],
			'offline as text' => [['offline' => 'yes'], 'offline'],
			'offline as number' => [['offline' => 1], 'offline'],
			'offline null' => [['offline' => null], 'offline'],
		];
	}

	/** @param array<string, mixed> $params */
	#[DataProvider('refusedBodies')]
	public function testAMalformedBodyIs400WithTheFieldAndTheBackendIsNotWrittenTo(array $params, string $field): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->expects(self::never())->method('saveResources');
		$exApp->method('resources')->willReturn(self::resourcesAnswer());
		$logger = $this->createMock(LoggerInterface::class);
		$logger->expects(self::once())->method('warning')->with(self::anything(), self::identicalTo(['field' => $field]));

		$response = $this->controller($exApp, $logger, $params)->saveResources(
			$params['profile'] ?? null,
			$params['threads'] ?? null,
			$params['window'] ?? null,
			$params['offline'] ?? null,
		);

		self::assertSame(Http::STATUS_BAD_REQUEST, $response->getStatus());
		self::assertSame(['field' => $field], $response->getData());
	}

	public function testThreadsAboveTheDefaultAre400(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->expects(self::never())->method('saveResources');
		$exApp->method('resources')->willReturn(self::resourcesAnswer(4));

		$response = $this->post(['threads' => 5], $exApp);

		self::assertSame(Http::STATUS_BAD_REQUEST, $response->getStatus());
		self::assertSame(['field' => 'threads'], $response->getData());
	}

	public function testThreadsWithASilentBackendAre503(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->expects(self::never())->method('saveResources');
		$exApp->method('resources')->willReturn(null);

		self::assertSame(Http::STATUS_SERVICE_UNAVAILABLE, $this->post(['threads' => 2], $exApp)->getStatus());
	}

	public function testAValidBodyIsHandedOnAndTheAnswerCarriesTheZones(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('resources')->willReturn(self::resourcesAnswer(4));
		$exApp->expects(self::once())->method('saveResources')->with(self::identicalTo([
			'profile' => 'fast',
			'offline' => true,
			'window' => ['start' => '22:00', 'end' => '06:00', 'zone' => 'Europe/Berlin'],
			'threads' => 4,
		]))->willReturn(['status' => 200, 'body' => self::resourcesAnswer(4)]);

		$response = $this->post([
			'profile' => 'fast',
			'threads' => 4,
			'window' => ['start' => '22:00', 'end' => '06:00', 'zone' => 'Europe/Berlin'],
			'offline' => true,
		], $exApp);

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame('balanced', $response->getData()['proposed']);
		self::assertArrayHasKey('zones', $response->getData());
	}

	public function testNullThreadsAndNullWindowMeanDefaultAndAlways(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->expects(self::never())->method('resources');
		$exApp->expects(self::once())->method('saveResources')
			->with(self::identicalTo(['window' => null, 'threads' => null]))
			->willReturn(['status' => 200, 'body' => self::resourcesAnswer()]);

		self::assertSame(Http::STATUS_OK, $this->post(['threads' => null, 'window' => null], $exApp)->getStatus());
	}

	public function testALockedProfileOfTheBackendIs409WithTheNumbers(): void {
		$locked = ['code' => 'profile_locked', 'needBytes' => 5368709120, 'availableBytes' => 3328599654];
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('saveResources')->willReturn(['status' => 409, 'body' => $locked]);

		$response = $this->post(['profile' => 'quality'], $exApp);

		self::assertSame(Http::STATUS_CONFLICT, $response->getStatus());
		self::assertSame($locked, $response->getData());
	}

	public function testARefusalOfTheBackendIs400WithItsField(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('saveResources')->willReturn(['status' => 400, 'body' => ['field' => 'window_zone']]);

		$response = $this->post(['window' => ['start' => '22:00', 'end' => '06:00', 'zone' => 'UTC']], $exApp);

		self::assertSame(Http::STATUS_BAD_REQUEST, $response->getStatus());
		self::assertSame(['field' => 'window_zone'], $response->getData());
	}

	public function testASilentBackendOnSaveIs503(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('saveResources')->willReturn(['status' => 503, 'body' => null]);

		$response = $this->post(['offline' => false], $exApp);

		self::assertSame(Http::STATUS_SERVICE_UNAVAILABLE, $response->getStatus());
		self::assertSame(['error' => 'The backend did not answer.'], $response->getData());
	}

	// -- the protection is the absence of attributes ---------------------------------

	public function testNoRouteLiftsTheAdminTheTokenOrTheSessionRequirement(): void {
		$forbidden = ['NoAdminRequired', 'NoCSRFRequired', 'PublicPage', 'ExAppRequired', 'AuthorizedAdminSetting', 'SubAdminRequired'];
		$routes = [];

		foreach ((new \ReflectionClass(SettingsController::class))->getMethods(\ReflectionMethod::IS_PUBLIC) as $method) {
			foreach ($method->getAttributes() as $attribute) {
				$short = substr(strrchr('\\' . $attribute->getName(), '\\') ?: '', 1);
				self::assertNotContains($short, $forbidden, $method->getName() . ' carries ' . $short);
				if ($short === 'FrontpageRoute') {
					$arguments = $attribute->getArguments();
					$routes[] = ($arguments['verb'] ?? '') . ' ' . ($arguments['url'] ?? '');
				}
			}
		}

		sort($routes);
		self::assertSame(['GET /admin/resources', 'GET /admin/state', 'POST /admin/resources', 'POST /admin/sample'], $routes);
	}
}
