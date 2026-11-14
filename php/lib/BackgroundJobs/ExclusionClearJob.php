<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\BackgroundJobs;

use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\IJobList;
use OCP\BackgroundJob\QueuedJob;
use Psr\Log\LoggerInterface;

/**
 * Takes the files of one mount out of the work stock that a folder prefix set
 * after the fact covers (plan 02-18, DISC-03, D-02-04; after Findling's
 * ExclusionSweepJob).
 *
 * A prefix names a folder below the root of every mount, so SchedulerJob plans
 * one run per mount when a prefix is added. A run reads the media files of
 * the mount in bands of BAND through StorageService::getFileSlice, the one
 * place that knows what lies in a mount (gate rule 12), turns each internal
 * path into the path below the walk root with StorageService::mountRelativePath
 * and asks ExclusionService::isExcluded with the rules of now. A covered file
 * gets one exclude row; the container drops its reference and forgets a
 * content that loses its last one (D-02-04). A rule lifted while the run is
 * under way covers nothing more, so the run clears nothing more either.
 *
 * A storage that is excluded as a whole is not walked: it has its
 * exclude_storage row, and a row per file would only repeat it.
 *
 * Bands until the mount is done or MAX_SECONDS have passed; then the
 * successor continues at the cursor. A failure plans the same band again
 * after RETRY_SECONDS instead of ending the chain: SchedulerJob has written
 * the rule as applied already, and a lost run would leave the files of the
 * folder in the index until the reconcile finds them.
 *
 * Log lines carry the storage id and counts; never a path, a prefix or a
 * name (T-02-60).
 */
class ExclusionClearJob extends QueuedJob {
	/** Files per slice. */
	public const BAND = 500;
	/** Seconds per run at most; the cron slot is shared with every other job. */
	public const MAX_SECONDS = 30;
	/** Seconds until the next run of the same mount. */
	public const INTERVAL_SECONDS = 5;
	/** Seconds until a failed band is tried again. */
	public const RETRY_SECONDS = 300;

	public function __construct(
		ITimeFactory $time,
		private IJobList $jobList,
		private StorageService $storageService,
		private QueueService $queueService,
		private ExclusionService $exclusions,
		private LoggerInterface $logger,
	) {
		parent::__construct($time);
	}

	/**
	 * The argument of one run: the mount and the file id the walk stands behind.
	 *
	 * @return array{storage_id: int, root_id: int, last_file_id: int}
	 */
	public static function argument(int $storageId, int $rootId, int $lastFileId): array {
		return ['storage_id' => $storageId, 'root_id' => $rootId, 'last_file_id' => $lastFileId];
	}

	protected function run($argument): void {
		$storageId = is_array($argument) ? (int)($argument['storage_id'] ?? 0) : 0;
		$rootId = is_array($argument) ? (int)($argument['root_id'] ?? 0) : 0;
		$cursor = is_array($argument) ? max(0, (int)($argument['last_file_id'] ?? 0)) : 0;
		if ($storageId <= 0 || $rootId <= 0) {
			$this->logger->warning('Audio & Video Search: dropped a clearing job without a usable mount', ['storage_id' => $storageId]);
			return;
		}

		$deadline = $this->time->getTime() + self::MAX_SECONDS;
		$seen = 0;
		$cleared = 0;
		try {
			$this->exclusions->reload();
			if ($this->exclusions->isExcluded($storageId, '')) {
				return;
			}
			while (true) {
				$slice = $this->storageService->getFileSlice($storageId, $rootId, $cursor, self::BAND);
				foreach ($slice as $entry) {
					$fileId = (int)$entry->getId();
					$relative = $this->storageService->mountRelativePath($storageId, (string)$entry->getPath());
					if ($relative !== null && $relative !== '' && $this->exclusions->isExcluded($storageId, $relative)) {
						$this->queueService->enqueue(QueueMapper::KIND_EXCLUDE, $fileId, $storageId);
						$cleared++;
					}
					$cursor = max($cursor, $fileId);
					$seen++;
				}
				if (count($slice) < self::BAND) {
					$this->logger->info('Audio & Video Search: cleared a mount for a new folder exclusion', [
						'storage_id' => $storageId,
						'seen' => $seen,
						'cleared' => $cleared,
					]);
					return;
				}
				if ($this->time->getTime() >= $deadline) {
					break;
				}
			}
		} catch (\Throwable $e) {
			// The class only: the message of a file system or database error may carry a path.
			$this->logger->warning('Audio & Video Search: a clearing run failed, the band is tried again later', [
				'storage_id' => $storageId,
				'class' => $e::class,
			]);
			$this->jobList->scheduleAfter(self::class, $this->time->getTime() + self::RETRY_SECONDS, self::argument($storageId, $rootId, $cursor));
			return;
		}

		$this->logger->debug('Audio & Video Search: cleared a part of a mount', [
			'storage_id' => $storageId,
			'seen' => $seen,
			'cleared' => $cleared,
		]);
		$this->jobList->scheduleAfter(self::class, $this->time->getTime() + self::INTERVAL_SECONDS, self::argument($storageId, $rootId, $cursor));
	}
}
