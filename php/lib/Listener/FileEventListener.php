<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Listener;

use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\FileAccess;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCA\Files_Trashbin\Events\MoveToTrashEvent;
use OCA\Files_Trashbin\Events\NodeRestoredEvent;
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
 * - deleted: delete; QueueService::describe hands it out as trash when the
 *   file id lies in the trash bin then (plan 02-18, T-02-68)
 * - moved to the trash bin (files_trashbin): trash; restored from it:
 *   restore. Without files_trashbin only the deletion comes, a delete.
 *
 * Forgetting an orphaned content after seven days, and the deletion of a
 * file from the trash bin, belong to phase 8 (D-02-13); until then the
 * content is only marked.
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
			} elseif ($event instanceof MoveToTrashEvent) {
				// instanceof loads no class: without files_trashbin both branches never match.
				$this->queueTrash($event->getNode());
			} elseif ($event instanceof NodeRestoredEvent) {
				$this->queueRestore($event->getTarget());
			}
		} catch (\Throwable $e) {
			// The class only: the message of a file system error carries a path.
			$this->logger->warning('Audio & Video Search: a file event could not be queued', ['class' => $e::class]);
		}
	}

	private function queueContent(Node $node): void {
		$target = $this->admissibleFile($node);
		if ($target !== null) {
			$this->queueService->enqueue(QueueMapper::KIND_CONTENT, $target[0], $target[1], QueueMapper::ORIGIN_EVENT);
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
		$this->queueService->enqueue(QueueMapper::KIND_CONTENT, $identity[0], $identity[1], QueueMapper::ORIGIN_EVENT);
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
	 * Into the trash bin: the reference is set aside and gives no hit, its
	 * content is only marked (D-02-09). MoveToTrashEvent comes before the move
	 * and NodeDeletedEvent after it; the delete of the second replaces this
	 * row, and QueueService::describe hands it out as trash again once it sees
	 * the file id in the trash bin. Like a deletion, whatever the type says.
	 */
	private function queueTrash(Node $node): void {
		if (!$node instanceof File) {
			return;
		}
		$identity = self::identity($node);
		if ($identity !== null && $this->storageService->inMountSet($identity[1])) {
			$this->queueService->enqueue(QueueMapper::KIND_TRASH, $identity[0], $identity[1]);
		}
	}

	/**
	 * Out of the trash bin: restore, which the container answers without a
	 * download when the bytes are the same (D-02-09, plan 02-15b for SMB and
	 * SFTP). Restored to a place the work stock does not take, the file leaves.
	 */
	private function queueRestore(Node $target): void {
		$admissible = $this->admissibleFile($target);
		if ($admissible !== null) {
			$this->queueService->enqueue(QueueMapper::KIND_RESTORE, $admissible[0], $admissible[1]);
			return;
		}
		$this->queueDeletion($target);
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
