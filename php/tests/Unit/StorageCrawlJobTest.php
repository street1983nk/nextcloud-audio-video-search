<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\BackgroundJobs\StorageCrawlJob;
use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\IJobList;
use OCP\Files\Cache\ICacheEntry;
use OCP\Files\IMimeTypeLoader;
use OCP\Files\StorageNotAvailableException;
use OCP\Lock\LockedException;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The first crawl of one mount: bands, budget, cursor, end only on an empty slice.
 *
 * Everything is a double; the clock is a counter the cases move. Storage 3 is a
 * home with the walk root 11, its files lie below files/.
 */
#[CoversClass(StorageCrawlJob::class)]
final class StorageCrawlJobTest extends TestCase {
	private const STORAGE = 3;
	private const ROOT = 11;
	private const WEBM = 5;
	private const TEXT = 6;

	private int $now = 1_000_000;
	private IJobList&MockObject $jobList;
	private StorageService&MockObject $storage;
	private QueueService&MockObject $queue;
	private CrawlMapper&MockObject $crawls;
	private IMimeTypeLoader&MockObject $mimeTypes;
	/** @var list<int> */
	private array $queued = [];
	/** @var list<int> */
	private array $advanced = [];
	private int $finished = 0;
	/** @var list<array<string, int>> */
	private array $scheduled = [];
	/** @var array{storageId: int, rootId: int, lastFileId: int, generation: int, startedAt: ?int, finishedAt: ?int}|null */
	private ?array $crawl = null;

	protected function setUp(): void {
		parent::setUp();

		$this->queued = [];
		$this->advanced = [];
		$this->finished = 0;
		$this->scheduled = [];
		$this->crawl = [
			'storageId' => self::STORAGE,
			'rootId' => self::ROOT,
			'lastFileId' => 0,
			'generation' => 0,
			'startedAt' => $this->now,
			'finishedAt' => null,
		];

		$this->jobList = $this->createMock(IJobList::class);
		$this->jobList->method('scheduleAfter')->willReturnCallback(function (string $job, int $at, mixed $argument): void {
			self::assertSame(StorageCrawlJob::class, $job);
			self::assertSame($this->now + StorageCrawlJob::INTERVAL_SECONDS, $at);
			$this->scheduled[] = $argument;
		});
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('mountRelativePath')->willReturnCallback(
			static fn (int $storageId, string $path): ?string => str_starts_with($path, 'files/') ? substr($path, 6) : null,
		);
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('admissible')->willReturnCallback(
			static fn (int $storageId, int $mimeId, string $relative): bool => $mimeId === self::WEBM && $relative !== '',
		);
		$this->queue->method('enqueue')->willReturnCallback(function (string $kind, ?int $fileId, int $storageId): void {
			self::assertSame(QueueMapper::KIND_CONTENT, $kind);
			self::assertSame(self::STORAGE, $storageId);
			$this->queued[] = (int)$fileId;
		});
		$this->crawls = $this->createMock(CrawlMapper::class);
		$this->crawls->method('find')->willReturnCallback(fn (): ?array => $this->crawl);
		$this->crawls->method('advance')->willReturnCallback(function (int $storageId, int $rootId, int $cursor): void {
			$this->advanced[] = $cursor;
		});
		$this->crawls->method('finish')->willReturnCallback(function (): void {
			$this->finished++;
		});
		$this->mimeTypes = $this->createMock(IMimeTypeLoader::class);
		$this->mimeTypes->method('exists')->willReturn(true);
		$this->mimeTypes->method('getId')->willReturnCallback(
			static fn (string $mime): int => $mime === 'video/webm' ? self::WEBM : self::TEXT,
		);
	}

	private function job(): StorageCrawlJob {
		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturnCallback(fn (): int => $this->now);

		return new StorageCrawlJob(
			$time,
			$this->jobList,
			$this->storage,
			$this->queue,
			$this->crawls,
			$this->mimeTypes,
			$this->createMock(LoggerInterface::class),
		);
	}

	private function runJob(mixed $argument = null): void {
		$argument ??= StorageCrawlJob::argument(self::STORAGE, self::ROOT);
		(new \ReflectionMethod(StorageCrawlJob::class, 'run'))->invoke($this->job(), $argument);
	}

	private function entry(int $id, string $mime = 'video/webm', string $path = ''): ICacheEntry&MockObject {
		$entry = $this->createMock(ICacheEntry::class);
		$entry->method('getId')->willReturn($id);
		$entry->method('getMimeType')->willReturn($mime);
		$entry->method('getPath')->willReturn($path === '' ? 'files/m' . $id . '.webm' : $path);

		return $entry;
	}

	/** @return list<ICacheEntry> */
	private function band(int $from, int $count): array {
		$entries = [];
		for ($id = $from; $id < $from + $count; $id++) {
			$entries[] = $this->entry($id);
		}

		return $entries;
	}

	public function testAnEmptySliceFinishesTheCrawl(): void {
		$slices = [[$this->entry(7), $this->entry(9, 'text/plain', 'files/a.txt')], []];
		$this->storage->method('getFileSlice')->willReturnCallback(function (int $s, int $r, int $after, int $limit) use (&$slices): array {
			self::assertSame(StorageCrawlJob::BAND, $limit);
			return array_shift($slices) ?? [];
		});

		$this->runJob();

		self::assertSame([7], $this->queued);
		self::assertSame([9], $this->advanced);
		self::assertSame(1, $this->finished);
		self::assertSame([], $this->scheduled);
	}

	public function testARunEndsAfterMaxFilesWithTheCursorSetAndNotFinished(): void {
		$this->storage->method('getFileSlice')->willReturnCallback(
			fn (int $s, int $r, int $after, int $limit): array => $this->band($after + 1, $limit),
		);

		$this->runJob();

		self::assertCount(StorageCrawlJob::MAX_FILES, $this->queued);
		self::assertSame([500, 1000, 1500, 2000], $this->advanced);
		self::assertSame(0, $this->finished);
		self::assertSame([StorageCrawlJob::argument(self::STORAGE, self::ROOT)], $this->scheduled);
	}

	public function testARunEndsAfterSixtySeconds(): void {
		$this->storage->method('getFileSlice')->willReturnCallback(function (int $s, int $r, int $after, int $limit): array {
			$this->now += StorageCrawlJob::MAX_SECONDS + 1;
			return $this->band($after + 1, 3);
		});

		$this->runJob();

		self::assertSame([1, 2, 3], $this->queued);
		self::assertSame([3], $this->advanced);
		self::assertSame(0, $this->finished);
		self::assertCount(1, $this->scheduled);
	}

	public function testTheCrawlContinuesAtTheStoredCursor(): void {
		$this->crawl['lastFileId'] = 40;
		$asked = [];
		$this->storage->method('getFileSlice')->willReturnCallback(function (int $s, int $r, int $after) use (&$asked): array {
			$asked[] = $after;
			return [];
		});

		$this->runJob();

		self::assertSame([40], $asked);
		self::assertSame(1, $this->finished);
	}

	public function testALockedFileEndsTheRunWithoutFinishing(): void {
		$this->storage->method('getFileSlice')->willReturn($this->band(1, 2));
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('admissible')->willReturn(true);
		$this->queue->method('enqueue')->willThrowException(new LockedException('x'));

		$this->runJob();

		self::assertSame(0, $this->finished);
		// The locked first file stays in front of the cursor.
		self::assertSame([0], $this->advanced);
		self::assertCount(1, $this->scheduled);
	}

	public function testAStorageThatIsNotAvailableEndsTheRunWithoutFinishing(): void {
		$this->storage->method('getFileSlice')->willThrowException(new StorageNotAvailableException('gone'));

		$this->runJob();

		self::assertSame(0, $this->finished);
		self::assertSame([], $this->queued);
		self::assertCount(1, $this->scheduled);
	}

	public function testAFileOutsideTheWalkRootOrNotAMediumIsNotQueued(): void {
		$slices = [[
			$this->entry(5, 'video/webm', 'files_trashbin/files/x.webm.d1'),
			$this->entry(6, 'text/plain', 'files/notes.txt'),
			$this->entry(8),
		], []];
		$this->storage->method('getFileSlice')->willReturnCallback(function () use (&$slices): array {
			return array_shift($slices) ?? [];
		});

		$this->runJob();

		self::assertSame([8], $this->queued);
		self::assertSame([8], $this->advanced);
	}

	public function testAFinishedOrMissingCrawlDoesNothing(): void {
		$this->storage->expects(self::never())->method('getFileSlice');
		$this->crawl['finishedAt'] = $this->now;
		$this->runJob();

		$this->crawl = null;
		$this->runJob();

		self::assertSame([], $this->scheduled);
	}

	public function testAnArgumentWithoutAMountIsDropped(): void {
		$this->storage->expects(self::never())->method('getFileSlice');

		$this->runJob(['storage_id' => 0, 'root_id' => self::ROOT]);
		$this->runJob('nonsense');

		self::assertSame([], $this->scheduled);
	}
}
