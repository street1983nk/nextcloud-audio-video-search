<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Listener\CacheEventListener;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\Files\Cache\CacheEntryInsertedEvent;
use OCP\Files\Cache\CacheEntryRemovedEvent;
use OCP\Files\Cache\CacheEntryUpdatedEvent;
use OCP\Files\IMimeTypeDetector;
use OCP\Files\IMimeTypeLoader;
use OCP\Files\Storage\IStorage;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * Scanner finds into the work stock, with the media type as the first question.
 */
#[CoversClass(CacheEventListener::class)]
final class CacheEventListenerTest extends TestCase {
	private const WEBM = 5;
	private const MP2T = 7;

	private QueueService&MockObject $queue;
	private StorageService&MockObject $storage;
	private IMimeTypeLoader&MockObject $mimeTypes;
	/** @var list<array{0: string, 1: int, 2: int}> */
	private array $queued = [];

	protected function setUp(): void {
		parent::setUp();

		$this->queued = [];
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('admissible')->willReturnCallback(
			static fn (int $storageId, int $mimeId, string $relative): bool => in_array($mimeId, [self::WEBM, self::MP2T], true) && $storageId === 3,
		);
		$this->queue->method('enqueue')->willReturnCallback(function (string $kind, ?int $fileId, int $storageId): void {
			$this->queued[] = [$kind, (int)$fileId, $storageId];
		});
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('mountRelativePath')->willReturnCallback(
			static fn (int $storageId, string $path): ?string => str_starts_with($path, 'files/') ? substr($path, 6) : null,
		);
		$this->storage->method('inMountSet')->willReturnCallback(static fn (int $storageId): bool => $storageId === 3);
		$this->mimeTypes = $this->createMock(IMimeTypeLoader::class);
		$this->mimeTypes->method('exists')->willReturn(true);
		$this->mimeTypes->method('getId')->willReturnCallback(
			static fn (string $mime): int => match ($mime) {
				'video/webm' => self::WEBM,
				'video/MP2T' => self::MP2T,
				default => 99,
			},
		);
	}

	private function listener(): CacheEventListener {
		$detector = $this->createMock(IMimeTypeDetector::class);
		$detector->method('detectPath')->willReturnCallback(static fn (string $path): string => match (pathinfo($path, PATHINFO_EXTENSION)) {
			'webm' => 'video/webm',
			'mts' => 'video/MP2T',
			'jpg' => 'image/jpeg',
			default => 'application/octet-stream',
		});

		return new CacheEventListener($this->queue, $this->storage, $detector, $this->mimeTypes, $this->createMock(LoggerInterface::class));
	}

	private function storageDouble(): IStorage {
		return $this->createMock(IStorage::class);
	}

	public function testInsertedAndUpdatedMediaAreQueuedAsContent(): void {
		$listener = $this->listener();
		$listener->handle(new CacheEntryInsertedEvent($this->storageDouble(), 'files/a.webm', 10, 3));
		$listener->handle(new CacheEntryUpdatedEvent($this->storageDouble(), 'files/b.mts', 11, 3));

		self::assertSame([
			[QueueMapper::KIND_CONTENT, 10, 3],
			[QueueMapper::KIND_CONTENT, 11, 3],
		], $this->queued);
	}

	public function testAFolderOrAnotherTypeIsDroppedBeforeAnyLookup(): void {
		$this->storage->expects(self::never())->method('mountRelativePath');
		$this->storage->expects(self::never())->method('inMountSet');
		$this->mimeTypes->expects(self::never())->method('getId');
		$listener = $this->listener();

		$listener->handle(new CacheEntryInsertedEvent($this->storageDouble(), 'files/Musik', 10, 3));
		$listener->handle(new CacheEntryUpdatedEvent($this->storageDouble(), 'appdata_x/preview/1/2.jpg', 11, 1));
		$listener->handle(new CacheEntryRemovedEvent($this->storageDouble(), 'files/notes.txt', 12, 3));

		self::assertSame([], $this->queued);
	}

	public function testAMediumOutsideTheWalkRootIsNotQueued(): void {
		$this->listener()->handle(new CacheEntryInsertedEvent($this->storageDouble(), 'files_versions/a.webm.v1', 10, 3));

		self::assertSame([], $this->queued);
	}

	public function testARemovedMediumIsADeleteAndARemovedFileOfAnotherStorageIsNot(): void {
		$listener = $this->listener();
		$listener->handle(new CacheEntryRemovedEvent($this->storageDouble(), 'files/a.webm', 10, 3));
		$listener->handle(new CacheEntryRemovedEvent($this->storageDouble(), 'a.webm', 11, 8));

		self::assertSame([[QueueMapper::KIND_DELETE, 10, 3]], $this->queued);
	}

	public function testRemovedThenInsertedOfTheSameFileIdEndsAsContent(): void {
		// A move across storages: the queue lets the later of content and
		// delete of one file id replace the earlier one (QueueMapper, plan
		// 02-03); the listener has to hand both over in the order they came.
		$listener = $this->listener();
		$listener->handle(new CacheEntryRemovedEvent($this->storageDouble(), 'files/a.webm', 10, 3));
		$listener->handle(new CacheEntryInsertedEvent($this->storageDouble(), 'files/a.webm', 10, 3));

		self::assertSame([
			[QueueMapper::KIND_DELETE, 10, 3],
			[QueueMapper::KIND_CONTENT, 10, 3],
		], $this->queued);
	}

	public function testAFailureIsSwallowed(): void {
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('admissible')->willReturn(true);
		$this->queue->method('enqueue')->willThrowException(new \RuntimeException('database is locked'));

		$this->listener()->handle(new CacheEntryInsertedEvent($this->storageDouble(), 'files/a.webm', 10, 3));

		$this->addToAssertionCount(1);
	}
}
