<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\BackgroundJobs;

use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\IJobList;
use OCP\BackgroundJob\TimedJob;
use Psr\Log\LoggerInterface;

/**
 * Every 300 s: turns the mount set into first crawls, once the backend is there.
 *
 * The first crawl starts only after the handshake with the backend is ok (or
 * differs in the patch version only). Until then nothing is queued: the admin
 * can install the PHP app, set exclusions and only then install the backend,
 * and an excluded file never enters the work stock (D-02-05, T-02-21).
 *
 * A mount without a row in avs_crawl gets one and a StorageCrawlJob. A crawl
 * that is not finished and whose job is missing from the job list (a lost cron
 * run, a removed job) gets its job back; the cursor lives in avs_crawl, so it
 * continues where it stood. This job does no walking itself: enumerating the
 * mounts is cheap and bounded, walking them is neither.
 *
 * Log lines carry counts only.
 */
class SchedulerJob extends TimedJob {
	public const INTERVAL_SECONDS = 300;

	/** The backend states in which the discovery may start (ExAppService::SEARCHABLE_STATES). */
	public const CRAWL_STATES = [ExAppService::STATE_OK, ExAppService::STATE_VERSION_PATCH_DIFFERS];

	public function __construct(
		ITimeFactory $time,
		private IJobList $jobList,
		private StorageService $storageService,
		private CrawlMapper $crawlMapper,
		private ExAppService $exAppService,
		private LoggerInterface $logger,
	) {
		parent::__construct($time);
		$this->setInterval(self::INTERVAL_SECONDS);
	}

	protected function run($argument): void {
		$admin = $this->exAppService->firstAdmin();
		if ($admin === null) {
			$this->logger->info('Audio & Video Search: no enabled admin to check the backend state with, no crawl planned');
			return;
		}
		$state = $this->exAppService->backendState($admin)['state'];
		if (!in_array($state, self::CRAWL_STATES, true)) {
			$this->logger->debug('Audio & Video Search: the backend is not ready, no crawl planned', ['state' => $state]);
			return;
		}

		$created = 0;
		$resumed = 0;
		foreach ($this->storageService->getMounts() as $mount) {
			$storageId = (int)$mount['storage_id'];
			$rootId = (int)$mount['overridden_root'];
			if ($storageId <= 0 || $rootId <= 0) {
				continue;
			}
			$argument = StorageCrawlJob::argument($storageId, $rootId);
			if ($this->crawlMapper->upsert($storageId, $rootId)) {
				$this->jobList->add(StorageCrawlJob::class, $argument);
				$created++;
				continue;
			}
			$crawl = $this->crawlMapper->find($storageId, $rootId);
			if ($crawl !== null && $crawl['finishedAt'] === null && !$this->jobList->has(StorageCrawlJob::class, $argument)) {
				$this->jobList->add(StorageCrawlJob::class, $argument);
				$resumed++;
			}
		}

		if ($created > 0 || $resumed > 0) {
			$this->logger->info('Audio & Video Search: planned first crawls', ['created' => $created, 'resumed' => $resumed]);
		}
	}
}
