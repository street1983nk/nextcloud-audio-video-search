<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\BackgroundJobs;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageClassifier;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\IJobList;
use OCP\BackgroundJob\TimedJob;
use OCP\IAppConfig;
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
 * External storages are classified here first (StorageClassifier, D-02-03):
 * a new one at once, a known one every 24 h, one skipped for want of
 * credentials in every run (a login with "save in database" is picked up
 * five minutes later). Classifying stops after CLASSIFY_SECONDS per run; the
 * rest waits for the next run with what avs_storage says. Only a capturable
 * external storage gets a crawl, and one that became capturable crawls again
 * from cursor 0, because its earlier files were refused.
 *
 * Exclusions set after the fact (plan 02-18, DISC-03, D-02-04): every run
 * compares ExclusionService::fingerprint with the one it applied last, so a
 * rule written by occ audio_video_search:exclude and one written directly
 * with occ config:app:set are found alike (T-02-65). A change becomes work
 * for the container, once:
 *
 * - a new user, group or storage switch: exclude_storage for every storage
 *   these rules reach (ExclusionService::storageRuleCovers; D-02-08,
 *   D-02-11: the storages of the user, not the copies of others on the same
 *   share)
 * - a new folder prefix: an ExclusionClearJob per mount, which walks it in
 *   bands and queues exclude per covered file
 * - a lifted rule: the crawls of the mounts it may have hidden files in start
 *   over (cursor 0, a new generation); no removal
 *
 * The applied state (APPLIED_RULES_KEY, then APPLIED_FINGERPRINT_KEY) is
 * written only after every row is queued and every clearing job is planned,
 * so a run that fails half way repeats the whole change (T-02-67). Rules
 * that cannot be read change nothing here: the three checks of
 * ExclusionService already exclude everything, and a typo must not remove
 * every storage.
 *
 * Log lines carry counts only.
 */
class SchedulerJob extends TimedJob {
	public const INTERVAL_SECONDS = 300;

	/** The backend states in which the discovery may start (ExAppService::SEARCHABLE_STATES). */
	public const CRAWL_STATES = [ExAppService::STATE_OK, ExAppService::STATE_VERSION_PATCH_DIFFERS];

	/** Seconds per run for classifying external storages; a probe may wait on a remote server. */
	public const CLASSIFY_SECONDS = 60;

	/** The fingerprint of the exclusions the last applied change was made for. */
	public const APPLIED_FINGERPRINT_KEY = 'applied_exclusion_fingerprint';

	/** The four lists of that change, as JSON, to tell added from lifted entries. */
	public const APPLIED_RULES_KEY = 'applied_exclusions';

	public function __construct(
		ITimeFactory $time,
		private IJobList $jobList,
		private StorageService $storageService,
		private CrawlMapper $crawlMapper,
		private ExAppService $exAppService,
		private StorageClassifier $classifier,
		private LoggerInterface $logger,
		private ExclusionService $exclusions,
		private QueueService $queueService,
		private IAppConfig $appConfig,
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

		try {
			$this->applyExclusionChanges();
		} catch (\Throwable $e) {
			// The applied state stays as it was; the next run repeats the change.
			$this->logger->warning('Audio & Video Search: changed exclusions could not be applied yet', ['class' => $e::class]);
		}

		$created = 0;
		$resumed = 0;
		$restarted = 0;
		$skipped = 0;
		$deadline = $this->time->getTime() + self::CLASSIFY_SECONDS;
		/** @var array<int, array{capturable: bool, becameCapturable: bool, checked: bool}> $verdicts */
		$verdicts = [];
		foreach ($this->storageService->getMounts() as $mount) {
			$storageId = (int)$mount['storage_id'];
			$rootId = (int)$mount['overridden_root'];
			if ($storageId <= 0 || $rootId <= 0) {
				continue;
			}
			$verdict = null;
			if ($this->storageService->isExternal($storageId)) {
				$verdict = $verdicts[$storageId] ??= $this->verdict($storageId, $deadline);
				if (!$verdict['capturable']) {
					$skipped++;
					continue;
				}
			}
			$argument = StorageCrawlJob::argument($storageId, $rootId);
			if ($this->crawlMapper->upsert($storageId, $rootId)) {
				$this->jobList->add(StorageCrawlJob::class, $argument);
				$created++;
				continue;
			}
			if ($verdict !== null && $verdict['becameCapturable']) {
				$this->crawlMapper->reset($storageId, $rootId);
				if (!$this->jobList->has(StorageCrawlJob::class, $argument)) {
					$this->jobList->add(StorageCrawlJob::class, $argument);
				}
				$restarted++;
				continue;
			}
			$crawl = $this->crawlMapper->find($storageId, $rootId);
			if ($crawl !== null && $crawl['finishedAt'] === null && !$this->jobList->has(StorageCrawlJob::class, $argument)) {
				$this->jobList->add(StorageCrawlJob::class, $argument);
				$resumed++;
			}
		}

		if ($created > 0 || $resumed > 0 || $restarted > 0) {
			$this->logger->info('Audio & Video Search: planned first crawls', [
				'created' => $created,
				'resumed' => $resumed,
				'restarted' => $restarted,
				'skipped_external' => $skipped,
			]);
		}
	}

	/**
	 * Turn a change of the exclusions since the last applied one into work:
	 * see the class comment.
	 */
	private function applyExclusionChanges(): void {
		$this->exclusions->reload();
		$fingerprint = $this->exclusions->fingerprint();
		$applied = $this->appConfig->getValueString(Application::APP_ID, self::APPLIED_FINGERPRINT_KEY, '');
		if ($applied !== '' && hash_equals($applied, $fingerprint)) {
			return;
		}
		$changes = $this->exclusions->changesSince($this->appliedRules());
		$snapshot = $this->exclusions->snapshot();
		if ($changes === null || $snapshot === null) {
			$this->logger->debug('Audio & Video Search: the exclusions cannot be read, no change applied');
			return;
		}

		/** @var list<array{0: int, 1: int}> $mounts */
		$mounts = [];
		foreach ($this->storageService->getMounts() as $mount) {
			$storageId = (int)$mount['storage_id'];
			$rootId = (int)$mount['overridden_root'];
			if ($storageId > 0 && $rootId > 0) {
				$mounts[] = [$storageId, $rootId];
			}
		}
		$storages = array_values(array_unique(array_map(static fn (array $mount): int => $mount[0], $mounts)));

		$added = $changes['added'];
		$removed = 0;
		foreach ($storages as $storageId) {
			if ($this->exclusions->storageRuleCovers($added, $storageId)) {
				$this->queueService->enqueue(QueueMapper::KIND_EXCLUDE_STORAGE, null, $storageId);
				$removed++;
			}
		}
		$clearing = 0;
		if ($added[ExclusionService::LIST_FOLDERS] !== []) {
			foreach ($mounts as [$storageId, $rootId]) {
				$this->jobList->add(ExclusionClearJob::class, ExclusionClearJob::argument($storageId, $rootId, 0));
				$clearing++;
			}
		}

		$lifted = $changes['lifted'];
		$restarted = 0;
		$liftedPrefix = $lifted[ExclusionService::LIST_FOLDERS] !== [];
		foreach ($mounts as [$storageId, $rootId]) {
			if (!$liftedPrefix && !$this->exclusions->storageRuleCovers($lifted, $storageId)) {
				continue;
			}
			if ($this->exclusions->isExcluded($storageId, '') || $this->crawlMapper->find($storageId, $rootId) === null) {
				// Still left out as a whole, or never crawled: the planning below starts it.
				continue;
			}
			$this->crawlMapper->reset($storageId, $rootId);
			$restarted++;
		}

		$this->appConfig->setValueString(
			Application::APP_ID,
			self::APPLIED_RULES_KEY,
			json_encode($snapshot, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
		);
		$this->appConfig->setValueString(Application::APP_ID, self::APPLIED_FINGERPRINT_KEY, $fingerprint);
		$this->logger->info('Audio & Video Search: applied changed exclusions', [
			'removed_storages' => $removed,
			'clearing_jobs' => $clearing,
			'restarted_crawls' => $restarted,
		]);
	}

	/**
	 * The lists of the last applied change; nothing usable means nothing was
	 * applied, so every rule in force counts as new.
	 *
	 * @return array<mixed>
	 */
	private function appliedRules(): array {
		$raw = $this->appConfig->getValueString(Application::APP_ID, self::APPLIED_RULES_KEY, '');
		if ($raw === '') {
			return [];
		}
		try {
			$decoded = json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
		} catch (\JsonException) {
			return [];
		}

		return is_array($decoded) ? $decoded : [];
	}

	/**
	 * The classification of one external storage for this run; an error
	 * counts as not capturable, the next run tries again.
	 *
	 * @return array{capturable: bool, becameCapturable: bool, checked: bool}
	 */
	private function verdict(int $storageId, int $deadline): array {
		try {
			return $this->classifier->refresh($storageId, $this->time->getTime() < $deadline);
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: an external storage could not be classified', [
				'storage_id' => $storageId,
				'class' => $e::class,
			]);

			return ['capturable' => false, 'becameCapturable' => false, 'checked' => false];
		}
	}
}
