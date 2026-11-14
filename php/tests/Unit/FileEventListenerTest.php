<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\BackgroundJobs\StorageCrawlJob;
use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Listener\CacheEventListener;
use OCA\AudioVideoSearch\Listener\FileEventListener;
use OCA\AudioVideoSearch\Listener\GroupEventListener;
use OCA\AudioVideoSearch\Listener\UserEventListener;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCA\Files_Trashbin\Events\MoveToTrashEvent;
use OCA\Files_Trashbin\Events\NodeRestoredEvent;
use OCP\AppFramework\Bootstrap\IRegistrationContext;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\IJobList;
use OCP\Files\Cache\CacheEntryInsertedEvent;
use OCP\Files\Cache\CacheEntryRemovedEvent;
use OCP\Files\Events\Node\NodeCopiedEvent;
use OCP\Files\Events\Node\NodeCreatedEvent;
use OCP\Files\Events\Node\NodeDeletedEvent;
use OCP\Files\Events\Node\NodeRenamedEvent;
use OCP\Files\Events\Node\NodeTouchedEvent;
use OCP\Files\Events\Node\NodeWrittenEvent;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IMimeTypeDetector;
use OCP\Files\IMimeTypeLoader;
use OCP\Files\Mount\IMountPoint;
use OCP\Files\Node;
use OCP\Files\Config\ICachedMountInfo;
use OCP\Files\Config\IUserMountCache;
use OCP\Files\Storage\IStorage;
use OCP\Group\Events\UserAddedEvent;
use OCP\Group\Events\UserRemovedEvent;
use OCP\IAppConfig;
use OCP\IGroup;
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
#[CoversClass(GroupEventListener::class)]
#[CoversClass(Application::class)]
#[CoversClass(UserEventListener::class)]
#[CoversClass(CacheEventListener::class)]
final class FileEventListenerTest extends TestCase {
	private const WEBM = 5;
	private const TEXT = 6;

	private QueueService&MockObject $queue;
	private StorageService&MockObject $storage;
	private LoggerInterface&MockObject $logger;
	/** @var list<array{0: string, 1: int, 2: int}> */
	private array $queued = [];
	/** @var list<array{0: string, 1: string}> kind and origin of every enqueue, in order */
	private array $origins = [];

	protected function setUp(): void {
		parent::setUp();

		$this->queued = [];
		$this->origins = [];
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('admissible')->willReturnCallback(
			static fn (int $storageId, int $mimeId, string $relative): bool => $mimeId === self::WEBM && in_array($storageId, [3, 4], true),
		);
		$this->queue->method('enqueue')->willReturnCallback(function (string $kind, ?int $fileId, int $storageId, string $origin = QueueMapper::ORIGIN_CRAWL): void {
			$this->queued[] = [$kind, (int)$fileId, $storageId];
			$this->origins[] = [$kind, $origin];
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

	/**
	 * A file of a team folder as the node API hands it out: the storage of the
	 * mount is a jail (groupfolders 21 puts one over the storage of every
	 * folder), so the internal path of the node is the path BELOW the jail,
	 * while the cache of the numeric storage, and so the walk root of the mount
	 * in oc_mounts, holds the path above it. Real server classes, so the
	 * difference between the two spaces is not made up here.
	 */
	private function jailedFile(int $id, int $storageId, string $jailRoot, string $pathBelowJail): File&MockObject {
		$jail = new \OC\Files\Storage\Wrapper\Jail([
			'storage' => new \OC\Files\Storage\Temporary([]),
			'root' => $jailRoot,
		]);
		$masked = new \OC\Files\Storage\Wrapper\PermissionsMask([
			'storage' => $jail,
			'mask' => \OCP\Constants::PERMISSION_ALL,
		]);
		$file = $this->file($id, $storageId, 'video/webm', $pathBelowJail);
		$file->method('getStorage')->willReturn($masked);

		return $file;
	}

	private function cacheListener(): CacheEventListener {
		$detector = $this->createMock(IMimeTypeDetector::class);
		$detector->method('detectPath')->willReturnCallback(static fn (string $path): string => str_ends_with($path, '.webm') ? 'video/webm' : 'text/plain');
		$mimeTypes = $this->createMock(IMimeTypeLoader::class);
		$mimeTypes->method('exists')->willReturn(true);
		$mimeTypes->method('getId')->willReturnCallback(static fn (string $mime): int => $mime === 'video/webm' ? self::WEBM : self::TEXT);

		return new CacheEventListener($this->queue, $this->storage, $detector, $mimeTypes, $this->logger);
	}

	/**
	 * The last job of a file id: the queue keeps one job per file id and the
	 * one queued last replaces the earlier one (QueueMapper REPLACES).
	 *
	 * @return array{0: string, 1: int, 2: int}|null
	 */
	private function lastJobOf(int $fileId): ?array {
		$last = null;
		foreach ($this->queued as $job) {
			if ($job[1] === $fileId) {
				$last = $job;
			}
		}

		return $last;
	}

	/**
	 * The move of run 43387183622 (move-cross): ana moves wandern.webm (file
	 * id 80) by WebDAV MOVE from her home (storage 3) into the team folder
	 * Team (storage 4, a jail with the root files over the storage of the
	 * folder). In the order of View::rename at stable33: the cache move first
	 * (Cache::moveFromCache: removed for the source storage, inserted for the
	 * target, both with the path in the cache of the numeric storage), then
	 * the post_rename hook that HookConnector turns into NodeRenamedEvent.
	 */
	public function testAMoveFromTheHomeIntoAGroupFolderKeepsTheReference(): void {
		$listener = $this->listener();
		$cache = $this->cacheListener();
		$storage = $this->createMock(IStorage::class);

		$cache->handle(new CacheEntryRemovedEvent($storage, 'files/wandern.webm', 80, 3));
		$cache->handle(new CacheEntryInsertedEvent($storage, 'files/wandern.webm', 80, 4));
		$listener->handle(new NodeRenamedEvent(
			$this->file(80, 3, 'video/webm', 'files/wandern.webm'),
			$this->jailedFile(80, 4, 'files', 'wandern.webm'),
		));

		self::assertSame([QueueMapper::KIND_CONTENT, 80, 4], $this->lastJobOf(80));
		self::assertSame([
			[QueueMapper::KIND_DELETE, 80, 3],
			[QueueMapper::KIND_CONTENT, 80, 4],
			[QueueMapper::KIND_CONTENT, 80, 4],
		], $this->queued);
	}

	public function testAMediumCreatedInAGroupFolderIsQueued(): void {
		$this->listener()->handle(new NodeCreatedEvent($this->jailedFile(90, 4, 'files', 'neu.webm')));

		self::assertSame([[QueueMapper::KIND_CONTENT, 90, 4]], $this->queued);
	}

	/**
	 * A team folder without a storage of its own: the jail sits on the root
	 * storage at __groupfolders/<id>, and so does the walk root of the mount.
	 */
	public function testAMediumWrittenInAGroupFolderOnTheRootStorageIsQueued(): void {
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('mountRelativePath')->willReturnCallback(
			static fn (int $storageId, string $path): ?string => str_starts_with($path, '__groupfolders/1/') ? substr($path, 17) : null,
		);

		$this->listener()->handle(new NodeWrittenEvent($this->jailedFile(91, 4, '__groupfolders/1', 'unter/neu.webm')));

		self::assertSame([[QueueMapper::KIND_CONTENT, 91, 4]], $this->queued);
	}

	/** Guard: a jailed target outside every walk root still leaves the work stock. */
	public function testAMoveIntoAJailedPathOutsideEveryWalkRootStillTakesTheFileOut(): void {
		$this->listener()->handle(new NodeRenamedEvent(
			$this->file(80, 3, 'video/webm', 'files/wandern.webm'),
			$this->jailedFile(80, 4, 'trash', 'wandern.webm.d1'),
		));

		self::assertSame([[QueueMapper::KIND_DELETE, 80, 4]], $this->queued);
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

	/**
	 * Every content row a file or cache event queues carries the origin
	 * event (D-03-05, plan 03-04), in every case of this suite.
	 */
	protected function assertPostConditions(): void {
		foreach ($this->origins as [$kind, $origin]) {
			if ($kind === QueueMapper::KIND_CONTENT) {
				self::assertSame(QueueMapper::ORIGIN_EVENT, $origin);
			}
		}
	}

	public function testContentFromAFileEventIsQueuedWithTheOriginEvent(): void {
		$listener = $this->listener();
		$listener->handle(new NodeCreatedEvent($this->file(10)));
		$listener->handle(new NodeRenamedEvent($this->file(11, 3), $this->file(31, 4)));

		self::assertSame([
			[QueueMapper::KIND_CONTENT, QueueMapper::ORIGIN_EVENT],
			[QueueMapper::KIND_CONTENT, QueueMapper::ORIGIN_EVENT],
		], array_values(array_filter($this->origins, static fn (array $o): bool => $o[0] === QueueMapper::KIND_CONTENT)));
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

	// -- trash bin (plan 02-18, D-02-09) ----------------------------------------------

	/**
	 * In the order of the trash bin at stable34: MoveToTrashEvent before the
	 * move, NodeDeletedEvent after it. The delete replaces the trash row in the
	 * queue (QueueMapper REPLACES); QueueService::describe sees the file id in
	 * the trash bin and hands it out as trash.
	 */
	public function testMovingToTheTrashBinQueuesTrashAndTheDeletionAfterIt(): void {
		$listener = $this->listener();
		$file = $this->file(10, 3, 'video/webm', 'files/a.webm');

		$listener->handle(new MoveToTrashEvent($file));
		$listener->handle(new NodeDeletedEvent($file));

		self::assertSame([
			[QueueMapper::KIND_TRASH, 10, 3],
			[QueueMapper::KIND_DELETE, 10, 3],
		], $this->queued);
	}

	/** Like a deletion: whatever the type says now, but only in the mount set and only files. */
	public function testTheTrashBinTakesFilesOfTheMountSetOnly(): void {
		$listener = $this->listener();
		$listener->handle(new MoveToTrashEvent($this->file(10, 3, 'text/plain')));
		$listener->handle(new MoveToTrashEvent($this->file(11, 9)));
		$listener->handle(new MoveToTrashEvent($this->createMock(Folder::class)));

		self::assertSame([[QueueMapper::KIND_TRASH, 10, 3]], $this->queued);
	}

	public function testRestoringFromTheTrashBinQueuesRestore(): void {
		$this->listener()->handle(new NodeRestoredEvent(
			$this->file(10, 3, 'video/webm', 'files_trashbin/files/a.webm.d1700000000'),
			$this->file(10, 3, 'video/webm', 'files/a.webm'),
		));

		self::assertSame([[QueueMapper::KIND_RESTORE, 10, 3]], $this->queued);
	}

	/** Restored to a place the work stock does not take (a rule, no walk root): it leaves. */
	public function testARestoredFileThatIsNotAdmissibleLeavesTheWorkStock(): void {
		$listener = $this->listener();
		$listener->handle(new NodeRestoredEvent($this->file(10), $this->file(10, 3, 'text/plain')));
		$listener->handle(new NodeRestoredEvent($this->file(11, 9), $this->file(11, 9)));

		self::assertSame([[QueueMapper::KIND_DELETE, 10, 3]], $this->queued);
	}

	/** Without files_trashbin there is only NodeDeletedEvent: a deletion. */
	public function testWithoutTheTrashBinADeletionStaysADeletion(): void {
		$this->listener()->handle(new NodeDeletedEvent($this->file(10)));

		self::assertSame([[QueueMapper::KIND_DELETE, 10, 3]], $this->queued);
	}

	/**
	 * The trash bin events are registered by their class name: files_trashbin
	 * registers its autoloader after this app (the coordinator goes through
	 * the apps in order), so a class_exists check inside register() would
	 * answer no on every instance and drop both events. A name that never
	 * matches an event costs nothing when the trash bin is disabled.
	 */
	public function testTheApplicationListensToTheTrashBinAndToGroupChanges(): void {
		$registered = [];
		$context = $this->createMock(IRegistrationContext::class);
		$context->method('registerEventListener')->willReturnCallback(function (string $event, string $listener) use (&$registered): void {
			$registered[$event][] = $listener;
		});

		(new Application())->register($context);

		self::assertSame([FileEventListener::class], $registered['OCA\Files_Trashbin\Events\MoveToTrashEvent'] ?? null);
		self::assertSame([FileEventListener::class], $registered['OCA\Files_Trashbin\Events\NodeRestoredEvent'] ?? null);
		self::assertSame([GroupEventListener::class], $registered[UserAddedEvent::class] ?? null);
		self::assertSame([GroupEventListener::class], $registered[UserRemovedEvent::class] ?? null);
		self::assertSame([FileEventListener::class], $registered[NodeDeletedEvent::class] ?? null);
	}

	// -- group changes (plan 02-18, T-02-66) ------------------------------------------

	/**
	 * ana's mounts: her home 4, her SMB storage 8 (her own login), the team
	 * folder 5, the shared external storage 9 and the share of eva's home 3.
	 * The group extern is excluded.
	 *
	 * @param list<string> $excludedUsers users excluded after the change
	 * @param list<int> $excludedStorages storages excluded as a whole after the change
	 * @param list<int> $crawled storages whose walk roots have a crawl row
	 * @return array{listener: GroupEventListener, resets: \ArrayObject<int, array{int, int}>, jobs: \ArrayObject<int, mixed>}
	 */
	private function groupListener(array $excludedUsers = [], array $excludedStorages = [], array $crawled = [3, 4, 5, 8, 9]): array {
		$exclusions = $this->createMock(ExclusionService::class);
		$exclusions->method('groupListed')->willReturnCallback(static fn (string $gid): bool => $gid === 'extern');
		$exclusions->method('isExcludedUser')->willReturnCallback(static fn (string $uid): bool => in_array($uid, $excludedUsers, true));
		$exclusions->method('isExcluded')->willReturnCallback(
			static fn (int $storageId, string $path): bool => $path === '' && in_array($storageId, $excludedStorages, true),
		);
		$owners = [3 => 'eva', 4 => 'ana', 5 => null, 8 => 'ana', 9 => null];
		$exclusions->method('storageOwner')->willReturnCallback(static fn (int $storageId): ?string => $owners[$storageId] ?? null);

		$mountCache = $this->createMock(IUserMountCache::class);
		$mountCache->method('getMountsForUser')->willReturnCallback(function (IUser $user): array {
			$mounts = [];
			foreach ($user->getUID() === 'ana' ? [4, 8, 5, 9, 3, 4] : [] as $storageId) {
				$info = $this->createMock(ICachedMountInfo::class);
				$info->method('getStorageId')->willReturn($storageId);
				$mounts[] = $info;
			}

			return $mounts;
		});
		$this->storage->method('mountRoots')->willReturnCallback(
			static fn (int $storageId): array => [['rootId' => $storageId * 10 + 1, 'rootPath' => 'files']],
		);

		$resets = new \ArrayObject();
		$jobs = new \ArrayObject();
		$crawls = $this->createMock(CrawlMapper::class);
		$crawls->method('find')->willReturnCallback(static fn (int $storageId, int $rootId): ?array => in_array($storageId, $crawled, true)
			? ['storageId' => $storageId, 'rootId' => $rootId, 'lastFileId' => 9, 'generation' => 0, 'startedAt' => 1, 'finishedAt' => 2]
			: null);
		$crawls->method('reset')->willReturnCallback(static function (int $storageId, int $rootId) use ($resets): void {
			$resets[] = [$storageId, $rootId];
		});
		$jobList = $this->createMock(IJobList::class);
		$jobList->method('has')->willReturn(false);
		$jobList->method('add')->willReturnCallback(static function (string $job, mixed $argument) use ($jobs): void {
			self::assertSame(StorageCrawlJob::class, $job);
			$jobs[] = $argument;
		});

		return [
			'listener' => new GroupEventListener($exclusions, $mountCache, $this->storage, $this->queue, $crawls, $jobList, $this->logger),
			'resets' => $resets,
			'jobs' => $jobs,
		];
	}

	private function groupEvent(string $class, string $gid, string $uid): UserAddedEvent|UserRemovedEvent {
		$group = $this->createMock(IGroup::class);
		$group->method('getGID')->willReturn($gid);
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn($uid);

		return $class === UserAddedEvent::class ? new UserAddedEvent($group, $user) : new UserRemovedEvent($group, $user);
	}

	/** D-02-08, D-02-11: joining an excluded group removes what belongs to the user, at once. */
	public function testJoiningAnExcludedGroupRemovesTheStoragesOfTheUser(): void {
		$group = $this->groupListener(['ana']);

		$group['listener']->handle($this->groupEvent(UserAddedEvent::class, 'extern', 'ana'));

		self::assertSame([
			[QueueMapper::KIND_EXCLUDE_STORAGE, 0, 4],
			[QueueMapper::KIND_EXCLUDE_STORAGE, 0, 8],
		], $this->queued);
		self::assertSame([], $group['resets']->getArrayCopy());
	}

	public function testJoiningAnotherGroupDoesNothing(): void {
		$group = $this->groupListener();

		$group['listener']->handle($this->groupEvent(UserAddedEvent::class, 'intern', 'ana'));
		$group['listener']->handle($this->groupEvent(UserRemovedEvent::class, 'intern', 'ana'));

		self::assertSame([], $this->queued);
		self::assertSame([], $group['resets']->getArrayCopy());
	}

	/** Leaving the excluded group: the crawl of the storages of the user starts over, nothing is removed. */
	public function testLeavingTheExcludedGroupCrawlsTheStoragesOfTheUserAgain(): void {
		$group = $this->groupListener();

		$group['listener']->handle($this->groupEvent(UserRemovedEvent::class, 'extern', 'ana'));

		self::assertSame([], $this->queued);
		self::assertSame([[4, 41], [8, 81]], $group['resets']->getArrayCopy());
		self::assertSame([StorageCrawlJob::argument(4, 41), StorageCrawlJob::argument(8, 81)], $group['jobs']->getArrayCopy());
	}

	public function testLeavingTheGroupWhileStillExcludedOtherwiseDoesNothing(): void {
		$group = $this->groupListener(['ana']);

		$group['listener']->handle($this->groupEvent(UserRemovedEvent::class, 'extern', 'ana'));

		self::assertSame([], $this->queued);
		self::assertSame([], $group['resets']->getArrayCopy());
	}

	/** A storage switched off as a whole stays off; a storage never crawled is started by the scheduler. */
	public function testLeavingTheGroupSkipsAStorageExcludedAsAWholeAndOneNeverCrawled(): void {
		$group = $this->groupListener([], [8], [3, 5, 8, 9]);

		$group['listener']->handle($this->groupEvent(UserRemovedEvent::class, 'extern', 'ana'));

		self::assertSame([], $group['resets']->getArrayCopy());
		self::assertSame([], $group['jobs']->getArrayCopy());
	}

	public function testAFailureInAGroupEventIsSwallowedAndLoggedWithoutAName(): void {
		$exclusions = $this->createMock(ExclusionService::class);
		$exclusions->method('groupListed')->willThrowException(new \RuntimeException('extern ana'));
		$this->logger->expects(self::once())->method('warning')->with(
			self::anything(),
			self::callback(static fn (array $context): bool => $context === ['class' => \RuntimeException::class]),
		);
		$listener = new GroupEventListener(
			$exclusions,
			$this->createMock(IUserMountCache::class),
			$this->storage,
			$this->queue,
			$this->createMock(CrawlMapper::class),
			$this->createMock(IJobList::class),
			$this->logger,
		);

		$listener->handle($this->groupEvent(UserAddedEvent::class, 'extern', 'ana'));

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
