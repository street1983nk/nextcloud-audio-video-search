<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\Files\Cache\ICacheEntry;
use OCP\Files\Cache\IFileAccess;
use OCP\Files\Config\ICachedMountInfo;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IMimeTypeLoader;
use OCP\Files\IRootFolder;
use OCP\IUser;
use OCP\IUserManager;
use OCP\IUserSession;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The one pre-check and the second check at the hand over.
 *
 * Everything is a double. The reader context is the real class on a stateful
 * session double, so the cases see that a member is asked as the active user.
 */
#[CoversClass(QueueService::class)]
final class QueueServiceTest extends TestCase {
	private const TOKEN = 'abcdefabcdefabcdefabcdefabcdefab';
	private const WEBM = 5;

	private QueueMapper&MockObject $mapper;
	private StorageService&MockObject $storage;
	private IFileAccess&MockObject $fileAccess;
	private IMimeTypeLoader&MockObject $mimeTypes;
	private \OCP\Files\Config\IUserMountCache&MockObject $mountCache;
	private IRootFolder&MockObject $rootFolder;
	private IUserSession&MockObject $session;
	private ?IUser $active = null;
	/** @var list<string> */
	private array $askedAs = [];

	protected function setUp(): void {
		parent::setUp();

		$this->active = null;
		$this->askedAs = [];
		$this->mapper = $this->createMock(QueueMapper::class);
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('allowedMimeIds')->willReturn([self::WEBM]);
		$this->storage->method('inMountSet')->willReturnCallback(static fn (int $storageId): bool => in_array($storageId, [3, 5], true));
		$this->storage->method('mountRelativePath')->willReturnCallback(
			static fn (int $storageId, string $path): ?string => str_starts_with($path, 'files/') ? substr($path, 6) : null,
		);
		$this->fileAccess = $this->createMock(IFileAccess::class);
		$this->mimeTypes = $this->createMock(IMimeTypeLoader::class);
		$this->mimeTypes->method('exists')->willReturn(true);
		$this->mimeTypes->method('getId')->willReturnCallback(static fn (string $mime): int => $mime === 'video/webm' ? self::WEBM : 9);
		$this->mountCache = $this->createMock(\OCP\Files\Config\IUserMountCache::class);
		$this->rootFolder = $this->createMock(IRootFolder::class);
		$this->session = $this->createMock(IUserSession::class);
		$this->session->method('getUser')->willReturnCallback(fn (): ?IUser => $this->active);
		$this->session->method('setVolatileActiveUser')->willReturnCallback(function (?IUser $user): void {
			$this->active = $user;
		});
	}

	private function user(string $uid): IUser&MockObject {
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn($uid);

		return $user;
	}

	private function service(): QueueService {
		$users = $this->createMock(IUserManager::class);
		$users->method('get')->willReturnCallback(fn (string $uid): IUser => $this->user($uid));

		return new QueueService(
			$this->mapper,
			$this->storage,
			$this->fileAccess,
			$this->mimeTypes,
			$this->mountCache,
			$this->rootFolder,
			new ReaderContext($this->session, $users),
			$this->createMock(LoggerInterface::class),
		);
	}

	private function entry(int $storageId, string $mime, string $path): ICacheEntry&MockObject {
		$entry = $this->createMock(ICacheEntry::class);
		$entry->method('getStorageId')->willReturn($storageId);
		$entry->method('getMimeType')->willReturn($mime);
		$entry->method('getPath')->willReturn($path);
		$entry->method('getEtag')->willReturn('etag-1');
		$entry->method('getSize')->willReturn(4096);
		$entry->method('getStorageMTime')->willReturn(1700000000);
		$entry->method('getMTime')->willReturn(1);

		return $entry;
	}

	/** @param list<array{string, string}> $mounts uid and mount provider per mount */
	private function mounts(array $mounts): void {
		$infos = [];
		foreach ($mounts as [$uid, $provider]) {
			$info = $this->createMock(ICachedMountInfo::class);
			$info->method('getUser')->willReturn($this->user($uid));
			$info->method('getMountProvider')->willReturn($provider);
			$infos[] = $info;
		}
		$this->mountCache->method('getMountsForStorageId')->willReturn($infos);
	}

	/** @param list<string> $readers members for whom the file is readable */
	private function folders(array $readers): void {
		$this->rootFolder->method('getUserFolder')->willReturnCallback(function (string $uid) use ($readers): Folder {
			$this->askedAs[] = $uid . ':' . ($this->active?->getUID() ?? '-');
			$file = $this->createMock(File::class);
			$file->method('isReadable')->willReturn(in_array($uid, $readers, true));
			$folder = $this->createMock(Folder::class);
			$folder->method('getFirstNodeById')->willReturn($file);

			return $folder;
		});
	}

	/** @return array{id: int, kind: string, fileId: ?int, storageId: int, attempts: int} */
	private function row(int $id, string $kind, ?int $fileId, int $storageId = 3): array {
		return ['id' => $id, 'kind' => $kind, 'fileId' => $fileId, 'storageId' => $storageId, 'attempts' => 1];
	}

	public function testAdmissibleIsFalseForATextFileAndForAStorageOutsideTheMountSet(): void {
		$service = $this->service();

		self::assertTrue($service->admissible(3, self::WEBM, 'a.webm'));
		self::assertFalse($service->admissible(3, 9, 'a.txt'));
		self::assertFalse($service->admissible(4, self::WEBM, 'a.webm'));
		self::assertFalse($service->admissible(3, self::WEBM, ''));
	}

	public function testDescribeGivesExactlyTheNineKeys(): void {
		$this->fileAccess->method('getByFileId')->with(42)->willReturn($this->entry(3, 'video/webm', 'files/a.webm'));
		$this->mounts([['ana', 'OC\Files\Mount\LocalHomeMountProvider']]);
		$this->mapper->expects(self::once())->method('drop')->with(self::TOKEN, [])->willReturn(0);

		$described = $this->service()->describe(self::TOKEN, [$this->row(7, QueueMapper::KIND_CONTENT, 42)]);

		self::assertSame(0, $described['dropped']);
		self::assertCount(1, $described['items']);
		$item = $described['items'][0];
		self::assertSame(QueueService::ITEM_KEYS, array_keys($item));
		self::assertSame(
			[
				'queueId' => 7,
				'kind' => 'content',
				'fileId' => 42,
				'storageId' => 3,
				'etag' => 'etag-1',
				'size' => 4096,
				'mtime' => 1700000000,
				'prefilterKey' => null,
				'readerUid' => 'ana',
			],
			$item,
		);
	}

	public function testDescribeDropsARowWhoseFileIsNoLongerAdmissible(): void {
		$this->fileAccess->method('getByFileId')->willReturnCallback(fn (int $fileId): ?ICacheEntry => match ($fileId) {
			42 => $this->entry(3, 'text/plain', 'files/a.txt'),
			43 => $this->entry(3, 'video/webm', 'files_trashbin/files/b.webm.d1'),
			44 => $this->entry(4, 'video/webm', 'files/c.webm'),
			default => null,
		});
		$this->mapper->expects(self::once())->method('drop')->with(self::TOKEN, [1, 2, 3, 4])->willReturn(4);

		$described = $this->service()->describe(self::TOKEN, [
			$this->row(1, QueueMapper::KIND_CONTENT, 42),
			$this->row(2, QueueMapper::KIND_CONTENT, 43),
			$this->row(3, QueueMapper::KIND_METADATA, 44, 4),
			$this->row(4, QueueMapper::KIND_RESTORE, 45),
		]);

		self::assertSame(['items' => [], 'dropped' => 4], $described);
	}

	public function testRemovalsAreHandedOutWithoutLookingTheFileUp(): void {
		$this->fileAccess->expects(self::never())->method('getByFileId');
		$this->mapper->method('drop')->willReturn(0);

		$described = $this->service()->describe(self::TOKEN, [
			$this->row(1, QueueMapper::KIND_EXCLUDE_STORAGE, null, 9),
			$this->row(2, QueueMapper::KIND_DELETE, 42),
			$this->row(3, QueueMapper::KIND_TRASH, 43),
		]);

		self::assertSame([1, 2, 3], array_column($described['items'], 'queueId'));
		foreach ($described['items'] as $item) {
			self::assertSame(QueueService::ITEM_KEYS, array_keys($item));
			self::assertNull($item['etag']);
			self::assertNull($item['readerUid']);
		}
	}

	public function testTheReaderOfAHomeIsItsOwner(): void {
		$this->mounts([['ana', 'OC\Files\Mount\LocalHomeMountProvider']]);
		$this->rootFolder->expects(self::never())->method('getUserFolder');

		self::assertSame('ana', $this->service()->readerUid(3, 42));
	}

	public function testTheReaderOfATeamFolderIsTheFirstMemberWhoMayReadAskedAsThatMember(): void {
		$team = 'OCA\GroupFolders\Mount\MountProvider';
		$this->mounts([['ben', $team], ['ben', $team], ['cem', $team], ['dan', $team]]);
		$this->folders(['cem', 'dan']);

		self::assertSame('cem', $this->service()->readerUid(5, 42));
		self::assertSame(['ben:ben', 'cem:cem'], $this->askedAs);
		self::assertNull($this->active);
	}

	public function testATeamFolderAsksAtMostFiveMembersThenGivesUp(): void {
		$team = 'OCA\GroupFolders\Mount\MountProvider';
		$this->mounts(array_map(static fn (string $uid): array => [$uid, $team], ['u1', 'u2', 'u3', 'u4', 'u5', 'u6', 'u7']));
		$this->folders(['u6', 'u7']);

		self::assertNull($this->service()->readerUid(5, 42));
		self::assertCount(QueueService::MAX_READER_TRIES, $this->askedAs);
	}

	public function testStatsSayNotOkWhenTheTableCannotBeRead(): void {
		$this->mapper->method('openByKind')->willThrowException(new \RuntimeException('database gone'));

		$stats = $this->service()->stats();

		self::assertFalse($stats['ok']);
		self::assertSame(QueueMapper::KINDS, array_keys($stats['open']));
	}

	public function testStatsCarryTheOpenRowsPerKind(): void {
		$open = array_fill_keys(QueueMapper::KINDS, 0);
		$open[QueueMapper::KIND_CONTENT] = 3;
		$this->mapper->method('openByKind')->willReturn($open);

		self::assertSame(['ok' => true, 'open' => $open], $this->service()->stats());
	}
}
