<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Controller\ReconcileController;
use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Db\StorageStateMapper;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Http;
use OCP\Files\Cache\ICacheEntry;
use OCP\Files\Cache\IFileAccess;
use OCP\Files\IMimeTypeLoader;
use OCP\IRequest;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The reconcile routes as the container sees them (plan 02-19, DISC-04).
 *
 * Storage 3 is a home (walk root 11), storage 7 an external SMB storage
 * (walk root 30, share key stored, capturable), storage 9 an external storage
 * that is not capturable. backend/tests/test_php_gates.py rule 16 holds that
 * requeue enqueues only after admissible; this suite holds the answers.
 */
#[CoversClass(ReconcileController::class)]
final class ReconcileControllerTest extends TestCase {
	private const WEBM = 5;
	private const TEXT = 6;

	private StorageService&MockObject $storage;
	private QueueService&MockObject $queue;
	private CrawlMapper&MockObject $crawls;
	private StorageStateMapper&MockObject $states;
	private IFileAccess&MockObject $fileAccess;
	private IMimeTypeLoader&MockObject $mimeTypes;
	/** @var list<array{string, int, int}> */
	private array $enqueued = [];

	protected function setUp(): void {
		parent::setUp();

		$this->enqueued = [];
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('getMounts')->willReturnCallback(static function (): \Generator {
			yield ['storage_id' => 3, 'root_id' => 10, 'overridden_root' => 11];
			yield ['storage_id' => 7, 'root_id' => 30, 'overridden_root' => 30];
			yield ['storage_id' => 9, 'root_id' => 40, 'overridden_root' => 40];
		});
		$this->storage->method('isExternal')->willReturnCallback(static fn (int $id): bool => $id !== 3);
		$this->storage->method('mountRoots')->willReturnCallback(static fn (int $id): array => match ($id) {
			3 => [['rootId' => 11, 'rootPath' => 'files']],
			7 => [['rootId' => 30, 'rootPath' => '']],
			default => [],
		});
		$this->storage->method('mountRelativePath')->willReturnCallback(
			static fn (int $id, string $path): ?string => $id === 3 && str_starts_with($path, 'files/') ? substr($path, 6) : null,
		);

		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('storageCapturable')->willReturnCallback(static fn (int $id): bool => $id !== 9);
		$this->queue->method('admissible')->willReturnCallback(
			static fn (int $storageId, int $mimeId, string $relative): bool => $mimeId === self::WEBM && !str_starts_with($relative, 'Privat/'),
		);
		$this->queue->method('enqueue')->willReturnCallback(function (string $kind, ?int $fileId, int $storageId): void {
			$this->enqueued[] = [$kind, (int)$fileId, $storageId];
		});

		$this->crawls = $this->createMock(CrawlMapper::class);
		$this->crawls->method('find')->willReturnCallback(static fn (int $storageId, int $rootId): ?array => match ([$storageId, $rootId]) {
			[3, 11] => ['storageId' => 3, 'rootId' => 11, 'lastFileId' => 90, 'generation' => 0, 'startedAt' => 1, 'finishedAt' => 2],
			[7, 30] => ['storageId' => 7, 'rootId' => 30, 'lastFileId' => 5, 'generation' => 0, 'startedAt' => 1, 'finishedAt' => null],
			default => null,
		});

		$this->states = $this->createMock(StorageStateMapper::class);
		$this->states->method('find')->willReturnCallback(static fn (int $id): ?array => $id === 7
			? ['storageId' => 7, 'mountId' => 1, 'provider' => 'smb', 'shareKeyHash' => str_repeat('a', 64), 'rootPrefix' => '', 'authKind' => 'password', 'capturable' => true, 'reason' => null, 'users' => 2, 'checkedAt' => 1]
			: null);

		$this->fileAccess = $this->createMock(IFileAccess::class);
		$this->fileAccess->method('getByFileId')->willReturnCallback(fn (int $fileId): ?ICacheEntry => match ($fileId) {
			41 => $this->entry(41, 3, 'files/Sitzung/a.webm', 'video/webm'),
			42 => $this->entry(42, 3, 'files/Privat/b.webm', 'video/webm'),
			43 => $this->entry(43, 3, 'files/notes.txt', 'text/plain'),
			44 => $this->entry(44, 3, 'files_trashbin/files/c.webm.d1', 'video/webm'),
			default => null,
		});
		$this->mimeTypes = $this->createMock(IMimeTypeLoader::class);
		$this->mimeTypes->method('exists')->willReturn(true);
		$this->mimeTypes->method('getId')->willReturnCallback(static fn (string $mime): int => $mime === 'video/webm' ? self::WEBM : self::TEXT);
	}

	private function entry(int $fileId, int $storageId, string $path, string $mime, string $etag = 'e1', int $size = 100, int $mtime = 1700): ICacheEntry&MockObject {
		$entry = $this->createMock(ICacheEntry::class);
		$entry->method('getId')->willReturn($fileId);
		$entry->method('getStorageId')->willReturn($storageId);
		$entry->method('getPath')->willReturn($path);
		$entry->method('getMimeType')->willReturn($mime);
		$entry->method('getEtag')->willReturn($etag);
		$entry->method('getSize')->willReturn($size);
		$entry->method('getStorageMTime')->willReturn($mtime);
		$entry->method('getMTime')->willReturn($mtime + 1);

		return $entry;
	}

	private function backendAppId(): string {
		$value = (new \ReflectionClass(Application::class))->getConstant('BACKEND_APP_ID');
		self::assertIsString($value);

		return $value;
	}

	private function controller(?string $callerAppId = null): ReconcileController {
		$caller = $callerAppId ?? $this->backendAppId();
		$request = $this->createMock(IRequest::class);
		$request->method('getHeader')->willReturnCallback(
			static fn (string $name): string => $name === 'EX-APP-ID' ? $caller : '',
		);

		return new ReconcileController(
			$request,
			$this->storage,
			$this->queue,
			$this->crawls,
			$this->states,
			$this->fileAccess,
			$this->mimeTypes,
			$this->createMock(LoggerInterface::class),
		);
	}

	// -- guard and bounds -----------------------------------------------------------

	public function testAForeignExAppIsRefusedOnEveryRoute(): void {
		$this->queue->expects(self::never())->method(self::anything());
		$this->storage->expects(self::never())->method(self::anything());
		$controller = $this->controller('some_other_exapp');

		self::assertSame(Http::STATUS_FORBIDDEN, $controller->mounts()->getStatus());
		self::assertSame(Http::STATUS_FORBIDDEN, $controller->slice('3', '11')->getStatus());
		self::assertSame(Http::STATUS_FORBIDDEN, $controller->classify([3])->getStatus());
		self::assertSame(Http::STATUS_FORBIDDEN, $controller->requeue([41])->getStatus());
		self::assertSame([], $this->enqueued);
	}

	/** @return array<string, array{mixed}> */
	public static function badLists(): array {
		return [
			'257 ids' => [range(1, 257)],
			'empty' => [[]],
			'not a list' => ['41'],
			'missing' => [null],
			'zero' => [[0]],
			'negative' => [[-3]],
			'text' => [['x']],
			'nested' => [[[41]]],
		];
	}

	#[DataProvider('badLists')]
	public function testAListOutsideOneTo256PositiveIdsIsA400(mixed $ids): void {
		$this->storage->expects(self::never())->method('classifyAbsent');
		$this->queue->expects(self::never())->method('enqueue');

		self::assertSame(Http::STATUS_BAD_REQUEST, $this->controller()->classify($ids)->getStatus());
		self::assertSame(Http::STATUS_BAD_REQUEST, $this->controller()->requeue($ids)->getStatus());
	}

	public function testExactly256IdsAreAccepted(): void {
		$this->storage->method('classifyAbsent')->willReturn(['gone' => [], 'deselected' => [], 'present' => []]);

		self::assertSame(Http::STATUS_OK, $this->controller()->classify(range(1, 256))->getStatus());
		self::assertSame(Http::STATUS_OK, $this->controller()->requeue(range(1, 256))->getStatus());
	}

	// -- mounts ------------------------------------------------------------------------

	public function testMountsCarryTheWalkRootAndTheFlagsOfEachMount(): void {
		$response = $this->controller()->mounts();

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame([
			'ok' => true,
			'mounts' => [
				['storageId' => 3, 'rootId' => 11, 'crawlFinished' => true, 'capturable' => true, 'external' => false, 'groupable' => false],
				['storageId' => 7, 'rootId' => 30, 'crawlFinished' => false, 'capturable' => true, 'external' => true, 'groupable' => true],
				['storageId' => 9, 'rootId' => 40, 'crawlFinished' => false, 'capturable' => false, 'external' => true, 'groupable' => false],
			],
		], $response->getData());
	}

	public function testAMountListThatCannotBeReadIsOkFalseWithoutAList(): void {
		$storage = $this->createMock(StorageService::class);
		$storage->method('getMounts')->willThrowException(new \RuntimeException('db gone /files/secret'));
		$this->storage = $storage;

		$response = $this->controller()->mounts();

		self::assertSame(['ok' => false, 'mounts' => []], $response->getData());
	}

	public function testAFlagThatCannotBeReadIsOkFalseToo(): void {
		$crawls = $this->createMock(CrawlMapper::class);
		$crawls->method('find')->willThrowException(new \RuntimeException('locked'));
		$this->crawls = $crawls;

		self::assertSame(['ok' => false, 'mounts' => []], $this->controller()->mounts()->getData());
	}

	// -- slice -------------------------------------------------------------------------

	public function testASliceCarriesIdEtagSizeAndMtimeOnlyAndTheNextCursor(): void {
		$this->storage->expects(self::once())->method('getFileSlice')->with(3, 11, 40, 2)->willReturn([
			$this->entry(41, 3, 'files/a.webm', 'video/webm', 'e41', 10, 100),
			$this->entry(45, 3, 'files/b.webm', 'video/webm', 'e45', 20, 200),
		]);

		$response = $this->controller()->slice('3', '11', '40', '2');

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame([
			'files' => [
				['fileId' => 41, 'etag' => 'e41', 'size' => 10, 'mtime' => 100],
				['fileId' => 45, 'etag' => 'e45', 'size' => 20, 'mtime' => 200],
			],
			'next' => 45,
		], $response->getData());
	}

	public function testAShortSliceIsTheLast(): void {
		$this->storage->expects(self::once())->method('getFileSlice')->with(7, 30, 0, 500)
			->willReturn([$this->entry(31, 7, 'a.webm', 'video/webm')]);

		self::assertSame(null, $this->controller()->slice('7', '30')->getData()['next']);
	}

	/** @return array<string, array{mixed, mixed, mixed, mixed}> */
	public static function badSlices(): array {
		return [
			'storage zero' => ['0', '11', '0', '10'],
			'storage text' => ['x', '11', '0', '10'],
			'root missing' => ['3', null, '0', '10'],
			'after negative' => ['3', '11', '-1', '10'],
			'limit zero' => ['3', '11', '0', '0'],
			'limit 1001' => ['3', '11', '0', '1001'],
			'limit not canonical' => ['3', '11', '0', '010'],
		];
	}

	#[DataProvider('badSlices')]
	public function testASliceOutsideItsBoundsIsA400(mixed $storage, mixed $root, mixed $after, mixed $limit): void {
		$this->storage->expects(self::never())->method('getFileSlice');

		self::assertSame(Http::STATUS_BAD_REQUEST, $this->controller()->slice($storage, $root, $after, $limit)->getStatus());
	}

	public function testALimitOf1000IsAccepted(): void {
		$this->storage->expects(self::once())->method('getFileSlice')->with(3, 11, 0, 1000)->willReturn([]);

		self::assertSame(['files' => [], 'next' => null], $this->controller()->slice('3', '11', '0', '1000')->getData());
	}

	public function testARootThatIsNoWalkRootOfTheStorageIsA404(): void {
		$this->storage->expects(self::never())->method('getFileSlice');

		// 10 is the root of the home storage, not its files folder; 30 belongs to storage 7.
		self::assertSame(Http::STATUS_NOT_FOUND, $this->controller()->slice('3', '10')->getStatus());
		self::assertSame(Http::STATUS_NOT_FOUND, $this->controller()->slice('3', '30')->getStatus());
		self::assertSame(Http::STATUS_NOT_FOUND, $this->controller()->slice('4', '11')->getStatus());
	}

	public function testASliceThatCannotBeReadIsA500WithoutDetail(): void {
		$this->storage->method('getFileSlice')->willThrowException(new \RuntimeException('files/secret.webm'));

		$response = $this->controller()->slice('3', '11');

		self::assertSame(Http::STATUS_INTERNAL_SERVER_ERROR, $response->getStatus());
		self::assertStringNotContainsString('secret', (string)json_encode($response->getData()));
	}

	// -- classify ----------------------------------------------------------------------

	public function testClassifyAnswersTheThreeListsAndAsksTheCapturability(): void {
		$this->storage->expects(self::once())->method('classifyAbsent')->willReturnCallback(
			static function (array $ids, \Closure $capturable): array {
				self::assertSame([3, 9, 12], $ids);
				self::assertTrue($capturable(3));
				self::assertFalse($capturable(9));

				return ['gone' => [12], 'deselected' => [9], 'present' => [3]];
			},
		);

		$response = $this->controller()->classify([3, 9, 12, 9]);

		self::assertSame(['gone' => [12], 'deselected' => [9], 'present' => [3]], $response->getData());
	}

	public function testAClassificationThatFailsIsA500AndNamesNoStorage(): void {
		$this->storage->method('classifyAbsent')->willThrowException(new \RuntimeException('smb::bob@host//share'));

		$response = $this->controller()->classify([3]);

		self::assertSame(Http::STATUS_INTERNAL_SERVER_ERROR, $response->getStatus());
		self::assertArrayNotHasKey('gone', $response->getData());
		self::assertStringNotContainsString('host', (string)json_encode($response->getData()));
	}

	// -- requeue -----------------------------------------------------------------------

	public function testAnAdmissibleFileIsQueuedAsContent(): void {
		$response = $this->controller()->requeue([41]);

		self::assertSame(['enqueued' => 1, 'rejected' => 0], $response->getData());
		self::assertSame([[QueueMapper::KIND_CONTENT, 41, 3]], $this->enqueued);
	}

	public function testAnExcludedFileIsRejectedAndNothingIsQueued(): void {
		$response = $this->controller()->requeue([42]);

		self::assertSame(['enqueued' => 0, 'rejected' => 1], $response->getData());
		self::assertSame([], $this->enqueued);
	}

	public function testUnknownFilesOtherTypesAndTheTrashBinAreRejected(): void {
		$response = $this->controller()->requeue([99, 43, 44]);

		self::assertSame(['enqueued' => 0, 'rejected' => 3], $response->getData());
		self::assertSame([], $this->enqueued);
	}

	public function testAMixedListCountsEachFileOnce(): void {
		$response = $this->controller()->requeue([41, 42, 41, 99]);

		self::assertSame(['enqueued' => 1, 'rejected' => 2], $response->getData());
		self::assertSame([[QueueMapper::KIND_CONTENT, 41, 3]], $this->enqueued);
	}

	public function testTheStorageOfTheCacheEntryWinsOverAnyClaimOfTheCaller(): void {
		$this->queue->expects(self::once())->method('admissible')->with(3, self::WEBM, 'Sitzung/a.webm');

		$this->controller()->requeue([41]);
	}

	public function testALookupThatFailsRejectsTheFile(): void {
		$fileAccess = $this->createMock(IFileAccess::class);
		$fileAccess->method('getByFileId')->willThrowException(new \RuntimeException('files/x.webm'));
		$this->fileAccess = $fileAccess;

		self::assertSame(['enqueued' => 0, 'rejected' => 1], $this->controller()->requeue([41])->getData());
		self::assertSame([], $this->enqueued);
	}

	public function testAWorkStockThatCannotBeWrittenIsA500(): void {
		$queue = $this->createMock(QueueService::class);
		$queue->method('admissible')->willReturn(true);
		$queue->method('enqueue')->willThrowException(new \RuntimeException('db'));
		$this->queue = $queue;

		self::assertSame(Http::STATUS_INTERNAL_SERVER_ERROR, $this->controller()->requeue([41])->getStatus());
	}
}
