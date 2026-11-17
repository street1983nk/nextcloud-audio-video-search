<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\BackgroundJobs\ExclusionClearJob;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\IJobList;
use OCP\Files\Cache\ICacheEntry;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The clearing of a folder excluded after the fact (plan 02-18, DISC-03,
 * D-02-04): the media files of one mount in bands of 500 through
 * StorageService::getFileSlice, an exclude row for every file a rule of now
 * covers, the cursor carried to the successor.
 *
 * Storage 4 is a home walked from files/; the rule in force is the folder
 * privat. Storage 9 is excluded as a whole.
 */
#[CoversClass(ExclusionClearJob::class)]
final class ExclusionClearJobTest extends TestCase {
	private IJobList&MockObject $jobList;
	private StorageService&MockObject $storage;
	private QueueService&MockObject $queue;
	private ExclusionService&MockObject $exclusions;
	private LoggerInterface&MockObject $logger;
	private int $now = 1000;
	/** @var list<array{0: string, 1: ?int, 2: int}> */
	private array $queued = [];
	/** @var list<array{0: int, 1: mixed}> time and argument of every successor */
	private array $successors = [];
	/** @var list<array{0: int, 1: int, 2: int, 3: int}> storage, root, cursor and limit of every slice asked for */
	private array $asked = [];
	/** @var array<int, string> internal path per file id of storage 4 */
	private array $files = [];
	/** @var list<string> */
	private array $logged = [];

	protected function setUp(): void {
		parent::setUp();

		$this->now = 1000;
		$this->queued = [];
		$this->successors = [];
		$this->asked = [];
		$this->logged = [];
		$this->files = [];
		$this->jobList = $this->createMock(IJobList::class);
		$this->jobList->method('scheduleAfter')->willReturnCallback(function (string $job, int $at, mixed $argument): void {
			self::assertSame(ExclusionClearJob::class, $job);
			$this->successors[] = [$at, $argument];
		});
		$this->jobList->expects(self::never())->method('add');
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('getFileSlice')->willReturnCallback(function (int $storageId, int $rootId, int $after, int $limit): array {
			$this->asked[] = [$storageId, $rootId, $after, $limit];
			$slice = [];
			foreach ($this->files as $id => $path) {
				if ($id > $after && count($slice) < $limit) {
					$slice[] = $this->entry($id, $path);
				}
			}

			return $slice;
		});
		$this->storage->method('mountRelativePath')->willReturnCallback(
			static fn (int $storageId, string $path): ?string => str_starts_with($path, 'files/') ? substr($path, 6) : null,
		);
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('enqueue')->willReturnCallback(function (string $kind, ?int $fileId, int $storageId): void {
			$this->queued[] = [$kind, $fileId, $storageId];
		});
		$this->exclusions = $this->createMock(ExclusionService::class);
		$this->exclusions->method('isExcluded')->willReturnCallback(
			static fn (int $storageId, string $relative): bool => $storageId === 9 || $relative === 'privat' || str_starts_with($relative, 'privat/'),
		);
		$this->logger = $this->createMock(LoggerInterface::class);
		foreach (['debug', 'info', 'notice', 'warning', 'error'] as $level) {
			$this->logger->method($level)->willReturnCallback(function (string|\Stringable $message, array $context = []): void {
				$this->logged[] = $message . ' ' . json_encode($context);
			});
		}
	}

	private function entry(int $id, string $path): ICacheEntry&MockObject {
		$entry = $this->createMock(ICacheEntry::class);
		$entry->method('getId')->willReturn($id);
		$entry->method('getPath')->willReturn($path);

		return $entry;
	}

	private function runJob(mixed $argument): void {
		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturnCallback(fn (): int => $this->now);
		$job = new ExclusionClearJob($time, $this->jobList, $this->storage, $this->queue, $this->exclusions, $this->logger);
		(new \ReflectionMethod(ExclusionClearJob::class, 'run'))->invoke($job, $argument);
	}

	public function testTheFilesUnderTheRuleGetAnExcludeRowAndTheOthersNothing(): void {
		$this->files = [
			101 => 'files/privat/a.webm',
			102 => 'files/öffentlich/b.webm',
			103 => 'files/privat/tief/c.mp3',
			104 => 'files/privatsache/d.webm',
		];

		$this->runJob(ExclusionClearJob::argument(4, 41, 0));

		self::assertSame([
			[QueueMapper::KIND_EXCLUDE, 101, 4],
			[QueueMapper::KIND_EXCLUDE, 103, 4],
		], $this->queued);
		self::assertSame([4, 41, 0, ExclusionClearJob::BAND], $this->asked[0]);
		self::assertSame(500, ExclusionClearJob::BAND);
		// Fewer files than a band: the mount is done, no successor.
		self::assertSame([], $this->successors);
		self::assertCount(1, $this->asked);
	}

	public function testBandAfterBandUntilTheMountIsDone(): void {
		for ($id = 1; $id <= 1200; $id++) {
			$this->files[$id] = $id % 2 === 0 ? 'files/privat/' . $id . '.webm' : 'files/x/' . $id . '.webm';
		}

		$this->runJob(ExclusionClearJob::argument(4, 41, 0));

		self::assertSame([[4, 41, 0, 500], [4, 41, 500, 500], [4, 41, 1000, 500]], $this->asked);
		self::assertCount(600, $this->queued);
		self::assertSame([], $this->successors);
	}

	public function testTheRunContinuesAtTheCursorOfItsArgument(): void {
		$this->files = [5 => 'files/privat/alt.webm', 77 => 'files/privat/neu.webm'];

		$this->runJob(ExclusionClearJob::argument(4, 41, 50));

		self::assertSame([[4, 41, 50, 500]], $this->asked);
		self::assertSame([[QueueMapper::KIND_EXCLUDE, 77, 4]], $this->queued);
	}

	/** The cron slot is shared: after MAX_SECONDS the successor carries the cursor. */
	public function testARunEndsAtItsDeadlineAndItsSuccessorCarriesTheCursor(): void {
		for ($id = 1; $id <= 1200; $id++) {
			$this->files[$id] = 'files/privat/' . $id . '.webm';
		}
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('enqueue')->willReturnCallback(function (string $kind, ?int $fileId, int $storageId): void {
			$this->queued[] = [$kind, $fileId, $storageId];
			$this->now += 1;
		});

		$this->runJob(ExclusionClearJob::argument(4, 41, 0));

		self::assertSame([[4, 41, 0, 500]], $this->asked);
		self::assertCount(500, $this->queued);
		self::assertSame([[$this->now + ExclusionClearJob::INTERVAL_SECONDS, ExclusionClearJob::argument(4, 41, 500)]], $this->successors);
	}

	/** A storage excluded as a whole has its exclude_storage row; no row per file. */
	public function testAStorageExcludedAsAWholeIsNotWalked(): void {
		$this->files = [1 => 'files/privat/a.webm'];

		$this->runJob(ExclusionClearJob::argument(9, 90, 0));

		self::assertSame([], $this->asked);
		self::assertSame([], $this->queued);
		self::assertSame([], $this->successors);
	}

	public function testAFileOutsideEveryWalkRootIsSkipped(): void {
		$this->files = [1 => 'files_trashbin/files/privat/a.webm.d1', 2 => 'files/privat/b.webm'];

		$this->runJob(ExclusionClearJob::argument(4, 41, 0));

		self::assertSame([[QueueMapper::KIND_EXCLUDE, 2, 4]], $this->queued);
	}

	public function testAnArgumentWithoutAMountIsDroppedWithAWarning(): void {
		$this->runJob(['storage_id' => 0, 'root_id' => 41, 'last_file_id' => 0]);
		$this->runJob(null);

		self::assertSame([], $this->asked);
		self::assertSame([], $this->successors);
		self::assertCount(2, $this->logged);
	}

	/**
	 * The applied fingerprint says done, so a lost run would leave the files of
	 * the folder findable: a failure tries the same band again later, and the
	 * log line carries the class, never the message with its path.
	 */
	public function testAFailureTriesTheSameBandAgainLaterAndLogsNoPath(): void {
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('getFileSlice')->willThrowException(new \RuntimeException('files/privat/geheim.webm'));

		$this->runJob(ExclusionClearJob::argument(4, 41, 70));

		self::assertSame([[1000 + ExclusionClearJob::RETRY_SECONDS, ExclusionClearJob::argument(4, 41, 70)]], $this->successors);
		self::assertStringNotContainsString('geheim', implode("\n", $this->logged));
		self::assertStringContainsString(\RuntimeException::class, implode("\n", $this->logged));
	}
}
