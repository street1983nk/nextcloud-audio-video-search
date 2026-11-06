<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCP\App\IAppManager;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\Http\Client\IResponse;
use OCP\IAppConfig;
use OCP\IGroupManager;
use OCP\IUserManager;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The container is outside the trust boundary of this app: everything it sends
 * is a proposal and is type checked here before anybody reads it.
 *
 * The transport is the one doubled method, ExAppService::proxyRequest, because
 * OCA\AppAPI\PublicFunctions belongs to another app and is absent from the
 * autoload space of this suite. Everything above the transport is real code:
 * the four silent failure cases, the clamping and the field checks.
 */
#[CoversClass(ExAppService::class)]
final class ExAppServiceTest extends TestCase {
	/** @var array<string, string> the stored string keys of the app */
	private array $stored = [];

	/** @var list<array{path:string,userId:string,method:string,params:array<string,mixed>,timeout:float}> */
	private array $calls = [];

	private IAppConfig&MockObject $appConfig;

	protected function setUp(): void {
		parent::setUp();

		$this->stored = [];
		$this->calls = [];
		$this->appConfig = $this->createMock(IAppConfig::class);
		$this->appConfig->method('getValueString')->willReturnCallback(
			fn (string $app, string $key, string $default = ''): string => $this->stored[$key] ?? $default,
		);
		$this->appConfig->method('setValueString')->willReturnCallback(
			function (string $app, string $key, string $value): bool {
				self::assertSame(Application::APP_ID, $app);
				$this->stored[$key] = $value;

				return true;
			},
		);
	}

	/**
	 * The service with the transport scripted to one answer.
	 *
	 * @param array<mixed>|IResponse|null $answer
	 */
	private function service(array|IResponse|null $answer, ?LoggerInterface $logger = null, string $ownVersion = '0.1.0'): ExAppService&MockObject {
		$appManager = $this->createMock(IAppManager::class);
		$appManager->method('getAppVersion')->willReturn($ownVersion);

		$service = $this->getMockBuilder(ExAppService::class)
			->setConstructorArgs([
				$appManager,
				$this->createMock(IUserManager::class),
				$this->appConfig,
				$logger ?? $this->createMock(LoggerInterface::class),
				$this->createMock(IGroupManager::class),
				$this->createMock(ITimeFactory::class),
			])
			->onlyMethods(['proxyRequest'])
			->getMock();
		$service->method('proxyRequest')->willReturnCallback(
			function (string $path, string $userId, string $method, array $params, float $timeout) use ($answer): array|IResponse|null {
				$this->calls[] = ['path' => $path, 'userId' => $userId, 'method' => $method, 'params' => $params, 'timeout' => $timeout];

				return $answer;
			},
		);

		return $service;
	}

	private function answer(string $body, int $status = 200): IResponse&MockObject {
		$response = $this->createMock(IResponse::class);
		$response->method('getStatusCode')->willReturn($status);
		$response->method('getBody')->willReturn($body);

		return $response;
	}

	/** @param array<mixed> $value */
	private function json(array $value): IResponse&MockObject {
		$encoded = json_encode($value);
		self::assertIsString($encoded);

		return $this->answer($encoded);
	}

	// -- the four silent failure cases ------------------------------------------

	public function testAnUnreachableBackendIsNullAndLogsTheRouteOnly(): void {
		$logger = $this->createMock(LoggerInterface::class);
		$logger->expects(self::once())->method('warning')->with(
			self::stringContains('unreachable'),
			self::callback(static fn (array $context): bool => array_keys($context) === ['route', 'error', 'innerMs']
				&& $context['route'] === '/search'),
		);

		self::assertNull($this->service(['error' => 'timeout'], $logger)->search('alice', 'Haushalt', 25));
	}

	public function testAnErrorStatusIsNull(): void {
		self::assertNull($this->service($this->answer('{}', 500))->search('alice', 'Haushalt', 25));
	}

	public function testABodyAboveTheCeilingIsNullBeforeItIsParsed(): void {
		$huge = '{"hits":[],"pad":"' . str_repeat('a', 1048577) . '"}';

		self::assertNull($this->service($this->answer($huge))->search('alice', 'Haushalt', 25));
	}

	public function testABodyThatIsNotAJsonObjectIsNull(): void {
		self::assertNull($this->service($this->answer('not json'))->search('alice', 'Haushalt', 25));
		self::assertNull($this->service($this->answer('"a string"'))->search('alice', 'Haushalt', 25));
		self::assertNull($this->service($this->json(['appVersion' => '0.1.0']))->search('alice', 'Haushalt', 25));
	}

	public function testARefusedPreFlightIsNull(): void {
		self::assertNull($this->service(null)->search('alice', 'Haushalt', 25));
	}

	// -- search -----------------------------------------------------------------

	public function testAValidAnswerIsTheListOfHits(): void {
		$service = $this->service($this->json([
			'appVersion' => '0.1.0',
			'hits' => [
				['fileId' => 11, 'startMs' => 754200, 'excerpt' => 'der Haushalt wird beraten', 'sample' => false],
				['fileId' => 12, 'startMs' => 0, 'excerpt' => '', 'sample' => true],
			],
		]));

		self::assertSame([
			['fileId' => 11, 'startMs' => 754200, 'excerpt' => 'der Haushalt wird beraten', 'sample' => false],
			['fileId' => 12, 'startMs' => 0, 'excerpt' => '', 'sample' => true],
		], $service->search('alice', '  Haushalt  ', 25));
		self::assertSame('/search', $this->calls[0]['path']);
		self::assertSame('POST', $this->calls[0]['method']);
		self::assertSame(['term' => 'Haushalt', 'limit' => 25], $this->calls[0]['params']);
		self::assertSame(ExAppService::REQUEST_TIMEOUT_SECONDS, $this->calls[0]['timeout']);
	}

	public function testMalformedHitsAreDroppedAndCounted(): void {
		$logger = $this->createMock(LoggerInterface::class);
		$logger->expects(self::once())->method('warning')->with(
			self::stringContains('dropped'),
			['count' => 6],
		);
		$service = $this->service($this->json([
			'hits' => [
				['fileId' => 0, 'startMs' => 1, 'excerpt' => 'x', 'sample' => false],
				['fileId' => -3, 'startMs' => 1, 'excerpt' => 'x', 'sample' => false],
				['fileId' => 5, 'startMs' => -1, 'excerpt' => 'x', 'sample' => false],
				['fileId' => 5, 'startMs' => 1, 'excerpt' => 42, 'sample' => false],
				['fileId' => '5', 'startMs' => 1, 'excerpt' => 'x', 'sample' => false],
				'not a hit',
				['fileId' => 7, 'startMs' => 1, 'excerpt' => 'kept', 'sample' => false],
			],
		]), $logger);

		self::assertSame(
			[['fileId' => 7, 'startMs' => 1, 'excerpt' => 'kept', 'sample' => false]],
			$service->search('alice', 'Haushalt', 25),
		);
	}

	public function testAHitNeverCarriesATitleOrAPathOfTheContainer(): void {
		$service = $this->service($this->json([
			'hits' => [['fileId' => 7, 'startMs' => 1, 'excerpt' => 'x', 'sample' => false, 'title' => 'secret.mp4', 'path' => '/bob/secret.mp4']],
		]));

		$hits = $service->search('alice', 'Haushalt', 25);

		self::assertIsArray($hits);
		self::assertSame(['fileId', 'startMs', 'excerpt', 'sample'], array_keys($hits[0]));
	}

	public function testAnEmptyTermMakesNoCall(): void {
		self::assertSame([], $this->service(null)->search('alice', "  \t ", 25));
		self::assertSame([], $this->calls);
	}

	public function testTheTermAndTheLimitAreClamped(): void {
		$service = $this->service($this->json(['hits' => []]));

		$service->search('alice', str_repeat('ä', 250), 500);
		$service->search('alice', 'x', 0);

		self::assertSame(200, mb_strlen((string)$this->calls[0]['params']['term']));
		self::assertSame(50, $this->calls[0]['params']['limit']);
		self::assertSame(1, $this->calls[1]['params']['limit']);
	}

	public function testTheBackendVersionOfAnAnswerIsRemembered(): void {
		$this->service($this->json(['appVersion' => '0.1.3', 'hits' => []]))->search('alice', 'x', 5);

		self::assertSame('0.1.3', $this->stored[ExAppService::KEY_BACKEND_VERSION] ?? null);
	}

	public function testAVersionThatIsNotAVersionIsNotRemembered(): void {
		$this->service($this->json(['appVersion' => '<b>1</b>', 'hits' => []]))->search('alice', 'x', 5);

		self::assertArrayNotHasKey(ExAppService::KEY_BACKEND_VERSION, $this->stored);
	}

	// -- lockstep ---------------------------------------------------------------

	public function testLockstepComparesMajorAndMinorOnly(): void {
		$service = $this->service(null);

		self::assertSame(ExAppService::LOCKSTEP_MATCH, $service->lockstep('0.1.5'));
		self::assertSame(ExAppService::LOCKSTEP_DRIFT, $service->lockstep('0.2.0'));
		self::assertSame(ExAppService::LOCKSTEP_UNKNOWN, $service->lockstep(''));
		self::assertSame(ExAppService::LOCKSTEP_UNKNOWN, $service->lockstep(null));
		self::assertSame(ExAppService::LOCKSTEP_UNKNOWN, $service->lockstep('nonsense'));
		self::assertSame('0.1.0', $service->ownVersion());
		self::assertSame('0.1', $service->majorMinor('0.1.9'));
		self::assertNull($service->majorMinor('x.y'));
	}

	public function testADriftOnRecordStopsTheSearchWithoutACall(): void {
		$this->stored[ExAppService::KEY_BACKEND_VERSION] = '0.2.0';
		$service = $this->service($this->json(['hits' => []]));

		self::assertFalse($service->searchAllowed());
		self::assertNotNull($service->driftOnRecord());
	}

	public function testNothingOnRecordOrAPatchDifferenceAllowsTheSearch(): void {
		self::assertTrue($this->service(null)->searchAllowed());

		$this->stored[ExAppService::KEY_BACKEND_VERSION] = '0.1.7';
		self::assertTrue($this->service(null)->searchAllowed());
	}

	// -- excerpt, sample, removeSample ------------------------------------------

	public function testExcerptHasItsShape(): void {
		$service = $this->service($this->json(['known' => true, 'excerpt' => 'an dieser Stelle']));

		self::assertSame(['known' => true, 'excerpt' => 'an dieser Stelle'], $service->excerpt('alice', 11, 42000));
		self::assertSame(['fileId' => 11, 'atMs' => 42000], $this->calls[0]['params']);
		self::assertSame('/excerpt', $this->calls[0]['path']);
	}

	public function testExcerptOfAnUnknownFileIsKnownFalse(): void {
		$service = $this->service($this->json(['known' => false, 'excerpt' => null]));

		self::assertSame(['known' => false, 'excerpt' => null], $service->excerpt('alice', 11, 0));
	}

	public function testExcerptRefusesBadInputAndBadAnswers(): void {
		self::assertNull($this->service($this->json(['known' => true, 'excerpt' => 'x']))->excerpt('alice', 0, 0));
		self::assertNull($this->service($this->json(['known' => true, 'excerpt' => 'x']))->excerpt('alice', 1, -1));
		self::assertSame([], $this->calls);
		self::assertNull($this->service($this->json(['known' => 'yes', 'excerpt' => 'x']))->excerpt('alice', 1, 0));
		self::assertNull($this->service($this->json(['known' => true, 'excerpt' => 5]))->excerpt('alice', 1, 0));
	}

	public function testSamplePublishesWithTheUserAndTheLongerTimeout(): void {
		$service = $this->service($this->json(['result' => 'published', 'mediaId' => 3, 'indexRev' => 9]));

		self::assertSame(['result' => 'published', 'mediaId' => 3, 'indexRev' => 9], $service->sample('alice', 11, 42000));
		self::assertSame('/sample', $this->calls[0]['path']);
		self::assertSame(['fileId' => 11, 'userId' => 'alice', 'atMs' => 42000], $this->calls[0]['params']);
		self::assertSame(ExAppService::SAMPLE_TIMEOUT_SECONDS, $this->calls[0]['timeout']);
	}

	public function testSampleErrorsAreAClosedSet(): void {
		self::assertSame(['error' => 'gateway_denied'], $this->service($this->json(['error' => 'gateway_denied']))->sample('alice', 11, 0));
		self::assertNull($this->service($this->json(['error' => 'anything else']))->sample('alice', 11, 0));
		self::assertNull($this->service($this->json(['result' => 'published', 'mediaId' => 0, 'indexRev' => 1]))->sample('alice', 11, 0));
		self::assertNull($this->service($this->json(['result' => 'maybe', 'mediaId' => 3, 'indexRev' => 1]))->sample('alice', 11, 0));
		self::assertSame(
			['result' => 'stale_rejected', 'mediaId' => 3, 'indexRev' => null],
			$this->service($this->json(['result' => 'stale_rejected', 'mediaId' => 3, 'indexRev' => null]))->sample('alice', 11, 0),
		);
	}

	public function testRemoveSampleHasItsShape(): void {
		self::assertSame(
			['result' => 'removed', 'mediaId' => 3],
			$this->service($this->json(['result' => 'removed', 'mediaId' => 3]))->removeSample('alice', 11),
		);
		self::assertSame(['fileId' => 11], $this->calls[0]['params']);
		self::assertSame('/sample/remove', $this->calls[0]['path']);
		self::assertSame(
			['result' => 'not_found', 'mediaId' => null],
			$this->service($this->json(['result' => 'not_found', 'mediaId' => null]))->removeSample('alice', 11),
		);
		self::assertNull($this->service($this->json(['result' => 'gone', 'mediaId' => null]))->removeSample('alice', 11));
	}
}
