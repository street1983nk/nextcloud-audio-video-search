<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Listener\FileEventListener;
use OCA\AudioVideoSearch\Listener\UserEventListener;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\Files\Events\Node\NodeCopiedEvent;
use OCP\Files\Events\Node\NodeCreatedEvent;
use OCP\Files\Events\Node\NodeDeletedEvent;
use OCP\Files\Events\Node\NodeRenamedEvent;
use OCP\Files\Events\Node\NodeTouchedEvent;
use OCP\Files\Events\Node\NodeWrittenEvent;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IMimeTypeLoader;
use OCP\Files\Mount\IMountPoint;
use OCP\Files\Node;
use OCP\IAppConfig;
use OCP\IUser;
use OCP\User\Events\UserDeletedEvent;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * Node events into the work stock: which kind for which event.
 *
 * Storages 3 and 4 are in the mount set; their files lie below files/. Media
 * type 5 is video/webm, 6 is text/plain.
 */
#[CoversClass(FileEventListener::class)]
#[CoversClass(UserEventListener::class)]
final class FileEventListenerTest extends TestCase {
	private const WEBM = 5;
	private const TEXT = 6;

	private QueueService&MockObject $queue;
	private StorageService&MockObject $storage;
	private LoggerInterface&MockObject $logger;
	/** @var list<array{0: string, 1: int, 2: int}> */
	private array $queued = [];

	protected function setUp(): void {
		parent::setUp();

		$this->queued = [];
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('admissible')->willReturnCallback(
			static fn (int $storageId, int $mimeId, string $relative): bool => $mimeId === self::WEBM && in_array($storageId, [3, 4], true),
		);
		$this->queue->method('enqueue')->willReturnCallback(function (string $kind, ?int $fileId, int $storageId): void {
			$this->queued[] = [$kind, (int)$fileId, $storageId];
		});
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('mountRelativePath')->willReturnCallback(
			static fn (int $storageId, string $path): ?string => str_starts_with($path, 'files/') ? substr($path, 6) : null,
		);
		$this->storage->method('inMountSet')->willReturnCallback(static fn (int $storageId): bool => in_array($storageId, [3, 4], true));
		$this->logger = $this->createMock(LoggerInterface::class);
	}

	private function listener(): FileEventListener {
		$mimeTypes = $this->createMock(IMimeTypeLoader::class);
		$mimeTypes->method('exists')->willReturn(true);
		$mimeTypes->method('getId')->willReturnCallback(static fn (string $mime): int => $mime === 'video/webm' ? self::WEBM : self::TEXT);

		return new FileEventListener($this->queue, $this->storage, $mimeTypes, $this->logger);
	}

	private function file(int $id, int $storageId = 3, string $mime = 'video/webm', string $path = ''): File&MockObject {
		$mount = $this->createMock(IMountPoint::class);
		$mount->method('getNumericStorageId')->willReturn($storageId);
		$file = $this->createMock(File::class);
		$file->method('getId')->willReturn($id);
		$file->method('getMimetype')->willReturn($mime);
		$file->method('getInternalPath')->willReturn($path === '' ? 'files/f' . $id : $path);
		$file->method('getMountPoint')->willReturn($mount);

		return $file;
	}

	public function testCreatedWrittenAndTouchedMediaAreQueuedAsContent(): void {
		$listener = $this->listener();
		$listener->handle(new NodeCreatedEvent($this->file(10)));
		$listener->handle(new NodeWrittenEvent($this->file(11)));
		$listener->handle(new NodeTouchedEvent($this->file(12)));

		self::assertSame([
			[QueueMapper::KIND_CONTENT, 10, 3],
			[QueueMapper::KIND_CONTENT, 11, 3],
			[QueueMapper::KIND_CONTENT, 12, 3],
		], $this->queued);
	}

	public function testATextFileOrAFileOutsideTheMountSetIsNotQueued(): void {
		$listener = $this->listener();
		$listener->handle(new NodeCreatedEvent($this->file(10, 3, 'text/plain')));
		$listener->handle(new NodeWrittenEvent($this->file(11, 9)));
		$listener->handle(new NodeCreatedEvent($this->file(12, 3, 'video/webm', 'files_trashbin/files/x.webm.d1')));
		$listener->handle(new NodeCreatedEvent($this->createMock(Folder::class)));

		self::assertSame([], $this->queued);
	}

	public function testACopyQueuesItsTarget(): void {
		$this->listener()->handle(new NodeCopiedEvent($this->file(10), $this->file(20)));

		self::assertSame([[QueueMapper::KIND_CONTENT, 20, 3]], $this->queued);
	}

	public function testARenameInsideOneStorageIsMetadataOnly(): void {
		$this->listener()->handle(new NodeRenamedEvent($this->file(10), $this->file(10)));

		self::assertSame([[QueueMapper::KIND_METADATA, 10, 3]], $this->queued);
	}

	public function testAMoveAcrossStoragesIsContentForTheTargetAndDeleteForAnotherSourceId(): void {
		$this->listener()->handle(new NodeRenamedEvent($this->file(10, 3), $this->file(30, 4)));

		self::assertSame([
			[QueueMapper::KIND_CONTENT, 30, 4],
			[QueueMapper::KIND_DELETE, 10, 3],
		], $this->queued);
	}

	public function testAMoveAcrossStoragesThatKeepsTheFileIdQueuesNoDelete(): void {
		$this->listener()->handle(new NodeRenamedEvent($this->file(10, 3), $this->file(10, 4)));

		self::assertSame([[QueueMapper::KIND_CONTENT, 10, 4]], $this->queued);
	}

	public function testARenameAwayFromAMediaEndingTakesTheFileOut(): void {
		$this->listener()->handle(new NodeRenamedEvent($this->file(10), $this->file(10, 3, 'text/plain')));

		self::assertSame([[QueueMapper::KIND_DELETE, 10, 3]], $this->queued);
	}

	public function testADeletionIsADeleteWhateverTheTypeSaysNow(): void {
		$listener = $this->listener();
		$listener->handle(new NodeDeletedEvent($this->file(10, 3, 'text/plain')));
		$listener->handle(new NodeDeletedEvent($this->file(11, 9)));

		self::assertSame([[QueueMapper::KIND_DELETE, 10, 3]], $this->queued);
	}

	public function testAFailureIsSwallowedAndLoggedWithoutAPath(): void {
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('admissible')->willReturn(true);
		$this->queue->method('enqueue')->willThrowException(new \RuntimeException('/data/ana/files/secret.webm'));
		$this->logger->expects(self::once())->method('warning')->with(
			self::anything(),
			self::callback(static fn (array $context): bool => $context === ['class' => \RuntimeException::class]),
		);

		$this->listener()->handle(new NodeCreatedEvent($this->file(10)));
	}

	public function testANodeWithoutAUsableIdIsIgnored(): void {
		$broken = $this->createMock(File::class);
		$broken->method('getId')->willThrowException(new \OCP\Files\NotFoundException());

		$this->listener()->handle(new NodeRenamedEvent($this->createMock(Node::class), $broken));

		self::assertSame([], $this->queued);
	}

	public function testADeletedUserOnlyWritesTheSweepHint(): void {
		$config = $this->createMock(IAppConfig::class);
		$config->expects(self::once())->method('setValueInt')->with('audio_video_search', UserEventListener::SWEEP_HINT_KEY, 1234);
		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturn(1234);
		$this->queue->expects(self::never())->method('enqueue');

		(new UserEventListener($config, $time, $this->logger))->handle(new UserDeletedEvent($this->createMock(IUser::class)));
	}
}
