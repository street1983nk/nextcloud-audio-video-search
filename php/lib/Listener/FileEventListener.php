<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Listener;

use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\FileAccess;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\EventDispatcher\Event;
use OCP\EventDispatcher\IEventListener;
use OCP\Files\Events\Node\NodeCopiedEvent;
use OCP\Files\Events\Node\NodeCreatedEvent;
use OCP\Files\Events\Node\NodeDeletedEvent;
use OCP\Files\Events\Node\NodeRenamedEvent;
use OCP\Files\Events\Node\NodeTouchedEvent;
use OCP\Files\Events\Node\NodeWrittenEvent;
use OCP\Files\File;
use OCP\Files\IMimeTypeLoader;
use OCP\Files\Node;
use Psr\Log\LoggerInterface;

/**
 * Node events of Nextcloud into the work stock, within minutes (DISC-04, after Findling).
 *
 * The events come from the dispatcher inside the Nextcloud process, not from
 * the AppAPI node_event bridge: that one is asynchronous and carries no share,
 * group or cache events, and a second way into the same queue is what Findling
 * ruled out (RESEARCH, Alternatives). HookConnector turns every write of View
 * (WebDAV, desktop client, web interface, occ) into these typed events.
 *
 * - created, written, touched: content, if the file is admissible
 * - copied: content for the target, a new file id
 * - renamed inside one storage: metadata, the file id and the bytes stay
 *   (DISC-06); across storages content for the target and delete for a source
 *   id that differs; a target that is no longer admissible (renamed away from
 *   a media ending): delete
 * - deleted: delete (plan 02-18 tells the trash bin apart)
 *
 * Tags raise no node event and change no etag in oc_filecache (RESEARCH,
 * Befund 8), so tagging queues nothing; system tag events are not subscribed.
 * Folders are not expanded here: a folder rename inside a storage changes no
 * file id, and what a folder move across storages leaves behind the cache
 * events and the reconcile of the container pick up.
 *
 * Every check goes through QueueService::admissible, the one pre-check of the
 * crawl as well. A failure never reaches the operation of the user; the log
 * line carries the class of the error only, never a path or a name.
 *
 * @template-implements IEventListener<Event>
 */
class FileEventListener implements IEventListener {
	public function __construct(
		private QueueService $queueService,
		private StorageService $storageService,
		private IMimeTypeLoader $mimeTypeLoader,
		private LoggerInterface $logger,
	) {
	}

	public function handle(Event $event): void {
		try {
			if ($event instanceof NodeCreatedEvent || $event instanceof NodeWrittenEvent || $event instanceof NodeTouchedEvent) {
				$this->queueContent($event->getNode());
			} elseif ($event instanceof NodeCopiedEvent) {
				$this->queueContent($event->getTarget());
			} elseif ($event instanceof NodeRenamedEvent) {
				$this->queueRename($event->getSource(), $event->getTarget());
			} elseif ($event instanceof NodeDeletedEvent) {
				$this->queueDeletion($event->getNode());
			}
		} catch (\Throwable $e) {
			// The class only: the message of a file system error carries a path.
			$this->logger->warning('Audio & Video Search: a file event could not be queued', ['class' => $e::class]);
		}
	}

	private function queueContent(Node $node): void {
		$target = $this->admissibleFile($node);
		if ($target !== null) {
			$this->queueService->enqueue(QueueMapper::KIND_CONTENT, $target[0], $target[1]);
		}
	}

	private function queueRename(Node $source, Node $target): void {
		if (!$target instanceof File) {
			return;
		}
		$identity = self::identity($target);
		if ($identity === null) {
			return;
		}
		$admissible = $this->admissibleFile($target);
		$sourceIdentity = self::identity($source);
		if ($admissible === null) {
			// Renamed away from a media ending or out of the mount set: it leaves the work stock.
			$this->queueService->enqueue(QueueMapper::KIND_DELETE, $identity[0], $identity[1]);
			return;
		}

		if ($sourceIdentity === null || $sourceIdentity[1] === $identity[1]) {
			$this->queueService->enqueue(QueueMapper::KIND_METADATA, $identity[0], $identity[1]);
			return;
		}

		// Across storages: the content key decides, the bytes are the same, so
		// at most one download (RESEARCH, Befund 8).
		$this->queueService->enqueue(QueueMapper::KIND_CONTENT, $identity[0], $identity[1]);
		if ($sourceIdentity[0] !== $identity[0]) {
			$this->queueService->enqueue(QueueMapper::KIND_DELETE, $sourceIdentity[0], $sourceIdentity[1]);
		}
	}

	/**
	 * A deleted file leaves the work stock whatever its type says now: the
	 * media type decides what gets in, never what gets out.
	 */
	private function queueDeletion(Node $node): void {
		if (!$node instanceof File) {
			return;
		}
		$identity = self::identity($node);
		if ($identity !== null && $this->storageService->inMountSet($identity[1])) {
			$this->queueService->enqueue(QueueMapper::KIND_DELETE, $identity[0], $identity[1]);
		}
	}

	/**
	 * File id and storage id of an admissible media file, or null.
	 *
	 * @return array{0: int, 1: int}|null
	 */
	private function admissibleFile(Node $node): ?array {
		if (!$node instanceof File) {
			return null;
		}
		$identity = self::identity($node);
		if ($identity === null) {
			return null;
		}
		$mime = (string)$node->getMimetype();
		$mimeId = $mime !== '' && $this->mimeTypeLoader->exists($mime) ? $this->mimeTypeLoader->getId($mime) : 0;
		// In the space of the walk roots, not below the jail of a team folder.
		$storagePath = FileAccess::storagePath($node);
		$relative = $storagePath === null ? null : $this->storageService->mountRelativePath($identity[1], $storagePath);
		if ($relative === null || !$this->queueService->admissible($identity[1], $mimeId, $relative)) {
			return null;
		}

		return $identity;
	}

	/**
	 * File id and numeric storage id of a node, or null when either is not usable.
	 *
	 * @return array{0: int, 1: int}|null
	 */
	private static function identity(Node $node): ?array {
		try {
			$fileId = (int)$node->getId();
			$storageId = (int)$node->getMountPoint()->getNumericStorageId();
		} catch (\Throwable) {
			// The source of a rename may no longer resolve.
			return null;
		}

		return $fileId > 0 && $storageId > 0 ? [$fileId, $storageId] : null;
	}
}
