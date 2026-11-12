<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCA\AudioVideoSearch\Db\StorageStateMapper;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\Files\Cache\IScanner;
use OCP\Files\Config\ICachedMountInfo;
use OCP\Files\Config\IUserMountCache;
use OCP\IConfig;
use Psr\Log\LoggerInterface;

/**
 * The rescan of external storages: changes made on the external server
 * itself, which Nextcloud never sees in the background (DISC-04,
 * 02-RESEARCH.md Befund 5, Pitfall 3).
 *
 * oc_filecache of an external storage only changes when somebody scans. The
 * background scan of Nextcloud visits unfinished folders only and finds no
 * replaced file. So every capturable external storage is scanned here once
 * in RESCAN_SECONDS with the scanner of Nextcloud itself; what the scanner
 * writes raises cache events, and CacheEventListener (plan 02-07) queues the
 * media among them. This class queues nothing itself.
 *
 * Order: storages of one share (same share key hash, one cache per user)
 * follow each other, the one with the most media rows first; the copies of
 * the other users are cheap afterwards, the prefilter groups them. The share
 * that waited longest comes first.
 *
 * Budget: BUDGET_SECONDS per run. Once it is spent no further storage is
 * started, and a scan in progress stops at the next folder (T-02-51). A
 * storage that was stopped keeps its old rescanned_at, so it is due again in
 * the next run; folders the scanner left unfinished are picked up first
 * (IScanner::backgroundScan), then the storage is walked again. Only a walk
 * that reached its end writes rescanned_at.
 *
 * Never scanned: a storage that is not an external storage of the mount set,
 * has no row in avs_storage or is not capturable there, and one whose probe
 * (StorageClassifier::probe) hands out no usable storage (T-02-52).
 *
 * files_no_background_scan of the admin switches the timed job off
 * (ExternalRescanJob asks backgroundScanDisabled()); occ
 * audio_video_search:rescan stays possible as an explicit act of the admin.
 *
 * Log lines carry the storage id, the status, the duration and counts.
 * Nothing here logs or returns a path, a file name, a host or a share.
 */
class RescanService {
	/** A storage is rescanned again after this many seconds. */
	public const RESCAN_SECONDS = 86400;

	/** Seconds per run, for the timed job and for the occ command alike. */
	public const BUDGET_SECONDS = 300;

	/** How many users of a storage are tried as its reader. */
	public const MAX_READER_TRIES = 5;

	/** The walk reached its end; rescanned_at is written. */
	public const STATUS_SCANNED = 'scanned';
	/** The budget was spent before the walk reached its end. */
	public const STATUS_PARTIAL = 'partial';
	/** No reader, no usable storage, or the scanner gave up. */
	public const STATUS_FAILED = 'failed';
	/** Not an external storage that may be captured; nothing was touched. */
	public const STATUS_NOT_CAPTURABLE = 'not_capturable';

	/** What occ audio_video_search:status prints as backgroundRescan. */
	public const BACKGROUND_ON = 'on';
	public const BACKGROUND_DISABLED = 'disabled_by_config';

	/** The system value of Nextcloud that switches every background scan off. */
	private const NO_BACKGROUND_SCAN = 'files_no_background_scan';

	/** The hook scope of the scanner of Nextcloud (OC\Files\Cache\Scanner). */
	private const SCANNER_SCOPE = '\OC\Files\Cache\Scanner';

	public function __construct(
		private StorageStateMapper $storageStates,
		private StorageService $storageService,
		private StorageClassifier $classifier,
		private IUserMountCache $userMountCache,
		private ReaderContext $readerContext,
		private IConfig $config,
		private ITimeFactory $timeFactory,
		private LoggerInterface $logger,
	) {
	}

	/** Did the admin switch the background scans of the instance off? */
	public function backgroundScanDisabled(): bool {
		return $this->config->getSystemValueBool(self::NO_BACKGROUND_SCAN, false);
	}

	/** BACKGROUND_ON or BACKGROUND_DISABLED, for occ audio_video_search:status. */
	public function backgroundRescan(): string {
		return $this->backgroundScanDisabled() ? self::BACKGROUND_DISABLED : self::BACKGROUND_ON;
	}

	/** The moment a run that starts now has to stop. */
	public function deadline(): int {
		return $this->timeFactory->getTime() + self::BUDGET_SECONDS;
	}

	/**
	 * The capturable external storages whose last complete rescan is
	 * RESCAN_SECONDS old or never happened, in the order they are scanned.
	 *
	 * @return list<int>
	 */
	public function due(): array {
		return $this->ordered(true);
	}

	/**
	 * Every capturable external storage, due or not, in the same order.
	 *
	 * @return list<int>
	 */
	public function all(): array {
		return $this->ordered(false);
	}

	/**
	 * One run within the budget: the due storages (or all of them) one after
	 * the other. Once the budget is spent no further storage is started.
	 *
	 * @return array{results: list<array{storageId: int, status: string, seconds: int, new: int, changed: int}>, waiting: int}
	 */
	public function run(bool $onlyDue = true): array {
		$deadline = $this->deadline();
		$storageIds = $onlyDue ? $this->due() : $this->all();
		$results = [];
		$waiting = 0;
		foreach ($storageIds as $index => $storageId) {
			if ($this->timeFactory->getTime() >= $deadline) {
				$waiting = count($storageIds) - $index;
				break;
			}
			$results[] = $this->rescan($storageId, $deadline);
		}

		return ['results' => $results, 'waiting' => $waiting];
	}

	/**
	 * Scan one capturable external storage as one of its users, until the
	 * end of the walk or until $deadline (unix seconds).
	 *
	 * @return array{storageId: int, status: string, seconds: int, new: int, changed: int}
	 */
	public function rescan(int $storageId, int $deadline): array {
		$result = ['storageId' => $storageId, 'status' => self::STATUS_NOT_CAPTURABLE, 'seconds' => 0, 'new' => 0, 'changed' => 0];
		if ($storageId <= 0 || !$this->capturable($storageId)) {
			return $result;
		}

		$started = $this->timeFactory->getTime();
		if ($started >= $deadline) {
			$result['status'] = self::STATUS_PARTIAL;

			return $result;
		}

		$counts = ['new' => 0, 'changed' => 0];
		$status = self::STATUS_FAILED;
		foreach ($this->readers($storageId) as $info) {
			$outcome = $this->scanAs($info, $storageId, $deadline, $counts);
			if ($outcome !== null) {
				$status = $outcome;
				break;
			}
		}

		$finished = $this->timeFactory->getTime();
		if ($status === self::STATUS_SCANNED) {
			$this->storageStates->markRescanned($storageId, $finished);
		}
		$result['status'] = $status;
		$result['seconds'] = max(0, $finished - $started);
		$result['new'] = $counts['new'];
		$result['changed'] = $counts['changed'];
		$this->logger->info('Audio & Video Search: rescan of an external storage', [
			'storage_id' => $storageId,
			'status' => $status,
			'seconds' => $result['seconds'],
			'new' => $result['new'],
			'changed' => $result['changed'],
		]);

		return $result;
	}

	/**
	 * An external storage of the mount set with a row in avs_storage that
	 * says capturable. Everything else is never scanned (T-02-52).
	 */
	private function capturable(int $storageId): bool {
		if (!$this->storageService->isExternal($storageId)) {
			return false;
		}
		$state = $this->storageStates->find($storageId);

		return $state !== null && $state['capturable'];
	}

	/**
	 * @return list<int>
	 */
	private function ordered(bool $onlyDue): array {
		$now = $this->timeFactory->getTime();
		/** @var array<string, array{waitingSince: int, first: int, members: list<array{storageId: int, mediaRows: int}>}> $shares */
		$shares = [];
		foreach ($this->storageStates->rescanCandidates() as $row) {
			$storageId = $row['storageId'];
			$rescannedAt = $row['rescannedAt'];
			if ($storageId <= 0 || !$this->storageService->isExternal($storageId)) {
				continue;
			}
			if ($onlyDue && $rescannedAt !== null && $now - $rescannedAt < self::RESCAN_SECONDS) {
				continue;
			}
			// A storage without a share key (S3, local, WebDAV) is a share of its own.
			$share = $row['shareKeyHash'] ?? 'storage:' . $storageId;
			if (!isset($shares[$share])) {
				$shares[$share] = ['waitingSince' => $rescannedAt ?? 0, 'first' => $storageId, 'members' => []];
			}
			$shares[$share]['waitingSince'] = min($shares[$share]['waitingSince'], $rescannedAt ?? 0);
			$shares[$share]['first'] = min($shares[$share]['first'], $storageId);
			$shares[$share]['members'][] = ['storageId' => $storageId, 'mediaRows' => $this->mediaRows($storageId)];
		}

		$shares = array_values($shares);
		usort($shares, static fn (array $a, array $b): int => [$a['waitingSince'], $a['first']] <=> [$b['waitingSince'], $b['first']]);

		$storageIds = [];
		foreach ($shares as $share) {
			$members = $share['members'];
			usort($members, static fn (array $a, array $b): int => [$b['mediaRows'], $a['storageId']] <=> [$a['mediaRows'], $b['storageId']]);
			foreach ($members as $member) {
				$storageIds[] = $member['storageId'];
			}
		}

		return $storageIds;
	}

	/** The media rows of a storage, for the order only; 0 when they cannot be counted. */
	private function mediaRows(int $storageId): int {
		try {
			return $this->storageService->mediaRows($storageId);
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the media rows of an external storage could not be counted', [
				'storage_id' => $storageId,
				'class' => $e::class,
			]);

			return 0;
		}
	}

	/**
	 * The mounts to try as reader, one per user in the order of the user
	 * ids, at most MAX_READER_TRIES: the users of the mount configuration
	 * the storage was classified by, as the mount cache knows them.
	 *
	 * @return list<ICachedMountInfo>
	 */
	private function readers(int $storageId): array {
		$state = $this->storageStates->find($storageId);
		$mountId = $state === null ? null : $state['mountId'];
		$infos = [];
		$seen = [];
		foreach ($this->userMountCache->getMountsForStorageId($storageId) as $info) {
			if ($info->getMountProvider() !== StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER) {
				continue;
			}
			$uid = $info->getUser()->getUID();
			if ($uid === '' || isset($seen[$uid])) {
				continue;
			}
			if ($mountId !== null && $info->getMountId() !== $mountId) {
				continue;
			}
			$seen[$uid] = true;
			$infos[] = $info;
		}
		usort($infos, static fn (ICachedMountInfo $a, ICachedMountInfo $b): int => strcmp($a->getUser()->getUID(), $b->getUser()->getUID()));

		return array_slice($infos, 0, self::MAX_READER_TRIES);
	}

	/**
	 * Scan as the user of one mount. null: this user gets no usable storage,
	 * the next one is tried. A scan that began is never repeated as another
	 * user; an error in it is STATUS_FAILED.
	 *
	 * @param array{new: int, changed: int} $counts
	 */
	private function scanAs(ICachedMountInfo $info, int $storageId, int $deadline, array &$counts): ?string {
		try {
			return $this->readerContext->actAs(
				$info->getUser()->getUID(),
				function () use ($info, $storageId, $deadline, &$counts): ?string {
					$storage = $this->classifier->probe($info, $storageId);
					if ($storage === null) {
						return null;
					}

					return $this->scan($storage->getScanner(), $deadline, $counts);
				},
			);
		} catch (\Throwable $e) {
			$this->logger->info('Audio & Video Search: an external storage could not be rescanned', [
				'storage_id' => $storageId,
				'class' => $e::class,
			]);

			return self::STATUS_FAILED;
		}
	}

	/**
	 * Unfinished folders first, then the whole storage, etag and size reused
	 * for what did not change.
	 *
	 * The scanner of Nextcloud offers hooks (deprecated there, and the only
	 * way to look into a scan that runs): scanFolder and postScanFolder check
	 * the deadline, addToCache counts what is written. Both folder hooks fire
	 * outside the transaction the scanner wraps around the entries of one
	 * folder, so stopping there leaves no open transaction; a folder is the
	 * smallest step. A scanner without hooks is not stopped and counts
	 * nothing. The hooks are taken off again: the storage keeps its scanner
	 * for the whole process.
	 *
	 * @param array{new: int, changed: int} $counts
	 */
	private function scan(IScanner $scanner, int $deadline, array &$counts): string {
		$stop = new \RuntimeException('the rescan budget is spent');
		$tick = function () use ($deadline, $stop): void {
			if ($this->timeFactory->getTime() >= $deadline) {
				throw $stop;
			}
		};
		// addToCache(path, storage id, data, file id): the file id is -1 for a new entry.
		$count = static function (mixed ...$arguments) use (&$counts): void {
			if (($arguments[3] ?? -1) === -1) {
				$counts['new']++;
			} else {
				$counts['changed']++;
			}
		};

		$hooked = is_callable([$scanner, 'listen']) && is_callable([$scanner, 'removeListener']);
		if ($hooked) {
			$scanner->listen(self::SCANNER_SCOPE, 'scanFolder', $tick);
			$scanner->listen(self::SCANNER_SCOPE, 'postScanFolder', $tick);
			$scanner->listen(self::SCANNER_SCOPE, 'addToCache', $count);
		}
		try {
			$scanner->backgroundScan();
			$root = $scanner->scan('', IScanner::SCAN_RECURSIVE, IScanner::REUSE_ETAG | IScanner::REUSE_SIZE);
		} catch (\RuntimeException $e) {
			if ($e !== $stop) {
				throw $e;
			}

			return self::STATUS_PARTIAL;
		} finally {
			if ($hooked) {
				$scanner->removeListener(self::SCANNER_SCOPE, 'scanFolder', $tick);
				$scanner->removeListener(self::SCANNER_SCOPE, 'postScanFolder', $tick);
				$scanner->removeListener(self::SCANNER_SCOPE, 'addToCache', $count);
			}
		}

		// null: the scanner found no root to walk.
		return $root === null ? self::STATUS_FAILED : self::STATUS_SCANNED;
	}
}
