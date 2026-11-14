<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\BackgroundJobs\ExclusionClearJob;
use OCA\AudioVideoSearch\BackgroundJobs\SchedulerJob;
use OCA\AudioVideoSearch\BackgroundJobs\StorageCrawlJob;
use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageClassifier;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\IJobList;
use OCP\Files\Cache\IFileAccess;
use OCP\Files\Config\ICachedMountInfo;
use OCP\Files\Config\IUserMountCache;
use OCP\IAppConfig;
use OCP\IDBConnection;
use OCP\IGroupManager;
use OCP\IUser;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The first crawls start only after the handshake with the backend (D-02-05),
 * and a change of the exclusions turns into removals in the next run (plan
 * 02-18, DISC-03, D-02-04).
 */
#[CoversClass(SchedulerJob::class)]
final class SchedulerJobTest extends TestCase {
	private const HOME = 'OC\Files\Mount\LocalHomeMountProvider';
	private const SHARE = 'OCA\Files_Sharing\MountProvider';
	private const TEAM = 'OCA\GroupFolders\Mount\MountProvider';
	private const EXTERNAL = StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER;

	private IJobList&MockObject $jobList;
	private StorageService&MockObject $storage;
	private CrawlMapper&MockObject $crawls;
	private ExAppService&MockObject $exApp;
	private StorageClassifier&MockObject $classifier;
	private QueueService&MockObject $queue;
	private IAppConfig&MockObject $appConfig;
	private ExclusionService $exclusions;
	/** @var list<array<string, int>> */
	private array $added = [];
	/** @var list<array<string, int>> arguments of the clearing jobs */
	private array $clearing = [];
	/** @var list<array{0: string, 1: ?int, 2: int}> */
	private array $queued = [];
	/** @var list<array{0: int, 1: int}> */
	private array $resets = [];
	/** @var array<string, string> the app config of the app */
	private array $config = [];
	/** @var array<int, list<array{string, string, ?int}>> user, provider and mount id per storage */
	private array $mountCache = [];
	/** @var array<string, list<string>> members per group */
	private array $members = [];
	private bool $queueFails = false;

	protected function setUp(): void {
		parent::setUp();

		$this->added = [];
		$this->clearing = [];
		$this->queued = [];
		$this->resets = [];
		$this->config = [];
		$this->members = [];
		$this->queueFails = false;
		$this->jobList = $this->createMock(IJobList::class);
		$this->jobList->method('add')->willReturnCallback(function (string $job, mixed $argument): void {
			if ($job === ExclusionClearJob::class) {
				$this->clearing[] = $argument;
				return;
			}
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
		$this->queue = $this->createMock(QueueService::class);
		$this->queue->method('enqueue')->willReturnCallback(function (string $kind, ?int $fileId, int $storageId): void {
			if ($this->queueFails && $this->queued !== []) {
				throw new \RuntimeException('database gone');
			}
			$this->queued[] = [$kind, $fileId, $storageId];
		});
		$this->appConfig = $this->createMock(IAppConfig::class);
		$this->appConfig->method('getValueString')->willReturnCallback(
			function (string $app, string $key, string $default = ''): string {
				self::assertSame(Application::APP_ID, $app);

				return $this->config[$key] ?? $default;
			},
		);
		$this->appConfig->method('setValueString')->willReturnCallback(function (string $app, string $key, string $value): bool {
			self::assertSame(Application::APP_ID, $app);
			$this->config[$key] = $value;

			return true;
		});
		// Without a rule and with the empty set applied, the exclusions add nothing to a run.
		$this->exclusions = $this->exclusionService();
		$this->config[SchedulerJob::APPLIED_FINGERPRINT_KEY] = $this->exclusions->fingerprint();
	}

	/**
	 * The real exclusions over a mount cache in this class, as in
	 * ExclusionServiceTest:
	 *
	 *   3   the home of eva
	 *   4   the home of ana, one file of it shared with eva
	 *   5   a team folder of ana and eva
	 *   7   the storage of ben on the SMB configuration 1 (login credentials)
	 *   8   the storage of ana on the same configuration 1
	 *   9   an external storage of configuration 2 for ana and ben together
	 */
	private function exclusionService(): ExclusionService {
		$this->mountCache = [
			3 => [['eva', self::HOME, null]],
			4 => [['ana', self::HOME, null], ['eva', self::SHARE, null]],
			5 => [['ana', self::TEAM, null], ['eva', self::TEAM, null]],
			7 => [['ben', self::EXTERNAL, 1]],
			8 => [['ana', self::EXTERNAL, 1]],
			9 => [['ana', self::EXTERNAL, 2], ['ben', self::EXTERNAL, 2]],
		];
		$cache = $this->createMock(IUserMountCache::class);
		$cache->method('getMountsForStorageId')->willReturnCallback(function (int $storageId): array {
			$infos = [];
			foreach ($this->mountCache[$storageId] ?? [] as [$uid, $provider, $mountId]) {
				$user = $this->createMock(IUser::class);
				$user->method('getUID')->willReturn($uid);
				$info = $this->createMock(ICachedMountInfo::class);
				$info->method('getUser')->willReturn($user);
				$info->method('getMountProvider')->willReturn($provider);
				$info->method('getMountId')->willReturn($mountId);
				$infos[] = $info;
			}

			return $infos;
		});
		$groups = $this->createMock(IGroupManager::class);
		$groups->method('isInGroup')->willReturnCallback(fn (string $uid, string $gid): bool => in_array($uid, $this->members[$gid] ?? [], true));

		return new ExclusionService(
			$this->appConfig,
			$cache,
			$groups,
			$this->createMock(IFileAccess::class),
			$this->createMock(StorageService::class),
			$this->createMock(IDBConnection::class),
			$this->createMock(LoggerInterface::class),
		);
	}

	private function runJob(?ITimeFactory $time = null): void {
		$job = new SchedulerJob(
			$time ?? $this->createMock(ITimeFactory::class),
			$this->jobList,
			$this->storage,
			$this->crawls,
			$this->exApp,
			$this->classifier,
			$this->createMock(LoggerInterface::class),
			$this->exclusions,
			$this->queue,
			$this->appConfig,
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

		$this->runJob($time);

		self::assertSame([[4, true], [5, false]], $asked);
		self::assertSame([StorageCrawlJob::argument(3, 11)], $this->added);
	}

	// -- exclusions set after the fact (plan 02-18) ---------------------------------

	/**
	 * The mount set of the exclusion tests, one walk root per mount, every
	 * first crawl finished already.
	 */
	private function exclusionWorld(): void {
		$this->state(ExAppService::STATE_OK);
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('getMounts')->willReturn([
			['storage_id' => 3, 'root_id' => 30, 'overridden_root' => 31],
			['storage_id' => 4, 'root_id' => 40, 'overridden_root' => 41],
			['storage_id' => 5, 'root_id' => 50, 'overridden_root' => 51],
			['storage_id' => 5, 'root_id' => 52, 'overridden_root' => 52],
			['storage_id' => 7, 'root_id' => 70, 'overridden_root' => 70],
			['storage_id' => 8, 'root_id' => 80, 'overridden_root' => 80],
			['storage_id' => 9, 'root_id' => 90, 'overridden_root' => 90],
		]);
		$this->crawls->method('upsert')->willReturn(false);
		$this->crawls->method('find')->willReturnCallback(function (int $storageId, int $rootId): array {
			$reset = in_array([$storageId, $rootId], $this->resets, true);

			return [
				'storageId' => $storageId, 'rootId' => $rootId, 'lastFileId' => $reset ? 0 : 9, 'generation' => $reset ? 1 : 0,
				'startedAt' => 1, 'finishedAt' => $reset ? null : 2,
			];
		});
		$this->crawls->method('reset')->willReturnCallback(function (int $storageId, int $rootId): void {
			$this->resets[] = [$storageId, $rootId];
		});
		$this->jobList->method('has')->willReturn(false);
	}

	/** @param list<string> $entries */
	private function rule(string $list, array $entries): void {
		$this->config[$list] = json_encode($entries, JSON_THROW_ON_ERROR);
	}

	/** One run with the rules as they stand now, the earlier calls forgotten. */
	private function runAgain(): void {
		$this->queued = [];
		$this->clearing = [];
		$this->resets = [];
		$this->added = [];
		$this->runJob();
	}

	private function assertApplied(): void {
		$this->exclusions->reload();
		self::assertSame($this->exclusions->fingerprint(), $this->config[SchedulerJob::APPLIED_FINGERPRINT_KEY] ?? null);
		self::assertSame($this->exclusions->snapshot(), json_decode($this->config[SchedulerJob::APPLIED_RULES_KEY] ?? 'null', true));
	}

	public function testAnUnchangedFingerprintDoesNothing(): void {
		$this->exclusionWorld();
		$this->rule(ExclusionService::LIST_USERS, ['ana']);
		$this->runJob();
		self::assertNotSame([], $this->queued);

		$this->runAgain();

		self::assertSame([], $this->queued);
		self::assertSame([], $this->clearing);
		self::assertSame([], $this->resets);
		self::assertSame([], $this->added);
	}

	/**
	 * D-02-08, D-02-11: the storages that belong to ana, her home and the SMB
	 * storage built with her own login; ben's storage on the same share, the
	 * storage of both and the team folder stay. Written as with occ
	 * config:app:set, without the command: the fingerprint finds it.
	 */
	public function testANewUserRemovesTheStoragesThatBelongToThem(): void {
		$this->exclusionWorld();
		$this->runJob();
		self::assertSame([], $this->queued);

		$this->rule(ExclusionService::LIST_USERS, ['ana']);
		$this->runAgain();

		self::assertSame([
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 4],
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 8],
		], $this->queued);
		self::assertSame([], $this->clearing);
		self::assertSame([], $this->resets);
		$this->assertApplied();
	}

	public function testRulesInForceBeforeAnythingWasAppliedAreAppliedInTheFirstRun(): void {
		$this->exclusionWorld();
		unset($this->config[SchedulerJob::APPLIED_FINGERPRINT_KEY]);
		$this->rule(ExclusionService::LIST_USERS, ['ana']);

		$this->runJob();

		self::assertSame([
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 4],
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 8],
		], $this->queued);
		$this->assertApplied();
	}

	public function testANewGroupRemovesTheStoragesOfEveryMember(): void {
		$this->exclusionWorld();
		$this->members = ['extern' => ['ben', 'eva']];
		$this->rule(ExclusionService::LIST_GROUPS, ['extern']);

		$this->runJob();

		self::assertSame([
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 3],
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 7],
		], $this->queued);
		$this->assertApplied();
	}

	public function testANewStorageSwitchRemovesEveryStorageOfTheConfiguration(): void {
		$this->exclusionWorld();
		$this->rule(ExclusionService::LIST_MOUNTS, ['1']);

		$this->runJob();

		self::assertSame([
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 7],
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 8],
		], $this->queued);
		$this->assertApplied();
	}

	/** A prefix names files, not storages: one clearing job per mount, from the start. */
	public function testANewPrefixPlansOneClearingJobPerMount(): void {
		$this->exclusionWorld();
		$this->rule(ExclusionService::LIST_FOLDERS, ['privat', 'Archiv']);

		$this->runJob();

		self::assertSame([], $this->queued);
		self::assertSame([
			ExclusionClearJob::argument(3, 31, 0),
			ExclusionClearJob::argument(4, 41, 0),
			ExclusionClearJob::argument(5, 51, 0),
			ExclusionClearJob::argument(5, 52, 0),
			ExclusionClearJob::argument(7, 70, 0),
			ExclusionClearJob::argument(8, 80, 0),
			ExclusionClearJob::argument(9, 90, 0),
		], $this->clearing);
		$this->assertApplied();
	}

	/** Lifted: the crawl of the storages of ana starts over, nothing is removed. */
	public function testALiftedUserCrawlsTheirStoragesAgainFromTheStart(): void {
		$this->exclusionWorld();
		$this->rule(ExclusionService::LIST_USERS, ['ana', 'eva']);
		$this->runJob();

		$this->rule(ExclusionService::LIST_USERS, ['eva']);
		$this->runAgain();

		self::assertSame([], $this->queued);
		self::assertSame([], $this->clearing);
		self::assertSame([[4, 41], [8, 80]], $this->resets);
		// The crawl planning of the same run puts their jobs back.
		self::assertSame([StorageCrawlJob::argument(4, 41), StorageCrawlJob::argument(8, 80)], $this->added);
		$this->assertApplied();
	}

	/** A lifted prefix may have hidden files in any mount, except in one still excluded as a whole. */
	public function testALiftedPrefixCrawlsEveryMountAgainThatIsNotExcluded(): void {
		$this->exclusionWorld();
		$this->rule(ExclusionService::LIST_FOLDERS, ['privat']);
		$this->rule(ExclusionService::LIST_MOUNTS, ['1']);
		$this->runJob();

		$this->rule(ExclusionService::LIST_FOLDERS, []);
		$this->runAgain();

		self::assertSame([], $this->queued);
		self::assertSame([], $this->clearing);
		self::assertSame([[3, 31], [4, 41], [5, 51], [5, 52], [9, 90]], $this->resets);
		$this->assertApplied();
	}

	/** T-02-67: the applied state moves only after every removal is queued. */
	public function testAFailureHalfWayLeavesTheAppliedStateAndTheNextRunRepeats(): void {
		$this->exclusionWorld();
		$before = $this->config[SchedulerJob::APPLIED_FINGERPRINT_KEY];
		$this->rule(ExclusionService::LIST_USERS, ['ana']);
		$this->queueFails = true;

		$this->runJob();

		self::assertSame([[QueueMapper::KIND_EXCLUDE_STORAGE, null, 4]], $this->queued);
		self::assertSame($before, $this->config[SchedulerJob::APPLIED_FINGERPRINT_KEY]);
		self::assertArrayNotHasKey(SchedulerJob::APPLIED_RULES_KEY, $this->config);

		$this->queueFails = false;
		$this->runAgain();

		self::assertSame([
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 4],
			[QueueMapper::KIND_EXCLUDE_STORAGE, null, 8],
		], $this->queued);
		$this->assertApplied();
	}

	/**
	 * Rules nobody can read exclude everything at the three checks already;
	 * they are not turned into removals of every storage, and nothing counts
	 * as applied until they are repaired.
	 */
	public function testUnreadableRulesRemoveNothingAndApplyNothing(): void {
		$this->exclusionWorld();
		$before = $this->config[SchedulerJob::APPLIED_FINGERPRINT_KEY];
		$this->config[ExclusionService::LIST_USERS] = 'ana';

		$this->runJob();

		self::assertSame([], $this->queued);
		self::assertSame([], $this->clearing);
		self::assertSame([], $this->resets);
		self::assertSame($before, $this->config[SchedulerJob::APPLIED_FINGERPRINT_KEY]);
	}

	public function testNoExclusionIsAppliedBeforeTheBackendIsThere(): void {
		$this->state(ExAppService::STATE_BACKEND_MISSING);
		$this->rule(ExclusionService::LIST_USERS, ['ana']);

		$this->runJob();

		self::assertSame([], $this->queued);
		self::assertArrayNotHasKey(SchedulerJob::APPLIED_RULES_KEY, $this->config);
	}
}
