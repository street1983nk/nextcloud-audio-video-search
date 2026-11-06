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

	protected function setUp(): void {
		parent::setUp();

		$this->written = [];
		$this->debug = false;
		$this->failOnWrite = false;
	}

	private function controller(?ExAppService $exApp = null, ?LoggerInterface $logger = null): SettingsController {
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

		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn('root');
		$session = $this->createMock(IUserSession::class);
		$session->method('getUser')->willReturn($user);

		return new SettingsController(
			$this->createMock(IRequest::class),
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
		$logger->expects(self::once())->method('error')->with(
			self::stringContains('state'),
			self::callback(static fn (array $context): bool => ($context['exception'] ?? null) instanceof \RuntimeException),
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
		self::assertSame(['GET /admin/state', 'POST /admin/sample'], $routes);
	}
}
