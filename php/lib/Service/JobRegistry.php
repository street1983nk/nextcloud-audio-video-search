<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCA\AudioVideoSearch\BackgroundJobs\ExternalRescanJob;
use OCA\AudioVideoSearch\BackgroundJobs\SchedulerJob;
use OCP\BackgroundJob\IJobList;
use Psr\Log\LoggerInterface;

/**
 * The app puts its own background jobs back (plan 02-17b, owner decision).
 *
 * Enabling the app adds the jobs of info.xml to the job list once. A cron.php
 * that began before the app was enabled cannot build them, and
 * JobList::buildJob (stable33) then removes their rows ("failed to create
 * instance of background job"). Without the SchedulerJob there is never a
 * first crawl until the app is enabled again.
 *
 * The handshake of the backend calls ensure() at the start of the container
 * and every five minutes, in a fresh process that knows the classes of the
 * app. Only the public IJobList is used: has() with argument null asks for
 * exactly the row the enabling of the app adds, add() adds that row.
 *
 * Not final: the handshake test replaces it.
 */
class JobRegistry {
	/**
	 * The jobs of <background-jobs> in appinfo/info.xml, the same list
	 * (backend/tests/test_php_gates.py, rule 15).
	 *
	 * @var list<class-string>
	 */
	public const JOBS = [
		SchedulerJob::class,
		ExternalRescanJob::class,
	];

	public function __construct(
		private IJobList $jobList,
		private LoggerInterface $logger,
	) {
	}

	/**
	 * Adds every job of JOBS that is missing from the job list, never one that
	 * is there. The classes it added; an empty list after a failure, which is
	 * logged with the class of the error only.
	 *
	 * @return list<class-string>
	 */
	public function ensure(): array {
		try {
			$missing = [];
			foreach (self::JOBS as $job) {
				if (!$this->jobList->has($job, null)) {
					$missing[] = $job;
				}
			}
			foreach ($missing as $job) {
				$this->jobList->add($job, null);
				// For the admin: a job of the app had gone and is back.
				$this->logger->warning('Audio & Video Search: a missing background job was added again', ['job' => $job]);
			}

			return $missing;
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the background jobs could not be checked', ['class' => $e::class]);

			return [];
		}
	}
}
