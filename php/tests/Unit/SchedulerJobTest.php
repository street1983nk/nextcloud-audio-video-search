<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\BackgroundJobs\SchedulerJob;
use OCA\AudioVideoSearch\BackgroundJobs\StorageCrawlJob;
use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\StorageClassifier;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\IJobList;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The first crawls start only after the handshake with the backend (D-02-05).
 */
#[CoversClass(SchedulerJob::class)]
final class SchedulerJobTest extends TestCase {
	private IJobList&MockObject $jobList;
	private StorageService&MockObject $storage;
	private CrawlMapper&MockObject $crawls;
	private ExAppService&MockObject $exApp;
	private StorageClassifier&MockObject $classifier;
	/** @var list<array<string, int>> */
	private array $added = [];

	protected function setUp(): void {
		parent::setUp();

		$this->added = [];
		$this->jobList = $this->createMock(IJobList::class);
		$this->jobList->method('add')->willReturnCallback(function (string $job, mixed $argument): void {
			self::assertSame(StorageCrawlJob::class, $job);
			$this->added[] = $argument;
		});
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('getMounts')->willReturn([
			['storage_id' => 3, 'root_id' => 10, 'overridden_root' => 11],
			['storage_id' => 4, 'root_id' => 20, 'overridden_root' => 21],
			['storage_id' => 5, 'root_id' => 30, 'overridden_root' => 31],
		]);
		$this->crawls = $this->createMock(CrawlMapper::class);
		$this->exApp = $this->createMock(ExAppService::class);
		$this->exApp->method('firstAdmin')->willReturn('admin');
		$this->classifier = $this->createMock(StorageClassifier::class);
	}

	private function runJob(): void {
		$job = new SchedulerJob(
			$this->createMock(ITimeFactory::class),
			$this->jobList,
			$this->storage,
			$this->crawls,
			$this->exApp,
			$this->classifier,
			$this->createMock(LoggerInterface::class),
		);
		(new \ReflectionMethod(SchedulerJob::class, 'run'))->invoke($job, null);
	}

	private function state(string $state): void {
		$this->exApp->method('backendState')->willReturn([
			'state' => $state, 'own' => '0.2.0', 'backend' => '0.2.0', 'companion' => 'ok', 'sampleCount' => 0, 'checkedAt' => 1,
		]);
	}

	/** @return list<array{string}> */
	public static function notReady(): array {
		return [
			[ExAppService::STATE_BACKEND_MISSING],
			[ExAppService::STATE_BACKEND_DISABLED],
			[ExAppService::STATE_BACKEND_UNREACHABLE],
			[ExAppService::STATE_VERSION_DRIFT],
			[ExAppService::STATE_NO_APP_API],
		];
	}

	#[DataProvider('notReady')]
	public function testNoCrawlBeforeTheBackendIsThere(string $state): void {
		$this->state($state);
		$this->crawls->expects(self::never())->method('upsert');

		$this->runJob();

		self::assertSame([], $this->added);
	}

	public function testNoCrawlWithoutAnEnabledAdmin(): void {
		$this->exApp = $this->createMock(ExAppService::class);
		$this->exApp->method('firstAdmin')->willReturn(null);
		$this->exApp->expects(self::never())->method('backendState');
		$this->crawls->expects(self::never())->method('upsert');

		$this->runJob();

		self::assertSame([], $this->added);
	}

	/** @return list<array{string}> */
	public static function ready(): array {
		return [[ExAppService::STATE_OK], [ExAppService::STATE_VERSION_PATCH_DIFFERS]];
	}

	#[DataProvider('ready')]
	public function testANewMountGetsACrawlAKnownOneNothingAndALostOneItsJobBack(string $state): void {
		$this->state($state);
		// 3 is new, 4 is finished, 5 is unfinished and its job got lost.
		$this->crawls->method('upsert')->willReturnCallback(static fn (int $storageId): bool => $storageId === 3);
		$this->crawls->method('find')->willReturnCallback(static fn (int $storageId, int $rootId): array => [
			'storageId' => $storageId,
			'rootId' => $rootId,
			'lastFileId' => 7,
			'generation' => 0,
			'startedAt' => 1,
			'finishedAt' => $storageId === 4 ? 2 : null,
		]);
		$this->jobList->method('has')->willReturn(false);

		$this->runJob();

		self::assertSame([
			StorageCrawlJob::argument(3, 11),
			StorageCrawlJob::argument(5, 31),
		], $this->added);
	}

	public function testAnUnfinishedCrawlWithAQueuedJobGetsNoSecondOne(): void {
		$this->state(ExAppService::STATE_OK);
		$this->crawls->method('upsert')->willReturn(false);
		$this->crawls->method('find')->willReturnCallback(static fn (int $storageId, int $rootId): array => [
			'storageId' => $storageId, 'rootId' => $rootId, 'lastFileId' => 0, 'generation' => 0, 'startedAt' => 1, 'finishedAt' => null,
		]);
		$this->jobList->method('has')->willReturn(true);

		$this->runJob();

		self::assertSame([], $this->added);
	}

	/** Storage 4 and 5 are external storages, 3 is a home. */
	private function external(): void {
		$this->storage->method('isExternal')->willReturnCallback(static fn (int $storageId): bool => in_array($storageId, [4, 5], true));
	}

	public function testANotCapturableExternalStorageGetsNoCrawlAndAHomeNeedsNoClassification(): void {
		$this->state(ExAppService::STATE_OK);
		$this->external();
		$asked = [];
		$this->classifier->method('refresh')->willReturnCallback(function (int $storageId, bool $mayCheck) use (&$asked): array {
			$asked[] = [$storageId, $mayCheck];

			return ['capturable' => $storageId === 5, 'becameCapturable' => $storageId === 5, 'checked' => true];
		});
		$this->crawls->method('upsert')->willReturn(true);

		$this->runJob();

		self::assertSame([[4, true], [5, true]], $asked);
		self::assertSame([StorageCrawlJob::argument(3, 11), StorageCrawlJob::argument(5, 31)], $this->added);
	}

	public function testAnExternalStorageThatBecameCapturableCrawlsAgainFromTheStart(): void {
		$this->state(ExAppService::STATE_OK);
		$this->external();
		$this->classifier->method('refresh')->willReturnCallback(static fn (int $storageId): array => [
			'capturable' => true, 'becameCapturable' => $storageId === 4, 'checked' => true,
		]);
		// Every mount has a finished crawl already.
		$this->crawls->method('upsert')->willReturn(false);
		$this->crawls->method('find')->willReturnCallback(static fn (int $storageId, int $rootId): array => [
			'storageId' => $storageId, 'rootId' => $rootId, 'lastFileId' => 9, 'generation' => 0, 'startedAt' => 1, 'finishedAt' => 2,
		]);
		$this->crawls->expects(self::once())->method('reset')->with(4, 21);
		$this->jobList->method('has')->willReturn(false);

		$this->runJob();

		self::assertSame([StorageCrawlJob::argument(4, 21)], $this->added);
	}

	public function testAClassifierThatThrowsMeansNoCrawlForThatStorageOnly(): void {
		$this->state(ExAppService::STATE_OK);
		$this->external();
		$this->classifier->method('refresh')->willReturnCallback(static function (int $storageId): array {
			if ($storageId === 4) {
				throw new \RuntimeException('database gone');
			}

			return ['capturable' => true, 'becameCapturable' => false, 'checked' => true];
		});
		$this->crawls->method('upsert')->willReturn(true);

		$this->runJob();

		self::assertSame([StorageCrawlJob::argument(3, 11), StorageCrawlJob::argument(5, 31)], $this->added);
	}

	public function testOnceTheBudgetIsSpentTheClassifierOnlyReads(): void {
		$this->state(ExAppService::STATE_OK);
		$this->external();
		$now = 1000;
		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturnCallback(function () use (&$now): int {
			return $now;
		});
		$asked = [];
		$this->classifier->method('refresh')->willReturnCallback(function (int $storageId, bool $mayCheck) use (&$asked, &$now): array {
			$asked[] = [$storageId, $mayCheck];
			// The first probe takes the whole budget.
			$now += SchedulerJob::CLASSIFY_SECONDS;

			return ['capturable' => false, 'becameCapturable' => false, 'checked' => $mayCheck];
		});
		$this->crawls->method('upsert')->willReturn(true);

		$job = new SchedulerJob(
			$time,
			$this->jobList,
			$this->storage,
			$this->crawls,
			$this->exApp,
			$this->classifier,
			$this->createMock(LoggerInterface::class),
		);
		(new \ReflectionMethod(SchedulerJob::class, 'run'))->invoke($job, null);

		self::assertSame([[4, true], [5, false]], $asked);
		self::assertSame([StorageCrawlJob::argument(3, 11)], $this->added);
	}
}
