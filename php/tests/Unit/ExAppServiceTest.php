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
use PHPUnit\Framework\Attributes\DataProvider;
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

	/**
	 * A search answer of the container (plan 03-08) with the paging fields.
	 *
	 * @param list<mixed> $hits
	 * @return array<string, mixed>
	 */
	private static function page(array $hits, int $nextOffset = 0, bool $hasMore = false): array {
		return ['appVersion' => '0.1.0', 'hits' => $hits, 'nextOffset' => $nextOffset, 'hasMore' => $hasMore];
	}

	public function testAValidAnswerIsThePageOfHits(): void {
		$service = $this->service($this->json(self::page([
			['fileId' => 11, 'startMs' => 754200, 'excerpt' => 'der Haushalt wird beraten', 'sample' => false, 'stage' => 'final'],
			['fileId' => 12, 'startMs' => 0, 'excerpt' => '', 'sample' => true, 'stage' => 'sample'],
			['fileId' => 13, 'startMs' => 5000, 'excerpt' => 'vorläufig', 'sample' => false, 'stage' => 'preview'],
		], 8, true)));

		self::assertSame([
			'hits' => [
				['fileId' => 11, 'startMs' => 754200, 'excerpt' => 'der Haushalt wird beraten', 'sample' => false, 'stage' => 'final'],
				['fileId' => 12, 'startMs' => 0, 'excerpt' => '', 'sample' => true, 'stage' => 'sample'],
				['fileId' => 13, 'startMs' => 5000, 'excerpt' => 'vorläufig', 'sample' => false, 'stage' => 'preview'],
			],
			'nextOffset' => 8,
			'hasMore' => true,
		], $service->search('alice', '  Haushalt  ', 25, 5));
		self::assertSame('/search', $this->calls[0]['path']);
		self::assertSame('POST', $this->calls[0]['method']);
		self::assertSame(ExAppService::REQUEST_TIMEOUT_SECONDS, $this->calls[0]['timeout']);
	}

	public function testTheOffsetGoesIntoTheBody(): void {
		$service = $this->service($this->json(self::page([], 17)));

		$service->search('alice', 'Haushalt', 20, 17);
		$service->search('alice', 'Haushalt', 20);
		$service->search('alice', 'Haushalt', 20, 99999);
		$service->search('alice', 'Haushalt', 20, -4);

		self::assertSame(['term' => 'Haushalt', 'limit' => 20, 'offset' => 17], $this->calls[0]['params']);
		self::assertSame(0, $this->calls[1]['params']['offset']);
		self::assertSame(ExAppService::MAX_OFFSET, $this->calls[2]['params']['offset']);
		self::assertSame(1200, ExAppService::MAX_OFFSET);
		self::assertSame(0, $this->calls[3]['params']['offset']);
	}

	/** @return array<string, array{array<string, mixed>}> */
	public static function answersWithoutPaging(): array {
		return [
			'missing nextOffset' => [['hits' => [], 'hasMore' => false]],
			'missing hasMore' => [['hits' => [], 'nextOffset' => 5]],
			'nextOffset as text' => [['hits' => [], 'nextOffset' => '5', 'hasMore' => false]],
			'negative nextOffset' => [['hits' => [], 'nextOffset' => -1, 'hasMore' => false]],
			'hasMore as number' => [['hits' => [], 'nextOffset' => 5, 'hasMore' => 1]],
		];
	}

	#[\PHPUnit\Framework\Attributes\DataProvider('answersWithoutPaging')]
	public function testAnAnswerWithoutValidPagingIsNull(array $answer): void {
		self::assertNull($this->service($this->json($answer))->search('alice', 'Haushalt', 25));
	}

	public function testAMissingOrUnknownStageIsAPreview(): void {
		$service = $this->service($this->json(self::page([
			['fileId' => 11, 'startMs' => 1, 'excerpt' => 'a', 'sample' => false],
			['fileId' => 12, 'startMs' => 2, 'excerpt' => 'b', 'sample' => false, 'stage' => 'draft'],
			['fileId' => 13, 'startMs' => 3, 'excerpt' => 'c', 'sample' => false, 'stage' => 'sample'],
			['fileId' => 14, 'startMs' => 4, 'excerpt' => 'd', 'sample' => true, 'stage' => 'final'],
			['fileId' => 15, 'startMs' => 5, 'excerpt' => 'e', 'sample' => false, 'stage' => null],
		])));

		$page = $service->search('alice', 'Haushalt', 25);

		self::assertIsArray($page);
		self::assertSame(
			['preview', 'preview', 'preview', 'sample', 'preview'],
			array_map(static fn (array $hit): string => $hit['stage'], $page['hits']),
		);
	}

	public function testAStageThatIsNoTextDropsTheHit(): void {
		$logger = $this->createMock(LoggerInterface::class);
		$logger->expects(self::once())->method('warning')->with(self::stringContains('dropped'), ['count' => 2]);
		$service = $this->service($this->json(self::page([
			['fileId' => 11, 'startMs' => 1, 'excerpt' => 'a', 'sample' => false, 'stage' => 2],
			['fileId' => 12, 'startMs' => 2, 'excerpt' => 'b', 'sample' => false, 'stage' => ['final']],
			['fileId' => 13, 'startMs' => 3, 'excerpt' => 'c', 'sample' => false, 'stage' => 'final'],
		])), $logger);

		$page = $service->search('alice', 'Haushalt', 25);

		self::assertIsArray($page);
		self::assertSame([13], array_map(static fn (array $hit): int => $hit['fileId'], $page['hits']));
	}

	public function testMalformedHitsAreDroppedAndCounted(): void {
		$logger = $this->createMock(LoggerInterface::class);
		$logger->expects(self::once())->method('warning')->with(
			self::stringContains('dropped'),
			['count' => 6],
		);
		$service = $this->service($this->json(self::page([
				['fileId' => 0, 'startMs' => 1, 'excerpt' => 'x', 'sample' => false],
				['fileId' => -3, 'startMs' => 1, 'excerpt' => 'x', 'sample' => false],
				['fileId' => 5, 'startMs' => -1, 'excerpt' => 'x', 'sample' => false],
				['fileId' => 5, 'startMs' => 1, 'excerpt' => 42, 'sample' => false],
				['fileId' => '5', 'startMs' => 1, 'excerpt' => 'x', 'sample' => false],
				'not a hit',
				['fileId' => 7, 'startMs' => 1, 'excerpt' => 'kept', 'sample' => false, 'stage' => 'final'],
		])), $logger);

		$page = $service->search('alice', 'Haushalt', 25);

		self::assertIsArray($page);
		self::assertSame(
			[['fileId' => 7, 'startMs' => 1, 'excerpt' => 'kept', 'sample' => false, 'stage' => 'final']],
			$page['hits'],
		);
	}

	public function testAHitNeverCarriesATitleOrAPathOfTheContainer(): void {
		$service = $this->service($this->json(self::page(
			[['fileId' => 7, 'startMs' => 1, 'excerpt' => 'x', 'sample' => false, 'stage' => 'final', 'title' => 'secret.mp4', 'path' => '/bob/secret.mp4']],
		)));

		$page = $service->search('alice', 'Haushalt', 25);

		self::assertIsArray($page);
		self::assertSame(['fileId', 'startMs', 'excerpt', 'sample', 'stage'], array_keys($page['hits'][0]));
	}

	public function testAnEmptyTermMakesNoCall(): void {
		self::assertSame(['hits' => [], 'nextOffset' => 0, 'hasMore' => false], $this->service(null)->search('alice', "  \t ", 25));
		self::assertSame([], $this->calls);
	}

	public function testTheTermAndTheLimitAreClamped(): void {
		$service = $this->service($this->json(self::page([])));

		$service->search('alice', str_repeat('ä', 250), 500);
		$service->search('alice', 'x', 0);

		self::assertSame(200, mb_strlen((string)$this->calls[0]['params']['term']));
		self::assertSame(50, $this->calls[0]['params']['limit']);
		self::assertSame(1, $this->calls[1]['params']['limit']);
	}

	public function testTheBackendVersionOfAnAnswerIsRemembered(): void {
		$this->service($this->json(['appVersion' => '0.1.3', 'hits' => [], 'nextOffset' => 0, 'hasMore' => false]))->search('alice', 'x', 5);

		self::assertSame('0.1.3', $this->stored[ExAppService::KEY_BACKEND_VERSION] ?? null);
	}

	public function testAVersionThatIsNotAVersionIsNotRemembered(): void {
		$this->service($this->json(['appVersion' => '<b>1</b>', 'hits' => [], 'nextOffset' => 0, 'hasMore' => false]))->search('alice', 'x', 5);

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
		$service = $this->service($this->json([
			'known' => true,
			'excerpt' => 'an dieser Stelle',
			'stage' => 'preview',
			'partial' => true,
			'pendingHere' => false,
			'reason' => null,
		]));

		self::assertSame([
			'known' => true,
			'excerpt' => 'an dieser Stelle',
			'stage' => 'preview',
			'partial' => true,
			'pendingHere' => false,
			'reason' => null,
			'limitHours' => null,
		], $service->excerpt('alice', 11, 42000));
		self::assertSame(['fileId' => 11, 'atMs' => 42000], $this->calls[0]['params']);
		self::assertSame('/excerpt', $this->calls[0]['path']);
	}

	public function testExcerptOfAnUnknownFileIsKnownFalse(): void {
		$unknown = [
			'known' => false,
			'excerpt' => null,
			'stage' => null,
			'partial' => false,
			'pendingHere' => false,
			'reason' => null,
			'limitHours' => null,
		];

		self::assertSame($unknown, $this->service($this->json(['known' => false]))->excerpt('alice', 11, 0));
		self::assertSame($unknown, $this->service($this->json(['known' => false, 'excerpt' => null]))->excerpt('alice', 11, 0));
	}

	public function testWithKnownFalseEveryOtherFieldIsIgnored(): void {
		// Whatever comes along with known false, even out of type, never
		// reaches the page: the answer is the one of an unknown file.
		$answer = $this->service($this->json([
			'known' => false,
			'excerpt' => 'der Haushalt wird beraten',
			'stage' => 7,
			'partial' => 'yes',
			'pendingHere' => true,
			'reason' => 'no_speech',
			'limitHours' => 99,
		]))->excerpt('alice', 11, 0);

		self::assertIsArray($answer);
		self::assertFalse($answer['known']);
		self::assertNull($answer['excerpt']);
		self::assertNull($answer['stage']);
		self::assertFalse($answer['partial']);
		self::assertFalse($answer['pendingHere']);
		self::assertNull($answer['reason']);
		self::assertNull($answer['limitHours']);
	}

	public function testMissingFieldsOfAKnownFileHaveTheirDefaults(): void {
		self::assertSame([
			'known' => true,
			'excerpt' => null,
			'stage' => null,
			'partial' => false,
			'pendingHere' => false,
			'reason' => null,
			'limitHours' => null,
		], $this->service($this->json(['known' => true]))->excerpt('alice', 11, 0));
	}

	public function testAReasonAndTheLimitArePassedOnForTheControllerToCheck(): void {
		$answer = $this->service($this->json([
			'known' => true,
			'excerpt' => null,
			'stage' => null,
			'partial' => false,
			'pendingHere' => false,
			'reason' => 'too_long',
			'limitHours' => 12,
		]))->excerpt('alice', 11, 0);

		self::assertIsArray($answer);
		self::assertSame('too_long', $answer['reason']);
		self::assertSame(12, $answer['limitHours']);
	}

	/** @return array<string, array{mixed, ?string}> */
	public static function stages(): array {
		return [
			'preview' => ['preview', 'preview'],
			'final' => ['final', 'final'],
			'sample' => ['sample', 'sample'],
			'null' => [null, null],
			'an unknown text' => ['draft', null],
		];
	}

	#[DataProvider('stages')]
	public function testTheStageIsAClosedListAndAnUnknownTextIsNull(mixed $stage, ?string $expected): void {
		$answer = $this->service($this->json(['known' => true, 'excerpt' => 'x', 'stage' => $stage]))->excerpt('alice', 11, 0);

		self::assertIsArray($answer);
		self::assertSame($expected, $answer['stage']);
	}

	/** @return array<string, array{string, mixed}> */
	public static function fieldsOutOfType(): array {
		return [
			'excerpt a number' => ['excerpt', 5],
			'stage a number' => ['stage', 2],
			'stage a list' => ['stage', ['final']],
			'stage true' => ['stage', true],
			'partial a text' => ['partial', 'true'],
			'partial a number' => ['partial', 1],
			'partial null' => ['partial', null],
			'pendingHere a text' => ['pendingHere', 'false'],
			'pendingHere a number' => ['pendingHere', 0],
			'pendingHere null' => ['pendingHere', null],
			'reason a number' => ['reason', 3],
			'reason a list' => ['reason', ['no_speech']],
			'reason false' => ['reason', false],
			'limitHours a text' => ['limitHours', '12'],
			'limitHours a float' => ['limitHours', 12.0],
			'limitHours zero' => ['limitHours', 0],
			'limitHours negative' => ['limitHours', -1],
			'limitHours beyond a day' => ['limitHours', 25],
			'limitHours true' => ['limitHours', true],
		];
	}

	#[DataProvider('fieldsOutOfType')]
	public function testOneFieldOutOfTypeMakesTheWholeAnswerNoAnswer(string $field, mixed $value): void {
		$valid = [
			'known' => true,
			'excerpt' => null,
			'stage' => 'preview',
			'partial' => false,
			'pendingHere' => false,
			'reason' => 'too_long',
			'limitHours' => 12,
		];
		// Positive control: the same answer with every field in type is valid.
		self::assertIsArray($this->service($this->json($valid))->excerpt('alice', 11, 0));

		$valid[$field] = $value;
		self::assertNull($this->service($this->json($valid))->excerpt('alice', 11, 0));
	}

	/** @return array<string, array{int}> */
	public static function limitsInRange(): array {
		return ['one hour' => [1], 'twelve hours' => [12], 'a day' => [24]];
	}

	#[DataProvider('limitsInRange')]
	public function testTheLimitFromOneToTwentyFourHoursIsKept(int $hours): void {
		$answer = $this->service($this->json(['known' => true, 'reason' => 'too_long', 'limitHours' => $hours]))->excerpt('alice', 11, 0);

		self::assertIsArray($answer);
		self::assertSame($hours, $answer['limitHours']);
	}

	public function testExcerptRefusesBadInputAndBadAnswers(): void {
		self::assertNull($this->service($this->json(['known' => true, 'excerpt' => 'x']))->excerpt('alice', 0, 0));
		self::assertNull($this->service($this->json(['known' => true, 'excerpt' => 'x']))->excerpt('alice', 1, -1));
		self::assertSame([], $this->calls);
		self::assertNull($this->service($this->json(['known' => 'yes', 'excerpt' => 'x']))->excerpt('alice', 1, 0));
		self::assertNull($this->service($this->json(['known' => true, 'excerpt' => 5]))->excerpt('alice', 1, 0));
		self::assertNull($this->service($this->json(['excerpt' => 'x']))->excerpt('alice', 1, 0));
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

	// -- the admin routes of occ (plan 02-10) ---------------------------------------

	/**
	 * The service with the transport scripted and an admin to ask as.
	 *
	 * @param array<mixed>|IResponse|null $answer
	 */
	private function adminService(array|IResponse|null $answer, ?string $admin = 'root'): ExAppService&MockObject {
		$appManager = $this->createMock(IAppManager::class);
		$appManager->method('getAppVersion')->willReturn('0.1.0');

		$service = $this->getMockBuilder(ExAppService::class)
			->setConstructorArgs([
				$appManager,
				$this->createMock(IUserManager::class),
				$this->appConfig,
				$this->createMock(LoggerInterface::class),
				$this->createMock(IGroupManager::class),
				$this->createMock(ITimeFactory::class),
			])
			->onlyMethods(['proxyRequest', 'firstAdmin'])
			->getMock();
		$service->method('firstAdmin')->willReturn($admin);
		$service->method('proxyRequest')->willReturnCallback(
			function (string $path, string $userId, string $method, array $params, float $timeout) use ($answer): array|IResponse|null {
				$this->calls[] = ['path' => $path, 'userId' => $userId, 'method' => $method, 'params' => $params, 'timeout' => $timeout];

				return $answer;
			},
		);

		return $service;
	}

	/** @return array<string, mixed> */
	private static function entry(array $override = []): array {
		return $override + ['fileId' => 11, 'mediaId' => 3, 'storageId' => 2, 'state' => 'active', 'stage' => 'keyed', 'reason' => null];
	}

	/** @return array<string, mixed> */
	private static function coverageAnswer(array $override = []): array {
		return $override + [
			'contents' => 4,
			'transcribed' => 1,
			'files' => 6,
			'byState' => ['active' => 6, 'trashed' => 0, 'unreadable' => 1, 'vanished' => 0],
			'byStage' => ['failed' => 1, 'fetching' => 0, 'keyed' => 3, 'pending' => 3, 'probing' => 0],
			'dueWork' => 3,
			'byPreview' => ['no_speech' => 1, 'queued' => 2] + array_fill_keys(ExAppService::PREVIEW_NAMES, 0),
		];
	}

	public function testWorkstockAsksAsAnAdminWithGetAndTheQuery(): void {
		$service = $this->adminService($this->json(['files' => [self::entry()], 'next' => 11]));

		$page = $service->workstock(['state' => 'active', 'after' => 5, 'limit' => 1]);

		self::assertSame(['files' => [self::entry()], 'next' => 11], $page);
		self::assertSame('/workstock', $this->calls[0]['path']);
		self::assertSame('root', $this->calls[0]['userId']);
		self::assertSame('GET', $this->calls[0]['method']);
		self::assertSame(['state' => 'active', 'after' => 5, 'limit' => 1], $this->calls[0]['params']);
		self::assertSame(ExAppService::ADMIN_TIMEOUT_SECONDS, $this->calls[0]['timeout']);
		self::assertSame(10.0, ExAppService::ADMIN_TIMEOUT_SECONDS);
	}

	public function testWorkstockRefusesAQueryOutsideTheContractWithoutACall(): void {
		$service = $this->adminService($this->json(['files' => [], 'next' => null]));

		self::assertNull($service->workstock(['state' => 'deleted']));
		self::assertNull($service->workstock(['after' => -1]));
		self::assertNull($service->workstock(['limit' => 0]));
		self::assertNull($service->workstock(['limit' => 1001]));
		self::assertSame([], $this->calls);
	}

	public function testWorkstockWithoutAnAdminMakesNoCall(): void {
		$service = $this->adminService($this->json(['files' => [], 'next' => null]), null);

		self::assertNull($service->workstock([]));
		self::assertSame([], $this->calls);
	}

	/** @return array<string, array{array<mixed>}> */
	public static function malformedPages(): array {
		return [
			'extra key' => [['files' => [], 'next' => null, 'path' => '/x']],
			'missing next' => [['files' => []]],
			'files not a list' => [['files' => ['a' => self::entry()], 'next' => null]],
			'next zero' => [['files' => [], 'next' => 0]],
			'entry with a path' => [['files' => [self::entry() + ['path' => '/alice/files/a.mp4']], 'next' => null]],
			'entry without reason' => [['files' => [array_diff_key(self::entry(), ['reason' => true])], 'next' => null]],
			'unknown state' => [['files' => [self::entry(['state' => 'gone'])], 'next' => null]],
			'unknown stage' => [['files' => [self::entry(['stage' => 'done'])], 'next' => null]],
			'reason with text' => [['files' => [self::entry(['reason' => 'Sitzung.mp4 denied'])], 'next' => null]],
			'file id zero' => [['files' => [self::entry(['fileId' => 0])], 'next' => null]],
			'media id as text' => [['files' => [self::entry(['mediaId' => '3'])], 'next' => null]],
			'negative storage' => [['files' => [self::entry(['storageId' => -1])], 'next' => null]],
		];
	}

	#[\PHPUnit\Framework\Attributes\DataProvider('malformedPages')]
	public function testAPageWithAnythingOutOfShapeIsNoPage(array $answer): void {
		self::assertNull($this->adminService($this->json($answer))->workstock([]));
	}

	public function testCoverageHasItsFixedKeysInTheOrderOfTheLists(): void {
		$service = $this->adminService($this->json(self::coverageAnswer()));

		$coverage = $service->coverage();

		self::assertNotNull($coverage);
		self::assertSame(ExAppService::COVERAGE_KEYS, array_keys($coverage));
		self::assertSame(ExAppService::WORK_STATES, array_keys($coverage['byState']));
		self::assertSame(ExAppService::WORK_STAGES, array_keys($coverage['byStage']));
		self::assertSame(ExAppService::PREVIEW_NAMES, array_keys($coverage['byPreview']));
		self::assertSame(2, $coverage['byPreview']['queued']);
		self::assertSame(1, $coverage['byPreview']['no_speech']);
		self::assertSame(1, $coverage['transcribed']);
		self::assertSame('/coverage', $this->calls[0]['path']);
		self::assertSame('GET', $this->calls[0]['method']);
	}

	/** @return array<string, array{array<mixed>}> */
	public static function malformedCoverage(): array {
		return [
			'extra key' => [self::coverageAnswer() + ['name' => 'x']],
			'negative' => [self::coverageAnswer(['files' => -1])],
			'text number' => [self::coverageAnswer(['contents' => '4'])],
			'over 100 percent' => [self::coverageAnswer(['transcribed' => 5])],
			'unknown state' => [self::coverageAnswer(['byState' => ['active' => 1, 'gone' => 0, 'trashed' => 0, 'unreadable' => 0]])],
			'missing stage' => [self::coverageAnswer(['byStage' => ['keyed' => 1]])],
			'without byPreview' => [array_diff_key(self::coverageAnswer(), ['byPreview' => true])],
			'missing preview name' => [self::coverageAnswer(['byPreview' => ['queued' => 1]])],
			'preview reason with text' => [self::coverageAnswer(['byPreview' => ['Sitzung.mp4' => 1] + array_diff_key(array_fill_keys(ExAppService::PREVIEW_NAMES, 0), ['queued' => true])])],
			'negative preview count' => [self::coverageAnswer(['byPreview' => ['queued' => -1] + array_fill_keys(ExAppService::PREVIEW_NAMES, 0)])],
		];
	}

	#[\PHPUnit\Framework\Attributes\DataProvider('malformedCoverage')]
	public function testCoverageOutOfShapeIsNoAnswer(array $answer): void {
		self::assertNull($this->adminService($this->json($answer))->coverage());
	}

	public function testAnUnreachableBackendIsNoCoverageAndNoPage(): void {
		self::assertNull($this->adminService(['error' => 'refused'])->coverage());
		self::assertNull($this->adminService(['error' => 'refused'])->workstock([]));
		self::assertNull($this->adminService($this->answer('{}', 500))->coverage());
	}

	public function testTheClosedListsAreTheOnesOfTheContainer(): void {
		// backend/src/audio_video_search_backend/store/repo.py STATES and STAGES.
		self::assertSame(['active', 'unreadable', 'vanished', 'trashed'], ExAppService::WORK_STATES);
		self::assertSame(['pending', 'probing', 'fetching', 'keyed', 'failed'], ExAppService::WORK_STAGES);
	}

	// -- the reconcile of the container (plan 02-19) -----------------------------------

	/** @return array<string, mixed> */
	private static function reconcileAnswer(array $override = []): array {
		// array_replace keeps the order of the contract, so assertSame can compare whole answers.
		return array_replace(['swept' => 2, 'vanished' => 1, 'orphaned' => 0, 'walkedMounts' => 3, 'requeued' => 4, 'rejected' => 1, 'reproofDue' => 0, 'skippedReason' => null], $override);
	}

	public function testReconcileNowPostsTheReproveFlagAsAnAdminWithTheLongTimeout(): void {
		$service = $this->adminService($this->json(self::reconcileAnswer()));

		self::assertSame(self::reconcileAnswer(), $service->reconcileNow(false));
		self::assertSame(self::reconcileAnswer(), $service->reconcileNow(true));

		self::assertSame('/reconcile/run', $this->calls[0]['path']);
		self::assertSame('POST', $this->calls[0]['method']);
		self::assertSame('root', $this->calls[0]['userId']);
		self::assertSame(['reprove' => false], $this->calls[0]['params']);
		self::assertSame(['reprove' => true], $this->calls[1]['params']);
		self::assertSame(120.0, $this->calls[0]['timeout']);
		self::assertSame(120.0, ExAppService::RECONCILE_TIMEOUT_SECONDS);
		self::assertSame(array_keys(self::reconcileAnswer()), ExAppService::RECONCILE_KEYS);
	}

	public function testASkippedRoundKeepsItsReasonCode(): void {
		$answer = self::reconcileAnswer(['skippedReason' => 'mounts_unavailable']);

		self::assertSame($answer, $this->adminService($this->json($answer))->reconcileNow(false));
	}

	/** @return array<string, array{array<string, mixed>}> */
	public static function malformedReconcile(): array {
		return [
			'extra key' => [self::reconcileAnswer() + ['path' => '/x']],
			'missing key' => [array_diff_key(self::reconcileAnswer(), ['swept' => 0])],
			'negative' => [self::reconcileAnswer(['requeued' => -1])],
			'text number' => [self::reconcileAnswer(['swept' => '2'])],
			'reason with a path' => [self::reconcileAnswer(['skippedReason' => '/files/a'])],
			'reason not text' => [self::reconcileAnswer(['skippedReason' => 3])],
		];
	}

	#[\PHPUnit\Framework\Attributes\DataProvider('malformedReconcile')]
	public function testAReconcileAnswerOutOfShapeIsNoAnswer(array $answer): void {
		self::assertNull($this->adminService($this->json($answer))->reconcileNow(false));
	}

	public function testAReconcileWithoutABackendOrAnAdminIsNoAnswer(): void {
		self::assertNull($this->adminService(['error' => 'refused'])->reconcileNow(false));
		self::assertNull($this->adminService($this->answer('{}', 500))->reconcileNow(false));
		self::assertNull($this->adminService($this->json(self::reconcileAnswer()), null)->reconcileNow(false));
		self::assertCount(2, $this->calls);
	}
}
