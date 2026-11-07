<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Db;

use OCP\AppFramework\Utility\ITimeFactory;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

/**
 * The first crawl of each mount: where it stands and whether it finished.
 *
 * One row per (storage_id, root_id), root_id being the folder the crawl walks
 * (the overridden root of StorageService::getMounts()). The crawl advances
 * last_file_id band by band; finished_at is what the reconcile of the
 * container waits for before it walks the mount (02-RESEARCH.md, Pattern 2).
 * reset() starts the crawl of a mount again with a new generation, for a lifted
 * exclusion or a storage that became capturable.
 */
class CrawlMapper {
	public const TABLE = 'avs_crawl';

	public function __construct(
		private IDBConnection $db,
		private ITimeFactory $timeFactory,
	) {
	}

	/**
	 * Make sure a row exists; an existing row is left exactly as it is.
	 *
	 * @return bool true when the row was created now
	 */
	public function upsert(int $storageId, int $rootId): bool {
		return $this->db->insertIgnoreConflict(self::TABLE, [
			'storage_id' => $storageId,
			'root_id' => $rootId,
			'last_file_id' => 0,
			'generation' => 0,
			'started_at' => $this->timeFactory->getTime(),
			'finished_at' => null,
		]) > 0;
	}

	/** Move the cursor forward; it never moves back. */
	public function advance(int $storageId, int $rootId, int $lastFileId): void {
		$qb = $this->db->getQueryBuilder();
		$qb->update(self::TABLE)
			->set('last_file_id', $qb->createNamedParameter($lastFileId, IQueryBuilder::PARAM_INT))
			->where($this->key($qb, $storageId, $rootId))
			->andWhere($qb->expr()->lt('last_file_id', $qb->createNamedParameter($lastFileId, IQueryBuilder::PARAM_INT)));
		$qb->executeStatement();
	}

	public function finish(int $storageId, int $rootId): void {
		$qb = $this->db->getQueryBuilder();
		$qb->update(self::TABLE)
			->set('finished_at', $qb->createNamedParameter($this->timeFactory->getTime(), IQueryBuilder::PARAM_INT))
			->where($this->key($qb, $storageId, $rootId));
		$qb->executeStatement();
	}

	/** Start over: cursor 0, a new generation, not finished. */
	public function reset(int $storageId, int $rootId): void {
		$this->upsert($storageId, $rootId);
		$qb = $this->db->getQueryBuilder();
		$qb->update(self::TABLE)
			->set('last_file_id', $qb->createNamedParameter(0, IQueryBuilder::PARAM_INT))
			->set('generation', $qb->createFunction('generation + 1'))
			->set('started_at', $qb->createNamedParameter($this->timeFactory->getTime(), IQueryBuilder::PARAM_INT))
			->set('finished_at', $qb->createNamedParameter(null, IQueryBuilder::PARAM_NULL))
			->where($this->key($qb, $storageId, $rootId));
		$qb->executeStatement();
	}

	/**
	 * @return array{storageId: int, rootId: int, lastFileId: int, generation: int, startedAt: ?int, finishedAt: ?int}|null
	 */
	public function find(int $storageId, int $rootId): ?array {
		$qb = $this->db->getQueryBuilder();
		$qb->select('storage_id', 'root_id', 'last_file_id', 'generation', 'started_at', 'finished_at')
			->from(self::TABLE)
			->where($this->key($qb, $storageId, $rootId));
		$result = $qb->executeQuery();
		$row = $result->fetch();
		$result->closeCursor();
		if ($row === false) {
			return null;
		}

		return [
			'storageId' => (int)$row['storage_id'],
			'rootId' => (int)$row['root_id'],
			'lastFileId' => (int)$row['last_file_id'],
			'generation' => (int)$row['generation'],
			'startedAt' => $row['started_at'] === null ? null : (int)$row['started_at'],
			'finishedAt' => $row['finished_at'] === null ? null : (int)$row['finished_at'],
		];
	}

	private function key(IQueryBuilder $qb, int $storageId, int $rootId): string {
		return (string)$qb->expr()->andX(
			$qb->expr()->eq('storage_id', $qb->createNamedParameter($storageId, IQueryBuilder::PARAM_INT)),
			$qb->expr()->eq('root_id', $qb->createNamedParameter($rootId, IQueryBuilder::PARAM_INT)),
		);
	}
}
