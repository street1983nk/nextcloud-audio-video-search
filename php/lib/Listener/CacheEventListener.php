<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Listener;

use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\EventDispatcher\Event;
use OCP\EventDispatcher\IEventListener;
use OCP\Files\Cache\CacheEntryInsertedEvent;
use OCP\Files\Cache\CacheEntryRemovedEvent;
use OCP\Files\Cache\CacheEntryUpdatedEvent;
use OCP\Files\Cache\ICacheEvent;
use OCP\Files\IMimeTypeDetector;
use OCP\Files\IMimeTypeLoader;
use Psr\Log\LoggerInterface;

/**
 * What a scanner finds into the work stock: occ files:scan, the rescan of
 * external storages (plan 02-14), a "check for changes" of a mount.
 *
 * A scanner writes oc_filecache directly and raises no node event, only cache
 * events (RESEARCH, Standard Stack). They fire for every row a scanner
 * touches, previews and app data included, so the media type is the first
 * question and needs no query: it is detected from the ending of the path, the
 * same mapping Nextcloud stores the type with (T-02-24). Only a medium goes on
 * to the mount set and to QueueService::admissible, the one pre-check of the
 * crawl and of the node events; describe checks the real cache row once more
 * when the row is handed out.
 *
 * - inserted, updated: content
 * - removed: delete, for a medium in the mount set
 *
 * A move across storages removes and inserts the same file id; content and
 * delete of one file id replace each other in the queue, so the insert that
 * comes second wins (T-02-25).
 *
 * A failure never reaches the scanner; the log line carries the class only.
 *
 * @template-implements IEventListener<Event>
 */
class CacheEventListener implements IEventListener {
	public function __construct(
		private QueueService $queueService,
		private StorageService $storageService,
		private IMimeTypeDetector $mimeTypeDetector,
		private IMimeTypeLoader $mimeTypeLoader,
		private LoggerInterface $logger,
	) {
	}

	public function handle(Event $event): void {
		if (!$event instanceof ICacheEvent) {
			return;
		}
		try {
			$mime = $this->mediaType($event->getPath());
			if ($mime === null) {
				return;
			}
			$fileId = $event->getFileId();
			$storageId = $event->getStorageId();
			if ($fileId <= 0 || $storageId <= 0) {
				return;
			}

			if ($event instanceof CacheEntryRemovedEvent) {
				if ($this->storageService->inMountSet($storageId)) {
					$this->queueService->enqueue(QueueMapper::KIND_DELETE, $fileId, $storageId);
				}
				return;
			}

			if ($event instanceof CacheEntryInsertedEvent || $event instanceof CacheEntryUpdatedEvent) {
				$mimeId = $this->mimeTypeLoader->exists($mime) ? $this->mimeTypeLoader->getId($mime) : 0;
				$relative = $this->storageService->mountRelativePath($storageId, $event->getPath());
				if ($relative !== null && $this->queueService->admissible($storageId, $mimeId, $relative)) {
					$this->queueService->enqueue(QueueMapper::KIND_CONTENT, $fileId, $storageId);
				}
			}
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: a cache event could not be queued', ['class' => $e::class]);
		}
	}

	/** audio/* or video/* by the ending of the path, null for anything else. */
	private function mediaType(string $internalPath): ?string {
		if ($internalPath === '') {
			return null;
		}
		// The detected spelling is kept: mts is stored as video/MP2T.
		$mime = $this->mimeTypeDetector->detectPath($internalPath);
		$lower = strtolower($mime);

		return str_starts_with($lower, 'audio/') || str_starts_with($lower, 'video/') ? $mime : null;
	}
}
