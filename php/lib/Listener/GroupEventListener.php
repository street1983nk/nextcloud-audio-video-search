<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Listener;

use OCA\AudioVideoSearch\BackgroundJobs\StorageCrawlJob;
use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\BackgroundJob\IJobList;
use OCP\EventDispatcher\Event;
use OCP\EventDispatcher\IEventListener;
use OCP\Files\Config\IUserMountCache;
use OCP\Group\Events\UserAddedEvent;
use OCP\Group\Events\UserRemovedEvent;
use OCP\IUser;
use Psr\Log\LoggerInterface;

/**
 * A membership of an excluded group, judged again at once (plan 02-18,
 * D-02-08, T-02-66; after Findling).
 *
 * A group exclusion means: the storages of every member are not captured
 * and the member gets no hits. The fingerprint of the rules does not change
 * when somebody joins or leaves a group, so SchedulerJob cannot see it; these
 * two events of OCP\Group\Events can.
 *
 * - joined an excluded group: exclude_storage for every storage that belongs
 *   to the user (ExclusionService::storageOwner: the home, an external
 *   storage only they have or built with their own login, D-02-11). What
 *   others share with them stays.
 * - left an excluded group and not excluded otherwise (by name, by another
 *   group): the crawls of their storages start over, cursor 0 and a new
 *   generation; a storage switched off as a whole stays off, one never
 *   crawled is started by SchedulerJob.
 *
 * Hits stop at once anyway: the search provider asks isExcludedUser for every
 * search. The storages are found through the mount cache of the user, so a
 * user who never logged in has none yet, and the crawl leaves them out
 * through QueueService::admissible.
 *
 * A failure never reaches the group change of the admin; the log line
 * carries the class only, never a user or a group.
 *
 * @template-implements IEventListener<Event>
 */
class GroupEventListener implements IEventListener {
	public function __construct(
		private ExclusionService $exclusions,
		private IUserMountCache $userMountCache,
		private StorageService $storageService,
		private QueueService $queueService,
		private CrawlMapper $crawlMapper,
		private IJobList $jobList,
		private LoggerInterface $logger,
	) {
	}

	public function handle(Event $event): void {
		try {
			if ($event instanceof UserAddedEvent) {
				$this->joined($event->getGroup()->getGID(), $event->getUser());
			} elseif ($event instanceof UserRemovedEvent) {
				$this->left($event->getGroup()->getGID(), $event->getUser());
			}
		} catch (\Throwable $e) {
			// The class only: the message of a group backend carries names.
			$this->logger->warning('Audio & Video Search: a group change could not be applied', ['class' => $e::class]);
		}
	}

	private function joined(string $gid, IUser $user): void {
		$this->exclusions->reload();
		if (!$this->exclusions->groupListed($gid)) {
			return;
		}
		$removed = 0;
		foreach ($this->ownStorages($user) as $storageId) {
			$this->queueService->enqueue(QueueMapper::KIND_EXCLUDE_STORAGE, null, $storageId);
			$removed++;
		}
		$this->logger->info('Audio & Video Search: a member of an excluded group was taken out', ['storages' => $removed]);
	}

	private function left(string $gid, IUser $user): void {
		$this->exclusions->reload();
		if (!$this->exclusions->groupListed($gid) || $this->exclusions->isExcludedUser($user->getUID())) {
			return;
		}
		$restarted = 0;
		foreach ($this->ownStorages($user) as $storageId) {
			if ($this->exclusions->isExcluded($storageId, '')) {
				continue;
			}
			foreach ($this->storageService->mountRoots($storageId) as $root) {
				$rootId = $root['rootId'];
				if ($this->crawlMapper->find($storageId, $rootId) === null) {
					continue;
				}
				$this->crawlMapper->reset($storageId, $rootId);
				$argument = StorageCrawlJob::argument($storageId, $rootId);
				if (!$this->jobList->has(StorageCrawlJob::class, $argument)) {
					$this->jobList->add(StorageCrawlJob::class, $argument);
				}
				$restarted++;
			}
		}
		$this->logger->info('Audio & Video Search: a former member of an excluded group is crawled again', ['crawls' => $restarted]);
	}

	/**
	 * The storages of the mount set that belong to this user, each once.
	 *
	 * @return list<int>
	 */
	private function ownStorages(IUser $user): array {
		$uid = mb_strtolower($user->getUID());
		$storages = [];
		foreach ($this->userMountCache->getMountsForUser($user) as $mount) {
			$storageId = (int)$mount->getStorageId();
			if ($storageId <= 0 || isset($storages[$storageId]) || $this->storageService->mountRoots($storageId) === []) {
				continue;
			}
			$owner = $this->exclusions->storageOwner($storageId);
			if ($owner !== null && mb_strtolower($owner) === $uid) {
				$storages[$storageId] = true;
			}
		}

		return array_keys($storages);
	}
}
