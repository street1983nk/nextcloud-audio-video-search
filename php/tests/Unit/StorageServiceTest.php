<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Service\StorageService;
use OCP\Files\Cache\ICacheEntry;
use OCP\Files\Cache\IFileAccess;
use OCP\Files\IMimeTypeLoader;
use OCP\IDBConnection;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;

/**
 * The mount set, the media type filter and the one path space.
 *
 * The media type ids come from oc_mimetypes of the throwaway instance, so the
 * filter is the real query; mounts and slices are doubles of IFileAccess.
 */
#[CoversClass(StorageService::class)]
final class StorageServiceTest extends TestCase {
	private IFileAccess&MockObject $fileAccess;

	protected function setUp(): void {
		parent::setUp();

		$this->fileAccess = $this->createMock(IFileAccess::class);
	}

	private function service(?IDBConnection $db = null): StorageService {
		return new StorageService($this->fileAccess, $db ?? $this->createMock(IDBConnection::class));
	}

	private function entry(string $path): ICacheEntry&MockObject {
		$entry = $this->createMock(ICacheEntry::class);
		$entry->method('getPath')->willReturn($path);

		return $entry;
	}

	/**
	 * A home on storage 3 (walk root 11 = files), a team folder on storage 5
	 * (walk root 20) and an external storage on storage 7 (walk root 30).
	 */
	private function withMounts(): void {
		$this->fileAccess->method('getDistinctMounts')->willReturnCallback(static function (array $providers): \Generator {
			if ($providers !== [StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER]) {
				yield ['storage_id' => 3, 'root_id' => 10, 'overridden_root' => 11];
				yield ['storage_id' => 5, 'root_id' => 20, 'overridden_root' => 20];
			}
			yield ['storage_id' => 7, 'root_id' => 30, 'overridden_root' => 30];
		});
		$this->fileAccess->method('getByFileIdInStorage')->willReturnCallback(
			fn (int $fileId, int $storageId): ?ICacheEntry => match ([$fileId, $storageId]) {
				[11, 3] => $this->entry('files'),
				[20, 5], [30, 7] => $this->entry(''),
				default => null,
			},
		);
	}

	public function testTheMountSetIsHomesTeamFoldersAndExternalStoragesAbWerk(): void {
		$providers = $this->service()->providers();

		self::assertContains('OC\Files\Mount\LocalHomeMountProvider', $providers);
		self::assertContains('OC\Files\Mount\ObjectHomeMountProvider', $providers);
		self::assertContains('OCA\GroupFolders\Mount\MountProvider', $providers);
		self::assertContains('OCA\Files_External\Config\ConfigAdapter', $providers);
		self::assertSame('OCA\Files_External\Config\ConfigAdapter', StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER);
	}

	public function testOnlyTheStoragesOfFilesExternalAreExternal(): void {
		$this->withMounts();
		$service = $this->service();

		self::assertTrue($service->isExternal(7));
		self::assertFalse($service->isExternal(3));
		self::assertFalse($service->isExternal(5));
		self::assertFalse($service->isExternal(9));
		self::assertTrue($service->inMountSet(7));
		self::assertSame('Sitzung/a.webm', $service->mountRelativePath(7, 'Sitzung/a.webm'));
	}

	public function testGetMountsAsksForUserFilesMountsOfTheMountSet(): void {
		$service = $this->service();
		$this->fileAccess->expects(self::once())
			->method('getDistinctMounts')
			->with($service->providers(), true)
			->willReturnCallback(static function (): \Generator {
				yield from [];
			});

		self::assertSame([], iterator_to_array($service->getMounts()));
	}

	public function testThePathIsRelativeToTheWalkRootAndTrashIsOutside(): void {
		$this->withMounts();
		$service = $this->service();

		self::assertSame('Sitzungen/a.webm', $service->mountRelativePath(3, 'files/Sitzungen/a.webm'));
		self::assertNull($service->mountRelativePath(3, 'files_trashbin/files/a.webm.d1'));
		self::assertNull($service->mountRelativePath(3, 'filesX/a.webm'));
		self::assertSame('t.webm', $service->mountRelativePath(5, 't.webm'));
		self::assertNull($service->mountRelativePath(4, 'files/a.webm'));
		self::assertTrue($service->inMountSet(3));
		self::assertFalse($service->inMountSet(4));
	}

	public function testTheMediaTypeIdsAreAudioAndVideoOnlyCaseBlind(): void {
		$loader = \OCP\Server::get(IMimeTypeLoader::class);
		// getId writes a missing type, so the instance knows all four afterwards.
		$mpeg = $loader->getId('audio/mpeg');
		$mp4 = $loader->getId('video/mp4');
		$mts = $loader->getId('video/MP2T');
		$jpeg = $loader->getId('image/jpeg');

		$ids = $this->service(\OCP\Server::get(IDBConnection::class))->allowedMimeIds();

		self::assertContains($mpeg, $ids);
		self::assertContains($mp4, $ids);
		self::assertContains($mts, $ids);
		self::assertNotContains($jpeg, $ids);
	}

	public function testTheSliceAsksWithTheMediaTypesAndABoundedLimit(): void {
		$service = $this->getMockBuilder(StorageService::class)
			->setConstructorArgs([$this->fileAccess, $this->createMock(IDBConnection::class)])
			->onlyMethods(['allowedMimeIds'])
			->getMock();
		$service->method('allowedMimeIds')->willReturn([4, 9]);
		$first = $this->entry('files/a.webm');
		$this->fileAccess->expects(self::once())
			->method('getByAncestorInStorage')
			->with(3, 11, 40, StorageService::MAX_SLICE, [4, 9], false, true)
			->willReturnCallback(static function () use ($first): \Generator {
				yield $first;
			});

		self::assertSame([$first], $service->getFileSlice(3, 11, 40, 50_000));
	}

	public function testAStorageWithoutMediaRowsCountsZeroInTheRealFileCache(): void {
		// The instance has to know a media type, or the count never asks.
		\OCP\Server::get(IMimeTypeLoader::class)->getId('audio/mpeg');
		$service = $this->service(\OCP\Server::get(IDBConnection::class));

		self::assertNotSame([], $service->allowedMimeIds());
		self::assertSame(0, $service->mediaRows(2_000_000_000));
	}

	public function testNoMediaTypeMeansNoMediaRowsAndNoQuery(): void {
		$db = $this->createMock(IDBConnection::class);
		$db->expects(self::never())->method('getQueryBuilder');
		$service = $this->getMockBuilder(StorageService::class)
			->setConstructorArgs([$this->fileAccess, $db])
			->onlyMethods(['allowedMimeIds'])
			->getMock();
		$service->method('allowedMimeIds')->willReturn([]);

		self::assertSame(0, $service->mediaRows(7));
	}

	public function testNoMediaTypeMeansNoSliceAndNoQuery(): void {
		$service = $this->getMockBuilder(StorageService::class)
			->setConstructorArgs([$this->fileAccess, $this->createMock(IDBConnection::class)])
			->onlyMethods(['allowedMimeIds'])
			->getMock();
		$service->method('allowedMimeIds')->willReturn([]);
		$this->fileAccess->expects(self::never())->method('getByAncestorInStorage');

		self::assertSame([], $service->getFileSlice(3, 11, 0, 10));
	}
}
