<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Db\StorageStateMapper;
use OCP\Files\Cache\IFileAccess;
use OCP\Files\Config\IUserMountCache;
use OCP\Files\File;
use OCP\Files\IMimeTypeLoader;
use OCP\Files\IRootFolder;
use Psr\Log\LoggerInterface;

/**
 * What goes into the work stock and what comes out of it.
 *
 * admissible() is the one pre-check of the discovery: event, crawl, reconcile
 * and the hand over all ask it, so they cannot disagree about a file. It holds
 * the exclusions (plan 02-16: an excluded file never enters the work stock,
 * D-02-05) and the capturability of external storages (plan 02-12: no
 * avs_storage row or capturable 0 means never queued and never handed out).
 *
 * describe() asks again when a claimed row is handed to the container, because
 * minutes may lie between queueing and claiming; a row whose file is no longer
 * admissible is dropped there and counted, never handed out.
 *
 * The exclusions are checked three times on purpose, each time through
 * ExclusionService and with the rules of that moment: here when a file is
 * queued, here again when its row is handed out, and in the content gateway
 * when the container asks for the bytes. An admin may set a rule at any time,
 * and between each two of these steps minutes or hours may pass; a file that
 * was admissible when it was queued must still not be loaded once a rule
 * covers it (T-02-57).
 *
 * What leaves this class is a fixed set of nine keys with ids and numbers
 * only: no path, no file name, no mount point (T-02-09).
 */
class QueueService {
	/** The keys of one item, in this order, and no other. */
	public const ITEM_KEYS = ['queueId', 'kind', 'fileId', 'storageId', 'etag', 'size', 'mtime', 'prefilterKey', 'readerUid'];

	/** Kinds whose file has to be there and admissible when the row is handed out. */
	private const NEEDS_FILE = [QueueMapper::KIND_CONTENT, QueueMapper::KIND_METADATA, QueueMapper::KIND_RESTORE];

	/** How many members of a team folder are asked before the reader stays unknown. */
	public const MAX_READER_TRIES = 5;

	public function __construct(
		private QueueMapper $queueMapper,
		private StorageService $storageService,
		private IFileAccess $fileAccess,
		private IMimeTypeLoader $mimeTypeLoader,
		private IUserMountCache $userMountCache,
		private IRootFolder $rootFolder,
		private ReaderContext $readerContext,
		private LoggerInterface $logger,
		private StorageStateMapper $storageStates,
		private ExclusionService $exclusions,
	) {
	}

	/**
	 * May a file of this storage, with this media type and this path below the
	 * walk root, enter the work stock? Cheap, no remote access.
	 *
	 * $mountRelativePath is the space the folder exclusions are written in.
	 * First check of three (see the class comment): an excluded file is never
	 * queued. The exclusions are asked before the classification, so nothing
	 * is looked up about a storage that is left out anyway.
	 */
	public function admissible(int $storageId, int $mimeId, string $mountRelativePath): bool {
		if ($storageId <= 0 || $mimeId <= 0 || $mountRelativePath === '') {
			return false;
		}
		if (!in_array($mimeId, $this->storageService->allowedMimeIds(), true)) {
			return false;
		}

		if (!$this->storageService->inMountSet($storageId)) {
			return false;
		}
		if ($this->exclusions->isExcluded($storageId, $mountRelativePath)) {
			return false;
		}

		return $this->storageCapturable($storageId);
	}

	/**
	 * May the files of a storage of the mount set be captured? Homes and team
	 * folders always; an external storage only with a row in avs_storage that
	 * says capturable. Without a row it never is (T-02-43).
	 */
	public function storageCapturable(int $storageId): bool {
		if (!$this->storageService->isExternal($storageId)) {
			return true;
		}
		$state = $this->storageStates->find($storageId);

		return $state !== null && $state['capturable'];
	}

	public function enqueue(string $kind, ?int $fileId, int $storageId): void {
		$this->queueMapper->enqueue($kind, $fileId, $storageId);
	}

	/**
	 * @return list<array{id: int, kind: string, fileId: ?int, storageId: int, attempts: int}>
	 */
	public function claim(int $limit, string $token): array {
		return $this->queueMapper->claim($limit, $token);
	}

	/** @param list<int> $ids */
	public function acknowledge(string $token, array $ids): int {
		return $this->queueMapper->acknowledge($token, $ids);
	}

	/** @param list<int> $ids */
	public function unlock(string $token, array $ids): int {
		return $this->queueMapper->unlock($token, $ids);
	}

	/**
	 * The items for the container, checked a second time. Rows that are no
	 * longer admissible are deleted under the claim token and counted.
	 *
	 * @param list<array{id: int, kind: string, fileId: ?int, storageId: int, attempts: int}> $rows
	 * @return array{items: list<array<string, int|string|null>>, dropped: int}
	 */
	public function describe(string $token, array $rows): array {
		$items = [];
		$dropped = [];
		foreach ($rows as $row) {
			$item = $this->describeRow($row);
			if ($item === null) {
				$dropped[] = $row['id'];
				continue;
			}
			$items[] = $item;
		}

		$removed = $this->queueMapper->drop($token, $dropped);
		if ($removed > 0) {
			$this->logger->info('Audio & Video Search: claimed rows no longer admissible, dropped', ['count' => $removed]);
		}

		return ['items' => $items, 'dropped' => $removed];
	}

	/**
	 * @param array{id: int, kind: string, fileId: ?int, storageId: int, attempts: int} $row
	 * @return array<string, int|string|null>|null
	 */
	private function describeRow(array $row): ?array {
		$item = array_fill_keys(self::ITEM_KEYS, null);
		$item['queueId'] = $row['id'];
		$item['kind'] = $row['kind'];
		$item['fileId'] = $row['fileId'];
		$item['storageId'] = $row['storageId'];
		if ($row['kind'] === QueueMapper::KIND_DELETE && $row['fileId'] !== null && $this->liesInTheTrashBin($row['fileId'])) {
			$item['kind'] = QueueMapper::KIND_TRASH;
		}
		if (!in_array($row['kind'], self::NEEDS_FILE, true)) {
			return $item;
		}

		$fileId = $row['fileId'];
		if ($fileId === null) {
			return null;
		}
		$entry = $this->fileAccess->getByFileId($fileId);
		if ($entry === null) {
			return null;
		}
		$storageId = (int)$entry->getStorageId();
		$mime = $entry->getMimeType();
		$mimeId = $this->mimeTypeLoader->exists($mime) ? $this->mimeTypeLoader->getId($mime) : 0;
		$relative = $this->storageService->mountRelativePath($storageId, (string)$entry->getPath());
		// Second check of three: admissible() asks the exclusions again with
		// the rules of now, so a row queued before a rule existed is dropped.
		if ($relative === null || !$this->admissible($storageId, $mimeId, $relative)) {
			return null;
		}

		$item['storageId'] = $storageId;
		$item['etag'] = (string)$entry->getEtag();
		$item['size'] = (int)$entry->getSize();
		$item['mtime'] = (int)$entry->getStorageMTime();
		$item['prefilterKey'] = $this->prefilterKey($storageId, (string)$entry->getPath(), (int)$entry->getSize(), (int)$entry->getStorageMTime());
		$item['readerUid'] = $this->readerUid($storageId, $fileId);

		return $item;
	}

	/**
	 * Was the deletion of this file a move into the trash bin? Decided at the
	 * cache entry when the row is handed out, not by the event (plan 02-18,
	 * T-02-68): NodeDeletedEvent comes for both, and the trash bin keeps the
	 * file id and moves its row out of every walk root of the same storage
	 * (files_trashbin/files of a home, the trash of a team folder). A file
	 * gone from the cache, or now on a storage outside the mount set, was
	 * deleted. A cache that cannot be asked keeps the deletion: no hit either
	 * way, the content is only marked (D-02-13).
	 */
	private function liesInTheTrashBin(int $fileId): bool {
		try {
			$entry = $this->fileAccess->getByFileId($fileId);
			if ($entry === null) {
				return false;
			}
			$storageId = (int)$entry->getStorageId();

			return $this->storageService->inMountSet($storageId)
				&& $this->storageService->mountRelativePath($storageId, (string)$entry->getPath()) === null;
		} catch (\Throwable $e) {
			$this->logger->debug('Audio & Video Search: a deleted file could not be looked up, handed out as deleted', ['class' => $e::class]);

			return false;
		}
	}

	/**
	 * The prefilter key of a file on a grouped share (SMB, SFTP), from the
	 * share key hash and root prefix the classification stored; null for
	 * every other storage. Built here, so no path reaches the container.
	 */
	private function prefilterKey(int $storageId, string $internalPath, int $size, int $storageMtime): ?string {
		if (!$this->storageService->isExternal($storageId)) {
			return null;
		}
		$state = $this->storageStates->find($storageId);
		if ($state === null || $state['shareKeyHash'] === null) {
			return null;
		}

		return StorageService::prefilterKey($state['shareKeyHash'], $state['rootPrefix'] ?? '', $internalPath, $size, $storageMtime);
	}

	/**
	 * The user the container reads this file as.
	 *
	 * A home has one user, its owner. An external storage built per user (one
	 * user in oc_mounts, e.g. SMB with the login of each user) belongs to that
	 * user, who is its reader (D-02-11). A team folder and an external storage
	 * mounted for several users are one storage for all of them, and ACLs or
	 * the external server may hide a file from some, so the first user for
	 * whom FileAccess::readableFile says yes inside ReaderContext::actAs is the
	 * reader, at most MAX_READER_TRIES users per file. Nobody found: null, and
	 * the container cannot read the file.
	 */
	public function readerUid(int $storageId, int $fileId): ?string {
		$mounts = $this->userMountCache->getMountsForStorageId($storageId);
		$uids = [];
		$external = true;
		foreach ($mounts as $mount) {
			$uid = $mount->getUser()->getUID();
			if ($uid === '') {
				continue;
			}
			$provider = $mount->getMountProvider();
			if (in_array($provider, StorageService::HOME_MOUNT_PROVIDERS, true)) {
				return $uid;
			}
			if ($provider !== StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER) {
				$external = false;
			}
			if (!in_array($uid, $uids, true)) {
				$uids[] = $uid;
			}
		}
		if ($external && count($uids) === 1) {
			return $uids[0];
		}

		foreach (array_slice($uids, 0, self::MAX_READER_TRIES) as $uid) {
			try {
				$file = $this->readerContext->actAs(
					$uid,
					fn (): ?File => FileAccess::readableFile($this->rootFolder->getUserFolder($uid), $fileId),
				);
			} catch (\Throwable $e) {
				$this->logger->debug('Audio & Video Search: a member could not be asked as reader', ['exception' => $e]);
				continue;
			}
			if ($file !== null) {
				return $uid;
			}
		}

		return null;
	}

	/**
	 * Rows per kind of the PHP work stock. ok is false when the table could not
	 * be read; the reconcile of the container treats that as a reason to wait.
	 *
	 * @return array{ok: bool, open: array<string, int>}
	 */
	public function stats(): array {
		try {
			return ['ok' => true, 'open' => $this->queueMapper->openByKind()];
		} catch (\Throwable $e) {
			$this->logger->error('Audio & Video Search: the work stock could not be counted', ['exception' => $e]);

			return ['ok' => false, 'open' => array_fill_keys(QueueMapper::KINDS, 0)];
		}
	}
}
