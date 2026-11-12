<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Db;

use OCP\AppFramework\Utility\ITimeFactory;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

/**
 * The classification of a storage in avs_storage (D-02-03, plan 02-12).
 *
 * One row per storage id. StorageClassifier writes it, QueueService reads it
 * for every file it is asked about, so a read is remembered for MEMO_SECONDS
 * and forgotten as soon as this mapper writes the same storage. capturable
 * defaults to 0 in the schema: a storage without a row is never captured
 * (T-02-43).
 *
 * The row never holds a host, a share name or a path of the external server:
 * the share key is kept as its sha256 only. root_prefix is the root of the
 * configuration inside the share; it stays in the database of the instance
 * and is never handed out.
 */
class StorageStateMapper {
	public const TABLE = 'avs_storage';

	/** How long a read is remembered within one process. */
	public const MEMO_SECONDS = 60;

	/** @var array<int, array{at: int, state: ?array}> */
	private array $memo = [];

	public function __construct(
		private IDBConnection $db,
		private ITimeFactory $timeFactory,
	) {
	}

	/**
	 * @return array{storageId: int, mountId: ?int, provider: string, shareKeyHash: ?string, rootPrefix: ?string, authKind: ?string, capturable: bool, reason: ?string, users: int, checkedAt: ?int}|null
	 */
	public function find(int $storageId): ?array {
		$now = $this->timeFactory->getTime();
		$memo = $this->memo[$storageId] ?? null;
		if ($memo !== null && $now - $memo['at'] < self::MEMO_SECONDS) {
			return $memo['state'];
		}

		$qb = $this->db->getQueryBuilder();
		$qb->select('storage_id', 'mount_id', 'provider', 'share_key_hash', 'root_prefix', 'auth_kind', 'capturable', 'reason', 'users', 'checked_at')
			->from(self::TABLE)
			->where($qb->expr()->eq('storage_id', $qb->createNamedParameter($storageId, IQueryBuilder::PARAM_INT)));
		$result = $qb->executeQuery();
		$row = $result->fetch();
		$result->closeCursor();
		$state = $row === false ? null : self::state($row);
		$this->memo[$storageId] = ['at' => $now, 'state' => $state];

		return $state;
	}

	/**
	 * Write the classification of one storage, a new row or over the old one.
	 * rescanned_at is not touched (markRescanned() owns it).
	 *
	 * @param array{storageId: int, mountId: ?int, provider: string, shareKeyHash: ?string, rootPrefix: ?string, authKind: ?string, capturable: bool, reason: ?string, users: int, checkedAt: ?int} $state
	 */
	public function store(array $state): void {
		$storageId = $state['storageId'];
		unset($this->memo[$storageId]);
		$values = [
			'mount_id' => $state['mountId'],
			'provider' => substr($state['provider'], 0, 64),
			'share_key_hash' => $state['shareKeyHash'],
			'root_prefix' => $state['rootPrefix'],
			'auth_kind' => $state['authKind'] === null ? null : substr($state['authKind'], 0, 64),
			'capturable' => $state['capturable'] ? 1 : 0,
			'reason' => $state['reason'],
			'users' => max(0, $state['users']),
			'checked_at' => $state['checkedAt'],
		];

		$inserted = $this->db->insertIgnoreConflict(self::TABLE, ['storage_id' => $storageId] + $values);
		if ($inserted > 0) {
			return;
		}

		$qb = $this->db->getQueryBuilder();
		$qb->update(self::TABLE);
		foreach ($values as $column => $value) {
			$qb->set($column, $qb->createNamedParameter(
				$value,
				match (true) {
					$value === null => IQueryBuilder::PARAM_NULL,
					is_int($value) => IQueryBuilder::PARAM_INT,
					default => IQueryBuilder::PARAM_STR,
				},
			));
		}
		$qb->where($qb->expr()->eq('storage_id', $qb->createNamedParameter($storageId, IQueryBuilder::PARAM_INT)));
		$qb->executeStatement();
	}

	/**
	 * Every storage that is classified and not capturable, ordered by mount
	 * configuration and storage, for occ audio_video_search:status.
	 *
	 * @return list<array{storageId: int, mountId: ?int, provider: string, shareKeyHash: ?string, rootPrefix: ?string, authKind: ?string, capturable: bool, reason: ?string, users: int, checkedAt: ?int}>
	 */
	public function skipped(): array {
		$qb = $this->db->getQueryBuilder();
		$qb->select('storage_id', 'mount_id', 'provider', 'share_key_hash', 'root_prefix', 'auth_kind', 'capturable', 'reason', 'users', 'checked_at')
			->from(self::TABLE)
			->where($qb->expr()->eq('capturable', $qb->createNamedParameter(0, IQueryBuilder::PARAM_INT)))
			->orderBy('mount_id', 'ASC')
			->addOrderBy('storage_id', 'ASC');
		$result = $qb->executeQuery();
		$rows = [];
		while (($row = $result->fetch()) !== false) {
			$rows[] = self::state($row);
		}
		$result->closeCursor();

		return $rows;
	}

	/**
	 * Every capturable storage with the hash of its share key and the time of
	 * its last complete rescan (null: never), ordered by storage, for
	 * RescanService (plan 02-14). Not remembered: the rescan asks once per run.
	 *
	 * @return list<array{storageId: int, shareKeyHash: ?string, rescannedAt: ?int}>
	 */
	public function rescanCandidates(): array {
		$qb = $this->db->getQueryBuilder();
		$qb->select('storage_id', 'share_key_hash', 'rescanned_at')
			->from(self::TABLE)
			->where($qb->expr()->eq('capturable', $qb->createNamedParameter(1, IQueryBuilder::PARAM_INT)))
			->orderBy('storage_id', 'ASC');
		$result = $qb->executeQuery();
		$rows = [];
		while (($row = $result->fetch()) !== false) {
			$rows[] = [
				'storageId' => (int)$row['storage_id'],
				'shareKeyHash' => $row['share_key_hash'] === null ? null : (string)$row['share_key_hash'],
				'rescannedAt' => $row['rescanned_at'] === null ? null : (int)$row['rescanned_at'],
			];
		}
		$result->closeCursor();

		return $rows;
	}

	/**
	 * Note the end of a complete rescan. Only a capturable storage carries
	 * the mark; the classification itself is not touched.
	 */
	public function markRescanned(int $storageId, int $at): void {
		$qb = $this->db->getQueryBuilder();
		$qb->update(self::TABLE)
			->set('rescanned_at', $qb->createNamedParameter($at, IQueryBuilder::PARAM_INT))
			->where($qb->expr()->eq('storage_id', $qb->createNamedParameter($storageId, IQueryBuilder::PARAM_INT)))
			->andWhere($qb->expr()->eq('capturable', $qb->createNamedParameter(1, IQueryBuilder::PARAM_INT)));
		$qb->executeStatement();
	}

	/**
	 * @param array<string, mixed> $row
	 * @return array{storageId: int, mountId: ?int, provider: string, shareKeyHash: ?string, rootPrefix: ?string, authKind: ?string, capturable: bool, reason: ?string, users: int, checkedAt: ?int}
	 */
	private static function state(array $row): array {
		return [
			'storageId' => (int)$row['storage_id'],
			'mountId' => $row['mount_id'] === null ? null : (int)$row['mount_id'],
			'provider' => (string)$row['provider'],
			'shareKeyHash' => $row['share_key_hash'] === null ? null : (string)$row['share_key_hash'],
			'rootPrefix' => $row['root_prefix'] === null ? null : (string)$row['root_prefix'],
			'authKind' => $row['auth_kind'] === null ? null : (string)$row['auth_kind'],
			'capturable' => (int)$row['capturable'] === 1,
			'reason' => $row['reason'] === null ? null : (string)$row['reason'],
			'users' => (int)$row['users'],
			'checkedAt' => $row['checked_at'] === null ? null : (int)$row['checked_at'],
		];
	}
}
