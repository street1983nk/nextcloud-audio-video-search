<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\BackgroundJobs\ExternalRescanJob;
use OCA\AudioVideoSearch\Command\RescanCommand;
use OCA\AudioVideoSearch\Db\StorageStateMapper;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCA\AudioVideoSearch\Service\RescanService;
use OCA\AudioVideoSearch\Service\StorageClassifier;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\Files\Cache\IScanner;
use OCP\Files\Config\ICachedMountInfo;
use OCP\Files\Config\IUserMountCache;
use OCP\Files\Storage\IStorage;
use OCP\IConfig;
use OCP\IUser;
use OCP\IUserManager;
use OCP\IUserSession;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\ArrayInput;
use Symfony\Component\Console\Output\BufferedOutput;

/**
 * The rescan of external storages (DISC-04, 02-RESEARCH.md Befund 5): which
 * storages are due and in which order, the time budget, the reader, and that
 * a storage which may not be captured is never scanned. Below that the timed
 * job and occ audio_video_search:rescan, both against a double of the service.
 *
 * Everything is a double. The scanner is a small stand-in that plays a list
 * of hook calls the way the scanner of Nextcloud raises them during a walk,
 * and moves the clock between them.
 */
#[CoversClass(RescanService::class)]
#[CoversClass(ExternalRescanJob::class)]
#[CoversClass(RescanCommand::class)]
final class RescanServiceTest extends TestCase {
	private const NOW = 2_000_000;
	private const MOUNT = 2;
	private const SHARE_A = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
	private const SHARE_B = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';

	private int $now = self::NOW;
	private bool $noBackgroundScan = false;
	private ?IUser $active = null;
	/** @var list<array{storageId: int, shareKeyHash: ?string, rescannedAt: ?int}> */
	private array $candidates = [];
	/** @var array<int, array{storageId: int, mountId: ?int, provider: string, shareKeyHash: ?string, rootPrefix: ?string, authKind: ?string, capturable: bool, reason: ?string, users: int, checkedAt: ?int}> */
	private array $rows = [];
	/** @var list<int> */
	private array $external = [];
	/** @var array<int, int> */
	private array $mediaRows = [];
	/** @var list<int> storages whose media rows cannot be counted */
	private array $uncountable = [];
	/** @var array<int, list<ICachedMountInfo>> */
	private array $mountInfos = [];
	/** @var array<int, IStorage> what the probe hands out, by storage id */
	private array $storages = [];
	/** @var list<string> users for whom the probe finds no usable storage */
	private array $unusable = [];
	/** @var list<array{int, int}> storage id and time of every markRescanned */
	private array $marked = [];
	/** @var list<array{string, string}> the active user and the user of the mount, per probe */
	private array $probedAs = [];
	/** @var list<int> */
	private array $askedMounts = [];
	/** @var list<array{string, string, array<string, mixed>}> level, message and context of every log line */
	private array $logged = [];

	protected function setUp(): void {
		parent::setUp();

		$this->now = self::NOW;
		$this->noBackgroundScan = false;
		$this->active = null;
		$this->candidates = [];
		$this->rows = [];
		$this->external = [];
		$this->mediaRows = [];
		$this->uncountable = [];
		$this->mountInfos = [];
		$this->storages = [];
		$this->unusable = [];
		$this->marked = [];
		$this->probedAs = [];
		$this->askedMounts = [];
		$this->logged = [];
	}

	private function user(string $uid): IUser&MockObject {
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn($uid);

		return $user;
	}

	private function logger(): LoggerInterface&MockObject {
		$logger = $this->createMock(LoggerInterface::class);
		foreach (['debug', 'info', 'warning', 'error'] as $level) {
			$logger->method($level)->willReturnCallback(function (string|\Stringable $message, array $context = []) use ($level): void {
				$this->logged[] = [$level, (string)$message, $context];
			});
		}

		return $logger;
	}

	private function service(): RescanService {
		$states = $this->createMock(StorageStateMapper::class);
		$states->method('rescanCandidates')->willReturnCallback(fn (): array => $this->candidates);
		$states->method('find')->willReturnCallback(fn (int $storageId): ?array => $this->rows[$storageId] ?? null);
		$states->method('markRescanned')->willReturnCallback(function (int $storageId, int $at): void {
			$this->marked[] = [$storageId, $at];
		});

		$storageService = $this->createMock(StorageService::class);
		$storageService->method('isExternal')->willReturnCallback(fn (int $storageId): bool => in_array($storageId, $this->external, true));
		$storageService->method('mediaRows')->willReturnCallback(function (int $storageId): int {
			if (in_array($storageId, $this->uncountable, true)) {
				throw new \RuntimeException('filecache of smb::ana@nas.local//Medien// is gone');
			}

			return $this->mediaRows[$storageId] ?? 0;
		});

		$classifier = $this->createMock(StorageClassifier::class);
		$classifier->method('probe')->willReturnCallback(function (ICachedMountInfo $info, int $storageId): ?IStorage {
			$uid = $info->getUser()->getUID();
			$this->probedAs[] = [$this->active?->getUID() ?? '-', $uid];

			return in_array($uid, $this->unusable, true) ? null : ($this->storages[$storageId] ?? null);
		});

		$mountCache = $this->createMock(IUserMountCache::class);
		$mountCache->method('getMountsForStorageId')->willReturnCallback(function (int $storageId): array {
			$this->askedMounts[] = $storageId;

			return $this->mountInfos[$storageId] ?? [];
		});

		$session = $this->createMock(IUserSession::class);
		$session->method('getUser')->willReturnCallback(fn (): ?IUser => $this->active);
		$session->method('setVolatileActiveUser')->willReturnCallback(function (?IUser $user): void {
			$this->active = $user;
		});
		$users = $this->createMock(IUserManager::class);
		$users->method('get')->willReturnCallback(fn (string $uid): IUser => $this->user($uid));

		$config = $this->createMock(IConfig::class);
		$config->method('getSystemValueBool')->willReturnCallback(
			fn (string $key, bool $default = false): bool => $key === 'files_no_background_scan' ? $this->noBackgroundScan : $default,
		);

		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturnCallback(fn (): int => $this->now);

		return new RescanService(
			$states,
			$storageService,
			$classifier,
			$mountCache,
			new ReaderContext($session, $users),
			$config,
			$time,
			$this->logger(),
		);
	}

	/** A storage for the list of candidates: capturable, external, with this last rescan. */
	private function candidate(int $storageId, ?int $rescannedAt = null, ?string $shareKeyHash = null, bool $external = true): void {
		$this->candidates[] = ['storageId' => $storageId, 'shareKeyHash' => $shareKeyHash, 'rescannedAt' => $rescannedAt];
		$this->classified($storageId);
		if ($external) {
			$this->external[] = $storageId;
		}
	}

	/** The row of avs_storage for one storage. */
	private function classified(int $storageId, bool $capturable = true, ?int $mountId = self::MOUNT): void {
		$this->rows[$storageId] = [
			'storageId' => $storageId,
			'mountId' => $mountId,
			'provider' => StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER,
			'shareKeyHash' => null,
			'rootPrefix' => null,
			'authKind' => 'password::logincredentials',
			'capturable' => $capturable,
			'reason' => $capturable ? null : StorageClassifier::REASON_CREDENTIALS_MISSING,
			'users' => 1,
			'checkedAt' => self::NOW - 60,
		];
	}

	/** @param list<array{0: string, 1: int, 2?: string}> $mounts uid, mount id and provider per row of oc_mounts */
	private function mounts(int $storageId, array $mounts): void {
		$infos = [];
		foreach ($mounts as $mount) {
			$info = $this->createMock(ICachedMountInfo::class);
			$info->method('getUser')->willReturn($this->user($mount[0]));
			$info->method('getMountId')->willReturn($mount[1]);
			$info->method('getMountProvider')->willReturn($mount[2] ?? StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER);
			$info->method('getStorageId')->willReturn($storageId);
			$infos[] = $info;
		}
		$this->mountInfos[$storageId] = $infos;
	}

	/** The probe of this storage hands out a storage with this scanner. */
	private function scannedBy(int $storageId, IScanner $scanner): void {
		$storage = $this->createMock(IStorage::class);
		$storage->method('getScanner')->willReturn($scanner);
		$this->storages[$storageId] = $storage;
	}

	/** A capturable external storage 7 of ana with this scanner. */
	private function storageSeven(IScanner $scanner): void {
		$this->candidate(7);
		$this->mounts(7, [['ana', self::MOUNT]]);
		$this->scannedBy(7, $scanner);
	}

	/**
	 * A scanner with the hooks of the scanner of Nextcloud. scan() plays
	 * $steps: the hook, its arguments and the seconds that pass after it.
	 *
	 * @param list<array{string, list<mixed>, int}> $steps
	 */
	private function hookedScanner(array $steps = [], bool $rootFound = true, ?\Throwable $error = null): IScanner {
		$advance = function (int $seconds): void {
			$this->now += $seconds;
		};

		return new class($steps, $rootFound, $error, $advance) implements IScanner {
			/** @var list<list<mixed>> */
			public array $calls = [];
			/** @var array<string, list<callable>> */
			public array $listeners = [];

			/** @param list<array{string, list<mixed>, int}> $steps */
			public function __construct(
				private array $steps,
				private bool $rootFound,
				private ?\Throwable $error,
				private \Closure $advance,
			) {
			}

			public function listen($scope, $method, callable $callback) {
				$this->listeners[$scope . '::' . $method][] = $callback;
			}

			public function removeListener($scope = null, $method = null, ?callable $callback = null) {
				$hook = $scope . '::' . $method;
				$this->listeners[$hook] = array_values(array_filter(
					$this->listeners[$hook] ?? [],
					static fn (callable $kept): bool => $kept !== $callback,
				));
			}

			public function scanFile($file, $reuseExisting = 0, $parentId = -1, $cacheData = null, $lock = true) {
				return null;
			}

			public function scan($path, $recursive = self::SCAN_RECURSIVE, $reuse = -1, $lock = true) {
				$this->calls[] = ['scan', $path, $recursive, $reuse];
				foreach ($this->steps as [$hook, $arguments, $seconds]) {
					foreach ($this->listeners['\OC\Files\Cache\Scanner::' . $hook] ?? [] as $callback) {
						$callback(...$arguments);
					}
					($this->advance)($seconds);
				}
				if ($this->error !== null) {
					throw $this->error;
				}

				return $this->rootFound ? ['fileid' => 1] : null;
			}

			public static function isPartialFile($file) {
				return false;
			}

			public function backgroundScan() {
				$this->calls[] = ['backgroundScan'];
			}
		};
	}

	/** A scanner that offers no hooks at all. */
	private function plainScanner(): IScanner {
		return new class() implements IScanner {
			/** @var list<list<mixed>> */
			public array $calls = [];

			public function scanFile($file, $reuseExisting = 0, $parentId = -1, $cacheData = null, $lock = true) {
				return null;
			}

			public function scan($path, $recursive = self::SCAN_RECURSIVE, $reuse = -1, $lock = true) {
				$this->calls[] = ['scan', $path, $recursive, $reuse];

				return ['fileid' => 1];
			}

			public static function isPartialFile($file) {
				return false;
			}

			public function backgroundScan() {
				$this->calls[] = ['backgroundScan'];
			}
		};
	}

	/** @return list<mixed> the arguments of the hook addToCache: path, storage, data, file id */
	private static function written(int $fileId = -1): array {
		return ['Sitzung/a.webm', 'smb::ana@nas.local//Medien//', ['size' => 5], $fileId];
	}

	/** @return list<mixed> the arguments of the folder hooks: path, storage */
	private static function folder(string $path = ''): array {
		return [$path, 'smb::ana@nas.local//Medien//'];
	}

	// -- due and order ----------------------------------------------------------------

	public function testDueIsNeverRescannedOrADayAgoAndOnlyExternalStorages(): void {
		$this->candidate(4);
		$this->candidate(5, self::NOW - RescanService::RESCAN_SECONDS);
		$this->candidate(6, self::NOW - RescanService::RESCAN_SECONDS + 1);
		$this->candidate(8, null, null, false);
		$service = $this->service();

		self::assertSame([4, 5], $service->due());
		self::assertSame([4, 5, 6], $service->all());
	}

	public function testStoragesOfOneShareFollowEachOtherTheOneWithTheMostMediaRowsFirst(): void {
		$this->candidate(4, null, self::SHARE_A);
		$this->candidate(5, null, self::SHARE_B);
		$this->candidate(6, null, self::SHARE_A);
		$this->candidate(7);
		$this->mediaRows = [4 => 2, 5 => 50, 6 => 9, 7 => 1];

		self::assertSame([6, 4, 5, 7], $this->service()->due());
	}

	public function testTheShareThatWaitedLongestComesFirstAndEqualMembersGoByStorageId(): void {
		$this->candidate(4, self::NOW - 90_000, self::SHARE_A);
		$this->candidate(5, self::NOW - 200_000, self::SHARE_B);
		$this->candidate(6, self::NOW - 100_000, self::SHARE_A);

		self::assertSame([5, 4, 6], $this->service()->due());
	}

	public function testMediaRowsThatCannotBeCountedCostTheOrderOnlyAndNoHostIsLogged(): void {
		$this->candidate(4, null, self::SHARE_A);
		$this->candidate(6, null, self::SHARE_A);
		$this->mediaRows = [6 => 9];
		$this->uncountable = [6];

		self::assertSame([4, 6], $this->service()->due());
		self::assertCount(1, $this->logged);
		self::assertSame(['storage_id' => 6, 'class' => \RuntimeException::class], $this->logged[0][2]);
	}

	// -- one storage --------------------------------------------------------------------

	public function testRescanWalksTheWholeStorageAsItsUserAndNotesTheEndOfTheWalk(): void {
		$scanner = $this->hookedScanner([
			['scanFolder', self::folder(), 3],
			['addToCache', self::written(), 0],
			['addToCache', self::written(12), 0],
			['addToCache', self::written(), 0],
			['postScanFolder', self::folder(), 4],
		]);
		$this->storageSeven($scanner);
		$service = $this->service();

		$result = $service->rescan(7, $service->deadline());

		self::assertSame(['storageId' => 7, 'status' => RescanService::STATUS_SCANNED, 'seconds' => 7, 'new' => 2, 'changed' => 1], $result);
		self::assertSame(
			[['backgroundScan'], ['scan', '', IScanner::SCAN_RECURSIVE, IScanner::REUSE_ETAG | IScanner::REUSE_SIZE]],
			$scanner->calls,
		);
		self::assertSame([[7, self::NOW + 7]], $this->marked);
		self::assertSame([['ana', 'ana']], $this->probedAs);
		self::assertNull($this->active);
		self::assertSame([], array_filter($scanner->listeners));
	}

	public function testTheLogLineOfARescanCarriesIdStatusDurationAndCountsOnly(): void {
		$this->storageSeven($this->hookedScanner([['addToCache', self::written(), 2]]));
		$service = $this->service();

		$service->rescan(7, $service->deadline());

		self::assertSame(
			[['info', 'Audio & Video Search: rescan of an external storage', ['storage_id' => 7, 'status' => 'scanned', 'seconds' => 2, 'new' => 1, 'changed' => 0]]],
			$this->logged,
		);
	}

	public function testAWalkThatRunsIntoTheDeadlineStopsAtTheNextFolderAndNotesNothing(): void {
		$scanner = $this->hookedScanner([
			['scanFolder', self::folder(), 200],
			['addToCache', self::written(), 0],
			['postScanFolder', self::folder(), 200],
			['scanFolder', self::folder('Sitzung'), 0],
			['addToCache', self::written(), 0],
		]);
		$this->storageSeven($scanner);
		$service = $this->service();

		$result = $service->rescan(7, $service->deadline());

		self::assertSame(['storageId' => 7, 'status' => RescanService::STATUS_PARTIAL, 'seconds' => 400, 'new' => 1, 'changed' => 0], $result);
		self::assertSame([], $this->marked);
		self::assertNull($this->active);
		self::assertSame([], array_filter($scanner->listeners));
	}

	public function testAWalkThatEndsExactlyOnTheDeadlineIsStillComplete(): void {
		$this->storageSeven($this->hookedScanner([
			['scanFolder', self::folder(), 0],
			['postScanFolder', self::folder(), RescanService::BUDGET_SECONDS],
		]));
		$service = $this->service();

		$result = $service->rescan(7, $service->deadline());

		self::assertSame(RescanService::STATUS_SCANNED, $result['status']);
		self::assertSame([[7, self::NOW + RescanService::BUDGET_SECONDS]], $this->marked);
	}

	public function testARescanAfterTheDeadlineStartsNothing(): void {
		$scanner = $this->hookedScanner();
		$this->storageSeven($scanner);

		$result = $this->service()->rescan(7, self::NOW);

		self::assertSame(['storageId' => 7, 'status' => RescanService::STATUS_PARTIAL, 'seconds' => 0, 'new' => 0, 'changed' => 0], $result);
		self::assertSame([], $scanner->calls);
		self::assertSame([], $this->probedAs);
		self::assertSame([], $this->marked);
	}

	/** @return array<string, array{int, bool, bool, bool}> storage id, has a row, capturable, external */
	public static function notCapturable(): array {
		return [
			'no row in avs_storage' => [7, false, false, true],
			'the row says not capturable' => [7, true, false, true],
			'not an external storage of the mount set' => [7, true, true, false],
			'no storage id' => [0, true, true, true],
			'a negative storage id' => [-7, true, true, true],
		];
	}

	#[DataProvider('notCapturable')]
	public function testAStorageThatMayNotBeCapturedIsNeverScanned(int $storageId, bool $row, bool $capturable, bool $external): void {
		$scanner = $this->hookedScanner();
		if ($row) {
			$this->classified($storageId, $capturable);
		}
		if ($external) {
			$this->external[] = $storageId;
		}
		$this->mounts($storageId, [['ana', self::MOUNT]]);
		$this->scannedBy($storageId, $scanner);
		$service = $this->service();

		$result = $service->rescan($storageId, $service->deadline());

		self::assertSame(['storageId' => $storageId, 'status' => RescanService::STATUS_NOT_CAPTURABLE, 'seconds' => 0, 'new' => 0, 'changed' => 0], $result);
		self::assertSame([], $scanner->calls);
		self::assertSame([], $this->probedAs);
		self::assertSame([], $this->askedMounts);
		self::assertSame([], $this->marked);
		self::assertSame([], $this->logged);
	}

	public function testTheFirstUserWithAUsableStorageIsTheReader(): void {
		$scanner = $this->hookedScanner();
		$this->candidate(7);
		$this->mounts(7, [['cem', self::MOUNT], ['ben', self::MOUNT], ['cem', self::MOUNT]]);
		$this->scannedBy(7, $scanner);
		$this->unusable = ['ben'];
		$service = $this->service();

		$result = $service->rescan(7, $service->deadline());

		self::assertSame(RescanService::STATUS_SCANNED, $result['status']);
		self::assertSame([['ben', 'ben'], ['cem', 'cem']], $this->probedAs);
		self::assertCount(2, $scanner->calls);
	}

	public function testWithoutAUsableStorageTheRescanFailsAfterFiveUsers(): void {
		$scanner = $this->hookedScanner();
		$this->candidate(7);
		$this->mounts(7, array_map(static fn (string $uid): array => [$uid, self::MOUNT], ['g', 'f', 'e', 'd', 'c', 'b', 'a']));
		$this->scannedBy(7, $scanner);
		$this->unusable = ['a', 'b', 'c', 'd', 'e', 'f', 'g'];
		$service = $this->service();

		$result = $service->rescan(7, $service->deadline());

		self::assertSame(RescanService::STATUS_FAILED, $result['status']);
		self::assertSame(['a', 'b', 'c', 'd', 'e'], array_column($this->probedAs, 1));
		self::assertSame(RescanService::MAX_READER_TRIES, count($this->probedAs));
		self::assertSame([], $scanner->calls);
		self::assertSame([], $this->marked);
	}

	public function testOnlyUsersOfTheClassifiedConfigurationOfFilesExternalAreTried(): void {
		$this->candidate(7);
		$this->mounts(7, [
			['ana', 3],
			['cem', self::MOUNT, 'OCA\GroupFolders\Mount\MountProvider'],
			['', self::MOUNT],
			['ben', self::MOUNT],
		]);
		$this->scannedBy(7, $this->hookedScanner());
		$service = $this->service();

		$service->rescan(7, $service->deadline());

		self::assertSame([['ben', 'ben']], $this->probedAs);
	}

	public function testAStorageWithoutAnyReaderFails(): void {
		$this->candidate(7);
		$service = $this->service();

		$result = $service->rescan(7, $service->deadline());

		self::assertSame(RescanService::STATUS_FAILED, $result['status']);
		self::assertSame([], $this->probedAs);
		self::assertSame([], $this->marked);
	}

	public function testAScannerThatThrowsIsAFailureAndNoHostOrFileNameIsLogged(): void {
		$scanner = $this->hookedScanner(
			[['addToCache', self::written(), 5]],
			true,
			new \RuntimeException('smb://ana:secret@nas.local/Medien/Sitzung/a.webm timed out'),
		);
		$this->storageSeven($scanner);
		$service = $this->service();

		$result = $service->rescan(7, $service->deadline());

		self::assertSame(['storageId' => 7, 'status' => RescanService::STATUS_FAILED, 'seconds' => 5, 'new' => 1, 'changed' => 0], $result);
		self::assertSame([], $this->marked);
		self::assertNull($this->active);
		self::assertSame([], array_filter($scanner->listeners));
		self::assertCount(2, $this->logged);
		$lines = (string)json_encode($this->logged);
		self::assertStringNotContainsString('nas.local', $lines);
		self::assertStringNotContainsString('a.webm', $lines);
		self::assertStringNotContainsString('secret', $lines);
		// A scan that began is not repeated as another user.
		self::assertCount(1, $this->probedAs);
	}

	public function testAScannerThatFindsNoRootIsAFailure(): void {
		$this->storageSeven($this->hookedScanner([], false));
		$service = $this->service();

		$result = $service->rescan(7, $service->deadline());

		self::assertSame(RescanService::STATUS_FAILED, $result['status']);
		self::assertSame([], $this->marked);
	}

	public function testAScannerWithoutHooksIsWalkedToTheEndAndCountsNothing(): void {
		$scanner = $this->plainScanner();
		$this->storageSeven($scanner);
		$service = $this->service();

		$result = $service->rescan(7, $service->deadline());

		self::assertSame(['storageId' => 7, 'status' => RescanService::STATUS_SCANNED, 'seconds' => 0, 'new' => 0, 'changed' => 0], $result);
		self::assertSame(
			[['backgroundScan'], ['scan', '', IScanner::SCAN_RECURSIVE, IScanner::REUSE_ETAG | IScanner::REUSE_SIZE]],
			$scanner->calls,
		);
		self::assertSame([[7, self::NOW]], $this->marked);
	}

	// -- one run ------------------------------------------------------------------------

	public function testOnceTheBudgetIsSpentNoFurtherStorageIsStarted(): void {
		$this->candidate(4);
		$this->candidate(5);
		$this->candidate(6);
		$first = $this->hookedScanner([
			['scanFolder', self::folder(), 0],
			['postScanFolder', self::folder(), RescanService::BUDGET_SECONDS],
		]);
		$later = $this->hookedScanner();
		foreach ([4, 5, 6] as $storageId) {
			$this->mounts($storageId, [['ana', self::MOUNT]]);
			$this->scannedBy($storageId, $storageId === 4 ? $first : $later);
		}

		$run = $this->service()->run();

		self::assertSame([4], array_column($run['results'], 'storageId'));
		self::assertSame(RescanService::STATUS_SCANNED, $run['results'][0]['status']);
		self::assertSame(2, $run['waiting']);
		self::assertSame([], $later->calls);
		self::assertSame([[4, self::NOW + RescanService::BUDGET_SECONDS]], $this->marked);
	}

	public function testARunTakesTheDueStoragesAndWithoutTheCadenceEveryCapturableOne(): void {
		$this->candidate(4, self::NOW - 60);
		$this->candidate(5);
		foreach ([4, 5] as $storageId) {
			$this->mounts($storageId, [['ana', self::MOUNT]]);
			$this->scannedBy($storageId, $this->hookedScanner());
		}
		$service = $this->service();

		$due = $service->run();
		$all = $service->run(false);

		self::assertSame([5], array_column($due['results'], 'storageId'));
		self::assertSame(0, $due['waiting']);
		self::assertSame([5, 4], array_column($all['results'], 'storageId'));
		self::assertSame([RescanService::STATUS_SCANNED, RescanService::STATUS_SCANNED], array_column($all['results'], 'status'));
		self::assertSame(0, $all['waiting']);
	}

	public function testARunWithNothingDueDoesNothing(): void {
		$this->candidate(4, self::NOW - 60);

		self::assertSame(['results' => [], 'waiting' => 0], $this->service()->run());
		self::assertSame([], $this->askedMounts);
	}

	// -- files_no_background_scan ---------------------------------------------------------

	public function testTheSwitchOfTheAdminIsReadFromTheConfigurationAndTheExplicitRescanIgnoresIt(): void {
		$this->storageSeven($this->hookedScanner());
		$service = $this->service();
		self::assertFalse($service->backgroundScanDisabled());
		self::assertSame(RescanService::BACKGROUND_ON, $service->backgroundRescan());

		$this->noBackgroundScan = true;

		self::assertTrue($service->backgroundScanDisabled());
		self::assertSame('disabled_by_config', $service->backgroundRescan());
		self::assertSame(RescanService::STATUS_SCANNED, $service->rescan(7, $service->deadline())['status']);
	}

	// -- the timed job ------------------------------------------------------------------

	private function job(RescanService $service): ExternalRescanJob {
		return new ExternalRescanJob($this->createMock(ITimeFactory::class), $service, $this->logger());
	}

	private static function runJob(ExternalRescanJob $job): void {
		(new \ReflectionMethod(ExternalRescanJob::class, 'run'))->invoke($job, null);
	}

	public function testTheTimedJobWakesHourly(): void {
		$job = $this->job($this->createMock(RescanService::class));

		self::assertSame(3600, ExternalRescanJob::INTERVAL_SECONDS);
		self::assertSame(ExternalRescanJob::INTERVAL_SECONDS, $job->getInterval());
	}

	public function testTheTimedJobDoesNothingWhenBackgroundScansAreSwitchedOff(): void {
		$service = $this->createMock(RescanService::class);
		$service->method('backgroundScanDisabled')->willReturn(true);
		$service->expects(self::never())->method('run');
		$service->expects(self::never())->method('rescan');

		self::runJob($this->job($service));

		self::assertSame(['debug'], array_column($this->logged, 0));
	}

	public function testTheTimedJobRunsTheDueStoragesAndLogsCountsOnly(): void {
		$service = $this->createMock(RescanService::class);
		$service->method('backgroundScanDisabled')->willReturn(false);
		$service->expects(self::once())->method('run')->willReturn([
			'results' => [
				['storageId' => 4, 'status' => RescanService::STATUS_SCANNED, 'seconds' => 20, 'new' => 1, 'changed' => 0],
				['storageId' => 5, 'status' => RescanService::STATUS_SCANNED, 'seconds' => 30, 'new' => 0, 'changed' => 2],
				['storageId' => 6, 'status' => RescanService::STATUS_PARTIAL, 'seconds' => 250, 'new' => 0, 'changed' => 0],
			],
			'waiting' => 3,
		]);

		self::runJob($this->job($service));

		self::assertSame(
			[['info', 'Audio & Video Search: rescanned external storages', ['scanned' => 2, 'partial' => 1, 'failed' => 0, 'waiting' => 3]]],
			$this->logged,
		);
	}

	public function testTheTimedJobIsSilentWhenNothingWasDue(): void {
		$service = $this->createMock(RescanService::class);
		$service->method('backgroundScanDisabled')->willReturn(false);
		$service->expects(self::once())->method('run')->willReturn(['results' => [], 'waiting' => 0]);

		self::runJob($this->job($service));

		self::assertSame([], $this->logged);
	}

	public function testARunThatThrowsNeverLeavesTheTimedJob(): void {
		$service = $this->createMock(RescanService::class);
		$service->method('backgroundScanDisabled')->willReturn(false);
		$service->method('run')->willThrowException(new \RuntimeException('smb://nas.local/Medien is gone'));

		self::runJob($this->job($service));

		self::assertSame(
			[['warning', 'Audio & Video Search: the rescan of external storages stopped early', ['class' => \RuntimeException::class]]],
			$this->logged,
		);
	}

	// -- occ audio_video_search:rescan ----------------------------------------------------

	private const DEADLINE = self::NOW + RescanService::BUDGET_SECONDS;

	private function rescanService(): RescanService&MockObject {
		$service = $this->createMock(RescanService::class);
		$service->method('deadline')->willReturn(self::DEADLINE);

		return $service;
	}

	/** @return array{storageId: int, status: string, seconds: int, new: int, changed: int} */
	private static function outcome(int $storageId, string $status, int $seconds = 12, int $new = 3, int $changed = 1): array {
		return ['storageId' => $storageId, 'status' => $status, 'seconds' => $seconds, 'new' => $new, 'changed' => $changed];
	}

	/** @param array<string, mixed> $input */
	private static function runCommand(RescanService $service, array $input, BufferedOutput $output): int {
		return (new RescanCommand($service))->run(new ArrayInput($input), $output);
	}

	public function testStorageScansExactlyThisStorageWithTheBudgetAndPrintsDurationAndCounts(): void {
		$service = $this->rescanService();
		$service->expects(self::once())->method('rescan')->with(7, self::DEADLINE)
			->willReturn(self::outcome(7, RescanService::STATUS_SCANNED));
		$service->expects(self::never())->method('run');
		$output = new BufferedOutput();

		$code = self::runCommand($service, ['--storage' => '7'], $output);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame("Storage 7: rescanned in 12 s, 3 new and 1 changed entries.\n", $output->fetch());
	}

	public function testAStorageThatIsUnknownOrNotCapturableIsAFailureWithOneSentence(): void {
		$service = $this->rescanService();
		$service->expects(self::once())->method('rescan')->with(99, self::DEADLINE)
			->willReturn(self::outcome(99, RescanService::STATUS_NOT_CAPTURABLE, 0, 0, 0));
		$output = new BufferedOutput();

		$code = self::runCommand($service, ['--storage' => '99'], $output);

		self::assertSame(Command::FAILURE, $code);
		self::assertSame("Storage not capturable.\n", $output->fetch());
	}

	/** @return array<string, array{string, string}> status and the line it prints */
	public static function unfinished(): array {
		return [
			'budget spent' => [RescanService::STATUS_PARTIAL, "Storage 7: time budget spent after 12 s, 3 new and 1 changed entries so far. Run the command again.\n"],
			'failed' => [RescanService::STATUS_FAILED, "Storage 7: rescan failed after 12 s.\n"],
		];
	}

	#[DataProvider('unfinished')]
	public function testAStorageThatWasNotScannedToItsEndIsAFailure(string $status, string $line): void {
		$service = $this->rescanService();
		$service->method('rescan')->willReturn(self::outcome(7, $status));
		$output = new BufferedOutput();

		$code = self::runCommand($service, ['--storage' => '7'], $output);

		self::assertSame(Command::FAILURE, $code);
		self::assertSame($line, $output->fetch());
	}

	/** @return array<string, array{array<string, mixed>}> */
	public static function unusableOptions(): array {
		return [
			'neither option' => [[]],
			'both options' => [['--storage' => '7', '--all' => true]],
			'no number' => [['--storage' => 'medien']],
			'zero' => [['--storage' => '0']],
			'negative' => [['--storage' => '-7']],
			'a fraction' => [['--storage' => '7.5']],
			'empty' => [['--storage' => '']],
			'a number with a space' => [['--storage' => ' 7']],
			'far too long' => [['--storage' => '1234567890123456789012']],
		];
	}

	/** @param array<string, mixed> $input */
	#[DataProvider('unusableOptions')]
	public function testUnusableOptionsAreInvalidAndNothingIsScanned(array $input): void {
		$service = $this->rescanService();
		$service->expects(self::never())->method('rescan');
		$service->expects(self::never())->method('run');
		$output = new BufferedOutput();

		$code = self::runCommand($service, $input, $output);

		self::assertSame(Command::INVALID, $code);
		self::assertNotSame('', $output->fetch());
	}

	public function testAllRunsWithoutTheCadenceAndPrintsOneLinePerStorage(): void {
		$service = $this->rescanService();
		$service->expects(self::once())->method('run')->with(false)->willReturn([
			'results' => [
				self::outcome(4, RescanService::STATUS_SCANNED, 20, 1, 0),
				self::outcome(5, RescanService::STATUS_SCANNED, 30, 0, 2),
			],
			'waiting' => 0,
		]);
		$service->expects(self::never())->method('rescan');
		$output = new BufferedOutput();

		$code = self::runCommand($service, ['--all' => true], $output);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame(
			"Storage 4: rescanned in 20 s, 1 new and 0 changed entries.\nStorage 5: rescanned in 30 s, 0 new and 2 changed entries.\n",
			$output->fetch(),
		);
	}

	public function testAllWithStoragesLeftOverIsAFailureThatSaysHowManyWait(): void {
		$service = $this->rescanService();
		$service->method('run')->willReturn([
			'results' => [self::outcome(4, RescanService::STATUS_SCANNED, 300, 1, 0)],
			'waiting' => 2,
		]);
		$output = new BufferedOutput();

		$code = self::runCommand($service, ['--all' => true], $output);

		self::assertSame(Command::FAILURE, $code);
		self::assertSame(
			"Storage 4: rescanned in 300 s, 1 new and 0 changed entries.\nTime budget spent, 2 storages not started. Run the command again.\n",
			$output->fetch(),
		);
	}

	public function testAllWithOneStorageThatFailedIsAFailure(): void {
		$service = $this->rescanService();
		$service->method('run')->willReturn([
			'results' => [
				self::outcome(4, RescanService::STATUS_FAILED, 2, 0, 0),
				self::outcome(5, RescanService::STATUS_SCANNED, 30, 0, 2),
			],
			'waiting' => 0,
		]);
		$output = new BufferedOutput();

		$code = self::runCommand($service, ['--all' => true], $output);

		self::assertSame(Command::FAILURE, $code);
		$text = $output->fetch();
		self::assertStringContainsString("Storage 4: rescan failed after 2 s.\n", $text);
		self::assertStringContainsString('Storage 5: rescanned in 30 s', $text);
	}

	public function testAllWithoutACapturableExternalStorageSaysSo(): void {
		$service = $this->rescanService();
		$service->method('run')->willReturn(['results' => [], 'waiting' => 0]);
		$output = new BufferedOutput();

		$code = self::runCommand($service, ['--all' => true], $output);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame("No capturable external storage.\n", $output->fetch());
	}

	public function testTheCommandIsRegisteredUnderItsNameWithBothOptions(): void {
		$command = new RescanCommand($this->rescanService());

		self::assertSame('audio_video_search:rescan', $command->getName());
		self::assertTrue($command->getDefinition()->hasOption('storage'));
		self::assertTrue($command->getDefinition()->hasOption('all'));
		self::assertTrue($command->getDefinition()->getOption('storage')->isValueRequired());
		self::assertFalse($command->getDefinition()->getOption('all')->acceptValue());
	}
}
