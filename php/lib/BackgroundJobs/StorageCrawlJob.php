<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\BackgroundJobs;

use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\IJobList;
use OCP\BackgroundJob\QueuedJob;
use OCP\Files\Cache\ICacheEntry;
use OCP\Files\IMimeTypeLoader;
use OCP\Files\StorageNotAvailableException;
use OCP\Lock\LockedException;
use Psr\Log\LoggerInterface;

/**
 * The first crawl of one mount: bands of media files into the work stock (after Findling).
 *
 * One run reads bands of BAND files through StorageService::getFileSlice, the
 * one place that knows what lies in a mount, until MAX_FILES files or
 * MAX_SECONDS seconds, whichever comes first. Every file goes through
 * QueueService::admissible before it is queued as content. The cursor moves
 * for every file looked at, admissible or not, so a crawl never stands in
 * front of a file it refuses; it is written to avs_crawl after each band.
 *
 * The crawl ends only on an empty slice: then finished_at is set, which the
 * reconcile of the container waits for before it walks the mount. Otherwise
 * the run plans its successor INTERVAL_SECONDS later. A locked file or a
 * storage that is not available ends the run without finished_at; the
 * successor continues at the cursor (T-02-22).
 *
 * Being a QueuedJob, it is removed from the job list before it runs, so a
 * mount never collects crawl jobs. No log line names a path or a file.
 */
class StorageCrawlJob extends QueuedJob {
	/** Files per slice. */
	public const BAND = 500;
	/** Files per run at most. */
	public const MAX_FILES = 2000;
	/** Seconds per run at most; the cron slot is shared with every other job. */
	public const MAX_SECONDS = 60;
	/** Seconds until the next run of the same mount. */
	public const INTERVAL_SECONDS = 5;

	public function __construct(
		ITimeFactory $time,
		private IJobList $jobList,
		private StorageService $storageService,
		private QueueService $queueService,
		private CrawlMapper $crawlMapper,
		private IMimeTypeLoader $mimeTypeLoader,
		private LoggerInterface $logger,
	) {
		parent::__construct($time);
	}

	/**
	 * The argument of the job of one mount; the cursor lives in avs_crawl, not here.
	 *
	 * @return array{storage_id: int, root_id: int}
	 */
	public static function argument(int $storageId, int $rootId): array {
		return ['storage_id' => $storageId, 'root_id' => $rootId];
	}

	protected function run($argument): void {
		$storageId = is_array($argument) ? (int)($argument['storage_id'] ?? 0) : 0;
		$rootId = is_array($argument) ? (int)($argument['root_id'] ?? 0) : 0;
		if ($storageId <= 0 || $rootId <= 0) {
			$this->logger->warning('Audio & Video Search: dropped a crawl job without a usable mount', ['storage_id' => $storageId]);
			return;
		}

		$crawl = $this->crawlMapper->find($storageId, $rootId);
		if ($crawl === null || $crawl['finishedAt'] !== null) {
			return;
		}

		$cursor = $crawl['lastFileId'];
		$deadline = $this->time->getTime() + self::MAX_SECONDS;
		$seen = 0;
		$queued = 0;
		$finished = false;
		try {
			while (true) {
				$slice = $this->storageService->getFileSlice($storageId, $rootId, $cursor, self::BAND);
				if ($slice === []) {
					$finished = true;
					break;
				}
				foreach ($slice as $entry) {
					if ($this->queueIfAdmissible($storageId, $entry)) {
						$queued++;
					}
					// Only behind a file that is done: a locked file stays in front
					// of the cursor and is the first one of the next run.
					$cursor = max($cursor, (int)$entry->getId());
					$seen++;
				}
				$this->crawlMapper->advance($storageId, $rootId, $cursor);
				if ($seen >= self::MAX_FILES || $this->time->getTime() >= $deadline) {
					break;
				}
			}
		} catch (LockedException|StorageNotAvailableException $e) {
			// The files looked at so far are queued; the next run starts behind them.
			$this->crawlMapper->advance($storageId, $rootId, $cursor);
			$this->logger->info('Audio & Video Search: a crawl run stopped early', [
				'storage_id' => $storageId,
				'class' => $e::class,
				'seen' => $seen,
			]);
		}

		if ($finished) {
			$this->crawlMapper->finish($storageId, $rootId);
			$this->logger->info('Audio & Video Search: finished the first crawl of a mount', [
				'storage_id' => $storageId,
				'seen' => $seen,
				'queued' => $queued,
			]);
			return;
		}

		$this->logger->debug('Audio & Video Search: crawled a part of a mount', [
			'storage_id' => $storageId,
			'seen' => $seen,
			'queued' => $queued,
		]);
		$this->jobList->scheduleAfter(
			self::class,
			$this->time->getTime() + self::INTERVAL_SECONDS,
			self::argument($storageId, $rootId),
		);
	}

	private function queueIfAdmissible(int $storageId, ICacheEntry $entry): bool {
		$mime = (string)$entry->getMimeType();
		$mimeId = $mime !== '' && $this->mimeTypeLoader->exists($mime) ? $this->mimeTypeLoader->getId($mime) : 0;
		$relative = $this->storageService->mountRelativePath($storageId, (string)$entry->getPath());
		if ($relative === null || !$this->queueService->admissible($storageId, $mimeId, $relative)) {
			return false;
		}
		$this->queueService->enqueue(QueueMapper::KIND_CONTENT, (int)$entry->getId(), $storageId);

		return true;
	}
}
