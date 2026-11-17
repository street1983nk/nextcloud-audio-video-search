<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\BackgroundJobs;

use OCA\AudioVideoSearch\Service\RescanService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\TimedJob;
use Psr\Log\LoggerInterface;

/**
 * Every hour: the rescan of the external storages that are due (DISC-04).
 *
 * The job only wakes RescanService: which storages are due (once in 24 h
 * each), in which order and within which budget (300 s per run) is decided
 * there, the same way occ audio_video_search:rescan --all decides it.
 *
 * With files_no_background_scan set in config.php the job does nothing: the
 * admin switched the background scans of the instance off, and this is one.
 * occ audio_video_search:status says so.
 *
 * Log lines carry counts only.
 */
class ExternalRescanJob extends TimedJob {
	public const INTERVAL_SECONDS = 3600;

	public function __construct(
		ITimeFactory $time,
		private RescanService $rescanService,
		private LoggerInterface $logger,
	) {
		parent::__construct($time);
		$this->setInterval(self::INTERVAL_SECONDS);
	}

	protected function run($argument): void {
		if ($this->rescanService->backgroundScanDisabled()) {
			$this->logger->debug('Audio & Video Search: background scans are switched off in the configuration, no rescan of external storages');
			return;
		}

		try {
			$run = $this->rescanService->run();
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the rescan of external storages stopped early', ['class' => $e::class]);
			return;
		}

		if ($run['results'] === [] && $run['waiting'] === 0) {
			return;
		}
		$statuses = array_count_values(array_column($run['results'], 'status'));
		$this->logger->info('Audio & Video Search: rescanned external storages', [
			'scanned' => $statuses[RescanService::STATUS_SCANNED] ?? 0,
			'partial' => $statuses[RescanService::STATUS_PARTIAL] ?? 0,
			'failed' => $statuses[RescanService::STATUS_FAILED] ?? 0,
			'waiting' => $run['waiting'],
		]);
	}
}
