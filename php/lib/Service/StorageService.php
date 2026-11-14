<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCP\DB\QueryBuilder\IQueryBuilder;
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
 * The mount set is homes, team folders and external storages (DISC-02, ab
 * Werk). An external storage is in the mount set, but admissible only once
 * StorageClassifier has found it capturable (QueueService::admissible,
 * D-02-03).
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

	/** External storages of files_external: built per user from a mount configuration. */
	public const EXTERNAL_STORAGE_MOUNT_PROVIDER = 'OCA\Files_External\Config\ConfigAdapter';

	/** How many file ids one slice carries at most. */
	public const MAX_SLICE = 1000;

	/** How many storage ids one lookup in oc_storages carries (Findling). */
	public const ABSENT_LOOKUP_BAND = 200;

	/** @var list<int>|null */
	private ?array $mimeIds = null;

	/** @var array<int, list<array{rootId: int, rootPath: string}>>|null */
	private ?array $roots = null;

	/** @var array<int, true>|null */
	private ?array $external = null;

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
		return [...self::HOME_MOUNT_PROVIDERS, self::TEAM_FOLDER_MOUNT_PROVIDER, self::EXTERNAL_STORAGE_MOUNT_PROVIDER];
	}

	/**
	 * Is this storage an external storage of the mount set? Read once per
	 * instance of this service, like mountRoots().
	 */
	public function isExternal(int $storageId): bool {
		if ($this->external === null) {
			$external = [];
			foreach ($this->fileAccess->getDistinctMounts([self::EXTERNAL_STORAGE_MOUNT_PROVIDER], true) as $mount) {
				$external[(int)$mount['storage_id']] = true;
			}
			$this->external = $external;
		}

		return isset($this->external[$storageId]);
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
	 * Which of the asked storages the container may forget at once (plan
	 * 02-19, after Findling classifyAbsent, T-02-70).
	 *
	 * The container asks this for storages it holds references of and no
	 * longer finds in the mount list. It must never delete out of an empty or
	 * disturbed mount list alone, so only this side decides:
	 *
	 * - gone: no row in oc_storages. The user or the external storage was
	 *   deleted, nothing will mount it again.
	 * - deselected: the row is there, but the storage is not in the mount set
	 *   (getMounts) or $capturable says no (an external storage the
	 *   classification left out). A decision of the admin or of the
	 *   classification, like an exclusion.
	 * - present: everything else; the container keeps its references.
	 *
	 * Only positive asked ids come back, each once and in ascending order. The
	 * lookup runs in bands of ABSENT_LOOKUP_BAND ids; $capturable is asked for
	 * storages of the mount set only. Numbers in, numbers out: no path, no
	 * storage key, no user.
	 *
	 * @param list<int> $storageIds
	 * @param \Closure(int): bool $capturable
	 * @return array{gone: list<int>, deselected: list<int>, present: list<int>}
	 */
	public function classifyAbsent(array $storageIds, \Closure $capturable): array {
		$wanted = [];
		foreach ($storageIds as $storageId) {
			if (is_int($storageId) && $storageId > 0) {
				$wanted[$storageId] = true;
			}
		}
		$wanted = array_keys($wanted);
		sort($wanted);
		$answer = ['gone' => [], 'deselected' => [], 'present' => []];
		if ($wanted === []) {
			return $answer;
		}

		$existing = [];
		foreach (array_chunk($wanted, self::ABSENT_LOOKUP_BAND) as $band) {
			$qb = $this->db->getQueryBuilder();
			$qb->select('numeric_id')
				->from('storages')
				->where($qb->expr()->in('numeric_id', $qb->createNamedParameter($band, IQueryBuilder::PARAM_INT_ARRAY)));
			$result = $qb->executeQuery();
			try {
				while (($row = $result->fetch()) !== false) {
					$existing[(int)$row['numeric_id']] = true;
				}
			} finally {
				$result->closeCursor();
			}
		}

		foreach ($wanted as $storageId) {
			if (!isset($existing[$storageId])) {
				$answer['gone'][] = $storageId;
			} elseif (!$this->inMountSet($storageId) || !$capturable($storageId)) {
				$answer['deselected'][] = $storageId;
			} else {
				$answer['present'][] = $storageId;
			}
		}

		return $answer;
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

	/**
	 * How many media rows oc_filecache holds for one storage. A number to
	 * order the rescan of external storages by (plan 02-14), nothing is read
	 * from the rows. One query per storage, on the storage column alone, so
	 * it also works on a sharded file cache.
	 */
	public function mediaRows(int $storageId): int {
		$mimeIds = $this->allowedMimeIds();
		if ($mimeIds === []) {
			return 0;
		}

		$qb = $this->db->getQueryBuilder();
		$qb->selectAlias($qb->func()->count('*'), 'media_rows')
			->from('filecache')
			->where($qb->expr()->eq('storage', $qb->createNamedParameter($storageId, IQueryBuilder::PARAM_INT)))
			->andWhere($qb->expr()->in('mimetype', $qb->createNamedParameter($mimeIds, IQueryBuilder::PARAM_INT_ARRAY)));
		$result = $qb->executeQuery();
		$row = $result->fetch();
		$result->closeCursor();

		return $row === false ? 0 : (int)$row['media_rows'];
	}

	/**
	 * The share key of a storage id string and the root of its configuration
	 * inside the share, or null when copies on this storage are never grouped.
	 *
	 * Only SMB and SFTP are grouped: their id names login, host, share and
	 * root, so the copies of all users of one share meet on one key once the
	 * login is cut off. The host is the text after the last @ before the first
	 * //, so a login name with its own @ stays out (Findling countingKey). The
	 * root moves into the path: two configurations of the same share with
	 * different roots meet as well. Everything else (S3, local, WebDAV, homes,
	 * object stores, a failed storage) is never grouped, which is correct and
	 * only costs a hash per copy.
	 *
	 * $storageId must be the full string of the storage object
	 * (IStorage::getId() after the setup of its user), never oc_storages.id:
	 * that column keeps an md5 above 64 characters (02-RESEARCH.md Befund 6).
	 * The share key names a host; it is kept as shareKeyHash() only.
	 *
	 * @return array{0: string, 1: string}|null [share key, root prefix]
	 */
	public static function shareKey(string $storageId): ?array {
		if (str_contains($storageId, "\0")) {
			return null;
		}
		foreach (['smb::', 'sftp::'] as $prefix) {
			if (!str_starts_with($storageId, $prefix)) {
				continue;
			}
			$rest = substr($storageId, strlen($prefix));
			$split = strpos($rest, '//');
			if ($split === false || $split === 0) {
				return null;
			}
			$login = substr($rest, 0, $split);
			$at = strrpos($login, '@');
			$host = $at === false ? '' : substr($login, $at + 1);
			if ($host === '') {
				return null;
			}
			// smb: "<share>/<root>", sftp: "<root>"
			$tail = substr($rest, $split + 2);
			if ($prefix === 'smb::') {
				$slash = strpos($tail, '/');
				$share = $slash === false ? $tail : substr($tail, 0, $slash);
				$root = $slash === false ? '' : substr($tail, $slash);
				if ($share === '') {
					return null;
				}

				return ['smb::' . $host . '//' . $share, trim($root, '/')];
			}

			return ['sftp::' . $host, trim($tail, '/')];
		}

		return null;
	}

	/** What avs_storage keeps of a share key: its sha256, hex. */
	public static function shareKeyHash(string $shareKey): string {
		return hash('sha256', $shareKey);
	}

	/**
	 * The prefilter key of one file: sha256 over the hash of the share key,
	 * the path inside the share (root of the configuration plus internal
	 * path), the size and the storage mtime, with a zero byte between the
	 * fields. The container sees only this hash, never a path (T-02-40).
	 *
	 * storage mtime and not mtime: the time of the external server is the same
	 * for every user of the share, the mtime can be set per request. The etag
	 * is no part of it: Nextcloud gives every cache row of every user its own.
	 *
	 * null for a zero byte in a field, a share key hash that is no sha256, an
	 * unknown size or an empty path: then the copy is not grouped.
	 */
	public static function prefilterKey(string $shareKeyHash, string $rootPrefix, string $internalPath, int $size, int $storageMtime): ?string {
		if (preg_match('/^[0-9a-f]{64}$/', $shareKeyHash) !== 1 || $size < 0) {
			return null;
		}
		if (str_contains($rootPrefix, "\0") || str_contains($internalPath, "\0")) {
			return null;
		}
		$parts = array_values(array_filter(
			[trim($rootPrefix, '/'), trim($internalPath, '/')],
			static fn (string $part): bool => $part !== '',
		));
		if ($parts === [] || trim($internalPath, '/') === '') {
			return null;
		}

		return hash('sha256', implode("\0", [$shareKeyHash, implode('/', $parts), (string)$size, (string)$storageMtime]));
	}
}
