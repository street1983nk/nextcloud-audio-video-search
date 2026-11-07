<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCP\Files\Cache\ICacheEntry;
use OCP\Files\Cache\IFileAccess;
use OCP\IDBConnection;

/**
 * The only place in this app that enumerates mounts and files (after Findling).
 *
 * Both enumerations go through IFileAccess (NC 32+, public): getDistinctMounts
 * gives every mount once per (storage, root) and not once per user, and
 * getByAncestorInStorage gives the files of one mount in slices, with the
 * media type filter inside the query. Event, crawl, reconcile and diagnosis
 * all ask here, so "what lies in this mount" has one answer (RESEARCH,
 * Pitfall 10).
 *
 * The mount set of this plan is homes and team folders. External storages join
 * it in plan 02-12 together with their classification (D-02-03); until then a
 * storage of files_external is never admissible.
 */
class StorageService {
	/**
	 * A storage of these providers is the home of exactly one user.
	 *
	 * @var list<string>
	 */
	public const HOME_MOUNT_PROVIDERS = [
		'OC\Files\Mount\LocalHomeMountProvider',
		'OC\Files\Mount\ObjectHomeMountProvider',
	];

	/** Team folders: one storage and one file id per file for all members. */
	private const TEAM_FOLDER_MOUNT_PROVIDER = 'OCA\GroupFolders\Mount\MountProvider';

	/** How many file ids one slice carries at most. */
	public const MAX_SLICE = 1000;

	/** @var list<int>|null */
	private ?array $mimeIds = null;

	/** @var array<int, list<array{rootId: int, rootPath: string}>>|null */
	private ?array $roots = null;

	public function __construct(
		private IFileAccess $fileAccess,
		private IDBConnection $db,
	) {
	}

	/**
	 * The mount providers of the mount set. The one place the list is composed.
	 *
	 * @return list<string>
	 */
	public function providers(): array {
		return [...self::HOME_MOUNT_PROVIDERS, self::TEAM_FOLDER_MOUNT_PROVIDER];
	}

	/**
	 * Every mount of the mount set, once per (storage, root). onlyUserFilesMounts
	 * bends the root of a home to its files folder, so trash bin and versions
	 * never show up.
	 *
	 * @return iterable<array{storage_id: int, root_id: int, overridden_root: int}>
	 */
	public function getMounts(): iterable {
		return $this->fileAccess->getDistinctMounts($this->providers(), true);
	}

	/**
	 * The walk roots of one storage in the mount set, with their internal path.
	 * Read once per instance of this service, like Findling's isIndexedStorage.
	 *
	 * @return list<array{rootId: int, rootPath: string}>
	 */
	public function mountRoots(int $storageId): array {
		if ($this->roots === null) {
			$roots = [];
			foreach ($this->getMounts() as $mount) {
				$storage = (int)$mount['storage_id'];
				$root = (int)$mount['overridden_root'];
				$entry = $this->fileAccess->getByFileIdInStorage($root, $storage);
				$roots[$storage][] = ['rootId' => $root, 'rootPath' => $entry === null ? '' : (string)$entry->getPath()];
			}
			$this->roots = $roots;
		}

		return $this->roots[$storageId] ?? [];
	}

	public function inMountSet(int $storageId): bool {
		return $this->mountRoots($storageId) !== [];
	}

	/**
	 * The path of a file relative to the walk root of its mount, or null when
	 * the storage is not in the mount set or the file lies outside every walk
	 * root of it (trash bin and versions of a home share the storage of its
	 * files folder). The longest matching root wins. Never logged.
	 */
	public function mountRelativePath(int $storageId, string $internalPath): ?string {
		$best = null;
		foreach ($this->mountRoots($storageId) as $root) {
			$prefix = $root['rootPath'];
			if ($prefix === '') {
				$relative = $internalPath;
			} elseif ($internalPath === $prefix) {
				$relative = '';
			} elseif (str_starts_with($internalPath, $prefix . '/')) {
				$relative = substr($internalPath, strlen($prefix) + 1);
			} else {
				continue;
			}
			if ($best === null || strlen($prefix) > $best[0]) {
				$best = [strlen($prefix), $relative];
			}
		}

		return $best === null ? null : $best[1];
	}

	/**
	 * One slice of the media files below a walk root, file ids after
	 * $afterFileId in ascending order. The crawl, the reconcile and the clearing
	 * of an excluded folder all read through this method.
	 *
	 * @return list<ICacheEntry>
	 */
	public function getFileSlice(int $storageId, int $rootId, int $afterFileId, int $limit): array {
		$limit = max(1, min($limit, self::MAX_SLICE));
		$mimeIds = $this->allowedMimeIds();
		if ($mimeIds === []) {
			return [];
		}

		$entries = [];
		foreach ($this->fileAccess->getByAncestorInStorage($storageId, $rootId, $afterFileId, $limit, $mimeIds, false, true) as $entry) {
			$entries[] = $entry;
		}

		return $entries;
	}

	/**
	 * Every media type id of this instance: audio/* and video/*, case blind
	 * (mts is stored as video/MP2T). Every format of MEDIA-01 carries one of
	 * the two (RESEARCH, Befund 2), so there is no list to keep. A type the
	 * instance sees for the first time joins with the next process; the
	 * reconcile picks up what was missed.
	 *
	 * @return list<int>
	 */
	public function allowedMimeIds(): array {
		if ($this->mimeIds !== null) {
			return $this->mimeIds;
		}

		$qb = $this->db->getQueryBuilder();
		$qb->select('id')
			->from('mimetypes')
			->where($qb->expr()->orX(
				$qb->expr()->iLike('mimetype', $qb->createNamedParameter('audio/%')),
				$qb->expr()->iLike('mimetype', $qb->createNamedParameter('video/%')),
			))
			->orderBy('id', 'ASC');
		$result = $qb->executeQuery();
		$ids = [];
		while (($row = $result->fetch()) !== false) {
			$ids[] = (int)$row['id'];
		}
		$result->closeCursor();
		$this->mimeIds = $ids;

		return $ids;
	}
}
