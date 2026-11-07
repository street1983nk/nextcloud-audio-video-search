<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Db;

use OCP\AppFramework\Utility\ITimeFactory;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

/**
 * The work stock of the discovery up to the hand over, and the only place that
 * decides who owns a row (after Findling's QueueMapper).
 *
 * Three properties carry it. A claim is a conditional update and nothing else:
 * candidates are read without a lock, then one update repeats the free condition
 * in its WHERE clause and stamps the winners with a claim token, so two callers
 * never get the same row. A claim expires after LOCK_TIMEOUT, so a container
 * that is killed hard holds its rows for fifteen minutes and no longer. And an
 * acknowledgement deletes only what did not change in the meantime: a file that
 * changes while its row is claimed marks the row dirty, and the acknowledgement
 * frees it instead of deleting it.
 *
 * The lock is short and fixed because the container acknowledges as soon as the
 * reference is in its state.db, which takes seconds; downloads and
 * transcription run in the stages of the container (02-RESEARCH.md, Pattern 1).
 *
 * Rows are plain arrays: no entity class, the controller hands them to
 * QueueService::describe() and nothing else reads them.
 */
class QueueMapper {
	public const TABLE = 'avs_queue';

	public const KIND_EXCLUDE_STORAGE = 'exclude_storage';
	public const KIND_EXCLUDE = 'exclude';
	public const KIND_DELETE = 'delete';
	public const KIND_TRASH = 'trash';
	public const KIND_RESTORE = 'restore';
	public const KIND_CONTENT = 'content';
	public const KIND_METADATA = 'metadata';

	/**
	 * The closed list of kinds, in the order the claim hands them out:
	 * everything that removes a reference before anything that adds one, so a
	 * rule of the admin is applied before new work arrives (D-02-04).
	 *
	 * @var list<string>
	 */
	public const KINDS = [
		self::KIND_EXCLUDE_STORAGE,
		self::KIND_EXCLUDE,
		self::KIND_DELETE,
		self::KIND_TRASH,
		self::KIND_RESTORE,
		self::KIND_CONTENT,
		self::KIND_METADATA,
	];

	/**
	 * Which kinds a new row of the same file takes the place of. The last word
	 * about a file wins: content after delete brings the file back (a move
	 * across storages is a removal and an insertion with the same file id,
	 * Cache::moveFromCache), delete after content removes it. Findling's rule
	 * "delete absorbs everything" is deliberately not taken over (RESEARCH,
	 * Anti-Patterns).
	 *
	 * @var array<string, list<string>>
	 */
	private const REPLACES = [
		self::KIND_CONTENT => [self::KIND_DELETE, self::KIND_TRASH],
		self::KIND_DELETE => [self::KIND_CONTENT, self::KIND_METADATA, self::KIND_TRASH, self::KIND_RESTORE],
		self::KIND_TRASH => [self::KIND_RESTORE, self::KIND_CONTENT, self::KIND_METADATA],
		self::KIND_RESTORE => [self::KIND_TRASH],
	];

	/** Fifteen minutes, far above the seconds a hand over takes. */
	public const LOCK_TIMEOUT = 900;

	/** One claim, acknowledgement or unlock carries at most this many ids. */
	public const MAX_BATCH = 256;

	public function __construct(
		private IDBConnection $db,
		private ITimeFactory $timeFactory,
	) {
	}

	/**
	 * Queue a job, or mark the row that is already there.
	 *
	 * No select before the insert for a file: the unique index on
	 * (kind, file_id, storage_id) decides the race, and the conflict becomes a
	 * dirty mark when the row is claimed right now. A job about a whole storage
	 * has no file id, and NULL never conflicts in a unique index, so for those
	 * the existing row is looked up first; a duplicate there would only repeat
	 * an idempotent removal.
	 */
	public function enqueue(string $kind, ?int $fileId, int $storageId): void {
		if (!in_array($kind, self::KINDS, true)) {
			throw new \InvalidArgumentException('unknown queue kind');
		}

		$now = $this->timeFactory->getTime();
		if ($fileId !== null && isset(self::REPLACES[$kind])) {
			$replace = $this->db->getQueryBuilder();
			$replace->delete(self::TABLE)
				->where($replace->expr()->eq('file_id', $replace->createNamedParameter($fileId, IQueryBuilder::PARAM_INT)))
				->andWhere($replace->expr()->in('kind', $replace->createNamedParameter(self::REPLACES[$kind], IQueryBuilder::PARAM_STR_ARRAY)));
			$replace->executeStatement();
		}

		if ($fileId === null && $this->markExisting($kind, null, $storageId, $now)) {
			return;
		}

		$inserted = $this->db->insertIgnoreConflict(self::TABLE, [
			'kind' => $kind,
			'file_id' => $fileId,
			'storage_id' => $storageId,
			'enqueued_at' => $now,
			'locked_at' => null,
			'lock_token' => null,
			'dirty' => 0,
			'attempts' => 0,
		]);
		if ($inserted > 0) {
			return;
		}

		$this->markExisting($kind, $fileId, $storageId, $now);
	}

	/**
	 * The conflict branch: a claimed row becomes dirty, a free row stays as it
	 * is (it is waiting already). True when a row with this key exists.
	 */
	private function markExisting(string $kind, ?int $fileId, int $storageId, int $now): bool {
		$dirty = $this->db->getQueryBuilder();
		$dirty->update(self::TABLE)
			->set('dirty', $dirty->createNamedParameter(1, IQueryBuilder::PARAM_INT))
			->where($this->sameKey($dirty, $kind, $fileId, $storageId))
			->andWhere($dirty->expr()->gt('locked_at', $dirty->createNamedParameter($now - self::LOCK_TIMEOUT, IQueryBuilder::PARAM_INT)));
		if ($dirty->executeStatement() > 0) {
			return true;
		}

		$exists = $this->db->getQueryBuilder();
		$exists->select('id')
			->from(self::TABLE)
			->where($this->sameKey($exists, $kind, $fileId, $storageId))
			->setMaxResults(1);
		$result = $exists->executeQuery();
		$found = $result->fetchOne();
		$result->closeCursor();

		return $found !== false;
	}

	private function sameKey(IQueryBuilder $qb, string $kind, ?int $fileId, int $storageId): string {
		$file = $fileId === null
			? $qb->expr()->isNull('file_id')
			: $qb->expr()->eq('file_id', $qb->createNamedParameter($fileId, IQueryBuilder::PARAM_INT));

		return (string)$qb->expr()->andX(
			$qb->expr()->eq('kind', $qb->createNamedParameter($kind)),
			$file,
			$qb->expr()->eq('storage_id', $qb->createNamedParameter($storageId, IQueryBuilder::PARAM_INT)),
		);
	}

	/**
	 * Claim up to $limit rows under $token, kind after kind in the order of KINDS.
	 *
	 * Handing a row out counts as an attempt, counted in the database; the claim
	 * clears the dirty mark, because the state the container reads now is the
	 * state the row stands for.
	 *
	 * @return list<array{id: int, kind: string, fileId: ?int, storageId: int, attempts: int}>
	 */
	public function claim(int $limit, string $token): array {
		$limit = max(0, min($limit, self::MAX_BATCH));
		$now = $this->timeFactory->getTime();
		$cutoff = $now - self::LOCK_TIMEOUT;
		$claimed = 0;

		foreach (self::KINDS as $kind) {
			if ($claimed >= $limit) {
				break;
			}

			$candidates = $this->db->getQueryBuilder();
			$candidates->select('id')
				->from(self::TABLE)
				->where($candidates->expr()->eq('kind', $candidates->createNamedParameter($kind)))
				->andWhere($this->free($candidates, $cutoff))
				->orderBy('id', 'ASC')
				->setMaxResults($limit - $claimed);
			$result = $candidates->executeQuery();
			$ids = [];
			while (($row = $result->fetch()) !== false) {
				$ids[] = (int)$row['id'];
			}
			$result->closeCursor();
			if ($ids === []) {
				continue;
			}

			$update = $this->db->getQueryBuilder();
			$update->update(self::TABLE)
				->set('locked_at', $update->createNamedParameter($now, IQueryBuilder::PARAM_INT))
				->set('lock_token', $update->createNamedParameter($token))
				->set('dirty', $update->createNamedParameter(0, IQueryBuilder::PARAM_INT))
				->set('attempts', $update->createFunction('attempts + 1'))
				->where($update->expr()->in('id', $update->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)))
				->andWhere($update->expr()->eq('kind', $update->createNamedParameter($kind)))
				->andWhere($this->free($update, $cutoff));
			$claimed += $update->executeStatement();
		}

		if ($claimed === 0) {
			return [];
		}

		return $this->rowsOfToken($token);
	}

	/**
	 * The rows of one claim, in the order of KINDS and then of their id.
	 *
	 * @return list<array{id: int, kind: string, fileId: ?int, storageId: int, attempts: int}>
	 */
	public function rowsOfToken(string $token): array {
		$qb = $this->db->getQueryBuilder();
		$qb->select('id', 'kind', 'file_id', 'storage_id', 'attempts')
			->from(self::TABLE)
			->where($qb->expr()->eq('lock_token', $qb->createNamedParameter($token)))
			->orderBy('id', 'ASC');
		$result = $qb->executeQuery();
		$rows = [];
		while (($row = $result->fetch()) !== false) {
			$rows[] = [
				'id' => (int)$row['id'],
				'kind' => (string)$row['kind'],
				'fileId' => $row['file_id'] === null ? null : (int)$row['file_id'],
				'storageId' => (int)$row['storage_id'],
				'attempts' => (int)$row['attempts'],
			];
		}
		$result->closeCursor();

		$rank = array_flip(self::KINDS);
		usort($rows, static fn (array $a, array $b): int => [$rank[$a['kind']] ?? PHP_INT_MAX, $a['id']] <=> [$rank[$b['kind']] ?? PHP_INT_MAX, $b['id']]);

		return $rows;
	}

	/**
	 * Delete the acknowledged rows of one claim. A dirty row is freed instead,
	 * so the change that arrived during the claim is handed out again. Rows of
	 * another token are not touched (T-02-11).
	 *
	 * @param list<int> $ids
	 * @return int rows deleted
	 */
	public function acknowledge(string $token, array $ids): int {
		if ($ids === []) {
			return 0;
		}

		$delete = $this->db->getQueryBuilder();
		$delete->delete(self::TABLE)
			->where($delete->expr()->in('id', $delete->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)))
			->andWhere($delete->expr()->eq('lock_token', $delete->createNamedParameter($token)))
			->andWhere($delete->expr()->eq('dirty', $delete->createNamedParameter(0, IQueryBuilder::PARAM_INT)));
		$deleted = $delete->executeStatement();

		$free = $this->db->getQueryBuilder();
		$free->update(self::TABLE)
			->set('locked_at', $free->createNamedParameter(null, IQueryBuilder::PARAM_NULL))
			->set('lock_token', $free->createNamedParameter(null, IQueryBuilder::PARAM_NULL))
			->set('dirty', $free->createNamedParameter(0, IQueryBuilder::PARAM_INT))
			->where($free->expr()->in('id', $free->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)))
			->andWhere($free->expr()->eq('lock_token', $free->createNamedParameter($token)))
			->andWhere($free->expr()->eq('dirty', $free->createNamedParameter(1, IQueryBuilder::PARAM_INT)));
		$free->executeStatement();

		return $deleted;
	}

	/**
	 * Hand rows of one claim back unjudged. The attempt the claim counted is
	 * taken back first, while the row is still held, so the decrement is the
	 * one this claim put up.
	 *
	 * @param list<int> $ids
	 * @return int rows released
	 */
	public function unlock(string $token, array $ids): int {
		if ($ids === []) {
			return 0;
		}

		$refund = $this->db->getQueryBuilder();
		$refund->update(self::TABLE)
			->set('attempts', $refund->createFunction('attempts - 1'))
			->where($refund->expr()->in('id', $refund->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)))
			->andWhere($refund->expr()->eq('lock_token', $refund->createNamedParameter($token)))
			->andWhere($refund->expr()->gt('attempts', $refund->createNamedParameter(0, IQueryBuilder::PARAM_INT)));
		$refund->executeStatement();

		$free = $this->db->getQueryBuilder();
		$free->update(self::TABLE)
			->set('locked_at', $free->createNamedParameter(null, IQueryBuilder::PARAM_NULL))
			->set('lock_token', $free->createNamedParameter(null, IQueryBuilder::PARAM_NULL))
			->where($free->expr()->in('id', $free->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)))
			->andWhere($free->expr()->eq('lock_token', $free->createNamedParameter($token)));

		return $free->executeStatement();
	}

	/**
	 * Remove rows of one claim that are no longer admissible (QueueService::describe).
	 *
	 * @param list<int> $ids
	 */
	public function drop(string $token, array $ids): int {
		if ($ids === []) {
			return 0;
		}

		$qb = $this->db->getQueryBuilder();
		$qb->delete(self::TABLE)
			->where($qb->expr()->in('id', $qb->createNamedParameter($ids, IQueryBuilder::PARAM_INT_ARRAY)))
			->andWhere($qb->expr()->eq('lock_token', $qb->createNamedParameter($token)));

		return $qb->executeStatement();
	}

	/**
	 * Rows per kind, every kind present with its number (0 included).
	 *
	 * @return array<string, int>
	 */
	public function openByKind(): array {
		$open = array_fill_keys(self::KINDS, 0);
		$qb = $this->db->getQueryBuilder();
		$qb->select('kind')
			->selectAlias($qb->func()->count('*'), 'open_rows')
			->from(self::TABLE)
			->groupBy('kind');
		$result = $qb->executeQuery();
		while (($row = $result->fetch()) !== false) {
			$kind = (string)$row['kind'];
			if (isset($open[$kind])) {
				$open[$kind] = (int)$row['open_rows'];
			}
		}
		$result->closeCursor();

		return $open;
	}

	/**
	 * Free: never claimed, or claimed longer ago than the lock timeout. One
	 * expression for the candidates and the claim, so they cannot drift apart.
	 */
	private function free(IQueryBuilder $qb, int $cutoff): string {
		return (string)$qb->expr()->orX(
			$qb->expr()->isNull('locked_at'),
			$qb->expr()->lte('locked_at', $qb->createNamedParameter($cutoff, IQueryBuilder::PARAM_INT)),
		);
	}
}
