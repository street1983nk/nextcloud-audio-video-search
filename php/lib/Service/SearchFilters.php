<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCP\DB\QueryBuilder\ICompositeExpression;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\Files\File;
use OCP\IDBConnection;
use OCP\IGroup;
use OCP\IUser;
use OCP\Search\IFilter;
use OCP\Search\ISearchQuery;
use OCP\Share\IShare;
use Psr\Log\LoggerInterface;

/**
 * The date and person filters of the unified search, with the meaning the
 * Files search gives them.
 *
 * The date bounds compare the modification time (mtime) of the media file,
 * inclusive at both ends, exactly like the Files search with its
 * greater-than-equal and less-than-equal comparisons on mtime (D-04-09). No
 * recording date out of any metadata is read.
 *
 * The person is the condition of FilesSearchProvider: the server turns its
 * owner comparison into uid_owner of the share table, and
 * QuerySearchHelper::equipQueryForShares joins that table with an INNER join
 * on file.fileid = s.file_source (stable33 to stable35 are identical,
 * 04-RESEARCH). A file counts when a share row with file_source = fileId
 * exists and uid_owner is the person, or share_with is the person at
 * share_type USER; for a group, share_with is the gid at share_type GROUP.
 * Three consequences of that reading are copied on purpose (D-04-10):
 * (a) a never shared file of the person does not appear, (b) only the file
 * itself counts, never a shared parent folder, and (c) every share kind
 * counts for uid_owner, link shares included.
 *
 * The filters narrow and never widen: they are asked only about files that
 * already passed the recheck of the provider (readableFile and the
 * exclusions), and their answer can only drop such a file. So the share
 * question reveals nothing the Files app would not show, and a database that
 * fails drops every candidate instead of showing one it could not check
 * (fail closed, T-04-04). Nothing here logs a uid, a gid or a date; the one
 * warning carries the class of the error and nothing else.
 */
final class SearchFilters {
	/** Databases cap the size of an IN list; the ids are asked in slices below it. */
	private const CHUNK = 1000;

	public function __construct(
		public readonly ?int $since,
		public readonly ?int $until,
		public readonly ?string $personUid,
		public readonly ?string $groupId,
		private readonly IDBConnection $db,
		private readonly LoggerInterface $logger,
	) {
	}

	/**
	 * The filters of one query. A value of an unexpected type is no filter:
	 * since and until count as \DateTimeImmutable only, the person as IUser
	 * (its uid) or IGroup (its gid), told apart by the public interfaces and
	 * never by a private server class.
	 */
	public static function fromQuery(ISearchQuery $query, IDBConnection $db, LoggerInterface $logger): self {
		$since = $query->getFilter(IFilter::BUILTIN_SINCE)?->get();
		$until = $query->getFilter(IFilter::BUILTIN_UNTIL)?->get();
		$person = $query->getFilter(IFilter::BUILTIN_PERSON)?->get();

		return new self(
			$since instanceof \DateTimeImmutable ? $since->getTimestamp() : null,
			$until instanceof \DateTimeImmutable ? $until->getTimestamp() : null,
			$person instanceof IUser ? $person->getUID() : null,
			$person instanceof IGroup ? $person->getGID() : null,
			$db,
			$logger,
		);
	}

	/** Whether anything is narrowed at all. */
	public function hasAny(): bool {
		return $this->since !== null || $this->until !== null || $this->hasPerson();
	}

	/** Whether a person or a group narrows the hits over the share table. */
	public function hasPerson(): bool {
		return $this->personUid !== null || $this->groupId !== null;
	}

	/**
	 * Whether the modification time of a confirmed file lies within the
	 * bounds, both ends inclusive to the second (D-04-09).
	 */
	public function matchesTime(File $file): bool {
		$mtime = $file->getMTime();

		return ($this->since === null || $mtime >= $this->since)
			&& ($this->until === null || $mtime <= $this->until);
	}

	/**
	 * The subset of the given files a share row ties to the person (D-04-10).
	 *
	 * One query per slice of CHUNK ids, so usually exactly one per call; no
	 * query without a person filter (nothing is narrowed, every id passes)
	 * and none for an empty list. A database that fails answers with the
	 * empty set: the filter then drops every candidate rather than showing
	 * one it could not check.
	 *
	 * @param list<int> $fileIds the ids of files that already passed the recheck
	 * @return array<int, true> the ids with a matching share row, as a set
	 */
	public function sharedSubset(array $fileIds): array {
		$ids = array_values(array_unique($fileIds));
		if (!$this->hasPerson()) {
			return array_fill_keys($ids, true);
		}
		if ($ids === []) {
			return [];
		}

		$subset = [];
		foreach (array_chunk($ids, self::CHUNK) as $slice) {
			try {
				$query = $this->db->getQueryBuilder();
				$query->select('file_source')
					->from('share')
					->where($query->expr()->in(
						'file_source',
						$query->createNamedParameter($slice, IQueryBuilder::PARAM_INT_ARRAY),
					))
					->andWhere($this->personCondition($query));
				$result = $query->executeQuery();
				while (($row = $result->fetch()) !== false) {
					$subset[(int)$row['file_source']] = true;
				}
				$result->closeCursor();
			} catch (\Throwable $e) {
				$this->logger->warning('Audio & Video Search: the share rows of the person filter could not be read', ['class' => $e::class]);

				return [];
			}
		}

		return $subset;
	}

	/**
	 * The person condition of Files: OR(uid_owner = uid, AND(share_with = uid,
	 * share_type = USER)) for a user, AND(share_with = gid, share_type = GROUP)
	 * for a group. Every value travels as a bound parameter and the ids as one
	 * bound int array, never as text in the statement (T-04-05).
	 */
	private function personCondition(IQueryBuilder $query): ICompositeExpression {
		if ($this->groupId !== null) {
			return $query->expr()->andX(
				$query->expr()->eq('share_with', $query->createNamedParameter($this->groupId)),
				$query->expr()->eq('share_type', $query->createNamedParameter(IShare::TYPE_GROUP, IQueryBuilder::PARAM_INT)),
			);
		}

		return $query->expr()->orX(
			$query->expr()->eq('uid_owner', $query->createNamedParameter((string)$this->personUid)),
			$query->expr()->andX(
				$query->expr()->eq('share_with', $query->createNamedParameter((string)$this->personUid)),
				$query->expr()->eq('share_type', $query->createNamedParameter(IShare::TYPE_USER, IQueryBuilder::PARAM_INT)),
			),
		);
	}
}
