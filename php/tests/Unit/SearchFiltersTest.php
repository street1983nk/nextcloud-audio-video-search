<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Service\SearchFilters;
use OCP\DB\IResult;
use OCP\DB\QueryBuilder\ICompositeExpression;
use OCP\DB\QueryBuilder\IExpressionBuilder;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\Files\File;
use OCP\IDBConnection;
use OCP\IGroup;
use OCP\IUser;
use OCP\Search\IFilter;
use OCP\Search\ISearchQuery;
use OCP\Share\IShare;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The filter meaning of Files, re-evaluated with an independent reading
 * (plan 04-02, D-04-09, D-04-10).
 *
 * The database is a double whose expression builder hands out readable
 * conditions, and executeQuery evaluates them against a small share table
 * the test owns, with every bound parameter resolved. So these cases do not
 * check that the service wrote the statement it wrote: they read the
 * statement the way a database would and check that it picks exactly the
 * rows of D-04-10 (the owner whatever the share kind, a direct share at
 * share_type USER, a group at share_type GROUP, and nothing else).
 */
#[CoversClass(SearchFilters::class)]
final class SearchFiltersTest extends TestCase {
	/** @var list<array{file_source:int,uid_owner:string,share_with:string,share_type:int}> the share table of the fake */
	private array $shareRows = [];

	/** How many queries were executed. */
	private int $queries = 0;

	/** @var array<string, array{value: mixed, type: mixed}> every named parameter by its placeholder */
	private array $params = [];

	/** @var list<list<int>> the int array band of every IN, in the order of the queries */
	private array $bands = [];

	/** @var array<int, array{string, list<mixed>}> the composite expressions by object id */
	private array $composites = [];

	/** @var list<string> every warning with its context, as one text */
	private array $logged = [];

	/** The next executeQuery throws, like a database that is gone. */
	private bool $failing = false;

	private int $opened = 0;
	private int $closed = 0;

	protected function setUp(): void {
		parent::setUp();

		$this->shareRows = [];
		$this->queries = 0;
		$this->params = [];
		$this->bands = [];
		$this->composites = [];
		$this->logged = [];
		$this->failing = false;
		$this->opened = 0;
		$this->closed = 0;
	}

	private function db(): IDBConnection {
		$db = $this->createMock(IDBConnection::class);
		$db->method('getQueryBuilder')->willReturnCallback(fn (): IQueryBuilder => $this->queryBuilder());

		return $db;
	}

	private function logger(): LoggerInterface {
		$logger = $this->createMock(LoggerInterface::class);
		$logger->method('warning')->willReturnCallback(function (string|\Stringable $message, array $context = []): void {
			$this->logged[] = $message . ' ' . json_encode($context);
		});

		return $logger;
	}

	private function queryBuilder(): IQueryBuilder {
		$conditions = [];

		$qb = $this->createMock(IQueryBuilder::class);
		$expr = $this->createMock(IExpressionBuilder::class);
		$expr->method('eq')->willReturnCallback(static fn (string $x, mixed $y, mixed $type = null): string => $x . ' = ' . $y);
		$expr->method('in')->willReturnCallback(static fn (string $x, mixed $y, mixed $type = null): string => $x . ' IN ' . $y);
		$expr->method('orX')->willReturnCallback(fn (mixed ...$parts): ICompositeExpression => $this->composite('or', $parts));
		$expr->method('andX')->willReturnCallback(fn (mixed ...$parts): ICompositeExpression => $this->composite('and', $parts));

		$qb->method('expr')->willReturn($expr);
		$qb->method('select')->willReturnSelf();
		$qb->method('from')->willReturnCallback(function (string $table) use ($qb): IQueryBuilder {
			self::assertSame('share', $table, 'the person filter reads the share table and nothing else');

			return $qb;
		});
		$qb->method('where')->willReturnCallback(function (mixed $predicate) use ($qb, &$conditions): IQueryBuilder {
			$conditions[] = $predicate;

			return $qb;
		});
		$qb->method('andWhere')->willReturnCallback(function (mixed $predicate) use ($qb, &$conditions): IQueryBuilder {
			$conditions[] = $predicate;

			return $qb;
		});
		$qb->method('createNamedParameter')->willReturnCallback(function (mixed $value, mixed $type = IQueryBuilder::PARAM_STR): string {
			$name = ':p' . (count($this->params) + 1);
			$this->params[$name] = ['value' => $value, 'type' => $type];
			if ($type === IQueryBuilder::PARAM_INT_ARRAY) {
				self::assertIsArray($value);
				$this->bands[] = array_values($value);
			}

			return $name;
		});
		$qb->method('executeQuery')->willReturnCallback(function () use (&$conditions): IResult {
			$this->queries++;
			if ($this->failing) {
				throw new \RuntimeException('gone');
			}

			$rows = [];
			foreach ($this->shareRows as $row) {
				$kept = true;
				foreach ($conditions as $condition) {
					if (!$this->holds($condition, $row)) {
						$kept = false;
						break;
					}
				}
				if ($kept) {
					// As a driver hands a row out: strings.
					$rows[] = ['file_source' => (string)$row['file_source']];
				}
			}

			return $this->resultOf($rows);
		});

		return $qb;
	}

	/** @param list<mixed> $parts */
	private function composite(string $kind, array $parts): ICompositeExpression {
		$expression = $this->createMock(ICompositeExpression::class);
		$this->composites[spl_object_id($expression)] = [$kind, $parts];

		return $expression;
	}

	/**
	 * Whether a condition the service built holds for one row of the share
	 * table, with the bound parameters resolved: the independent reading.
	 *
	 * @param array{file_source:int,uid_owner:string,share_with:string,share_type:int} $row
	 */
	private function holds(mixed $condition, array $row): bool {
		if ($condition instanceof ICompositeExpression) {
			[$kind, $parts] = $this->composites[spl_object_id($condition)];
			foreach ($parts as $part) {
				$answer = $this->holds($part, $row);
				if ($kind === 'or' && $answer) {
					return true;
				}
				if ($kind === 'and' && !$answer) {
					return false;
				}
			}

			return $kind === 'and';
		}

		self::assertIsString($condition);
		if (preg_match('/^(\w+) IN (:p\d+)$/', $condition, $found) === 1) {
			$band = $this->params[$found[2]]['value'];
			self::assertIsArray($band);

			return in_array((int)$row[$found[1]], array_map(static fn (mixed $id): int => (int)$id, $band), true);
		}
		if (preg_match('/^(\w+) = (:p\d+)$/', $condition, $found) === 1) {
			return (string)$row[$found[1]] === (string)$this->params[$found[2]]['value'];
		}

		self::fail('a condition the fake cannot read: ' . $condition);
	}

	/** @param list<array<string, string>> $rows */
	private function resultOf(array $rows): IResult {
		$this->opened++;
		$result = $this->createMock(IResult::class);
		$result->method('fetch')->willReturnCallback(static function () use (&$rows): mixed {
			return array_shift($rows) ?? false;
		});
		$result->method('closeCursor')->willReturnCallback(function (): bool {
			$this->closed++;

			return true;
		});

		return $result;
	}

	/** One row of the share table of the fake. */
	private function share(int $fileSource, string $owner, string $with, int $type): void {
		$this->shareRows[] = ['file_source' => $fileSource, 'uid_owner' => $owner, 'share_with' => $with, 'share_type' => $type];
	}

	private function filters(?int $since = null, ?int $until = null, ?string $personUid = null, ?string $groupId = null): SearchFilters {
		return new SearchFilters($since, $until, $personUid, $groupId, $this->db(), $this->logger());
	}

	/** @param array<string, mixed> $values filter name to the value its get() returns */
	private function query(array $values): ISearchQuery {
		$query = $this->createMock(ISearchQuery::class);
		$query->method('getFilter')->willReturnCallback(function (string $name) use ($values): ?IFilter {
			if (!array_key_exists($name, $values)) {
				return null;
			}
			$filter = $this->createMock(IFilter::class);
			$filter->method('get')->willReturn($values[$name]);

			return $filter;
		});

		return $query;
	}

	private function person(string $uid): IUser {
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn($uid);

		return $user;
	}

	private function group(string $gid): IGroup {
		$group = $this->createMock(IGroup::class);
		$group->method('getGID')->willReturn($gid);

		return $group;
	}

	private function fileWithMTime(int $mtime): File {
		$file = $this->createMock(File::class);
		$file->method('getMTime')->willReturn($mtime);

		return $file;
	}

	// -- reading the query --------------------------------------------------------

	public function testWithoutAnyFilterNothingIsNarrowedAndNothingIsAsked(): void {
		$filters = SearchFilters::fromQuery($this->query([]), $this->db(), $this->logger());

		self::assertFalse($filters->hasAny());
		self::assertFalse($filters->hasPerson());
		self::assertTrue($filters->matchesTime($this->fileWithMTime(0)));
		self::assertSame([11 => true, 12 => true], $filters->sharedSubset([11, 12]));
		self::assertSame(0, $this->queries);
	}

	public function testFromQueryReadsTheDatesAndAUserThroughThePublicInterfaces(): void {
		$filters = SearchFilters::fromQuery($this->query([
			IFilter::BUILTIN_SINCE => new \DateTimeImmutable('@1700000000'),
			IFilter::BUILTIN_UNTIL => new \DateTimeImmutable('@1700086400'),
			IFilter::BUILTIN_PERSON => $this->person('bob'),
		]), $this->db(), $this->logger());

		self::assertSame(1700000000, $filters->since);
		self::assertSame(1700086400, $filters->until);
		self::assertSame('bob', $filters->personUid);
		self::assertNull($filters->groupId);
		self::assertTrue($filters->hasAny());
		self::assertTrue($filters->hasPerson());
	}

	public function testAGroupAsThePersonIsToldApartByItsInterface(): void {
		$filters = SearchFilters::fromQuery(
			$this->query([IFilter::BUILTIN_PERSON => $this->group('friends')]),
			$this->db(),
			$this->logger(),
		);

		self::assertNull($filters->personUid);
		self::assertSame('friends', $filters->groupId);
		self::assertTrue($filters->hasAny());
		self::assertTrue($filters->hasPerson());
	}

	public function testAValueOfAnUnexpectedTypeIsNoFilter(): void {
		$filters = SearchFilters::fromQuery($this->query([
			IFilter::BUILTIN_SINCE => 'yesterday',
			IFilter::BUILTIN_UNTIL => 1700086400,
			IFilter::BUILTIN_PERSON => 'bob',
		]), $this->db(), $this->logger());

		self::assertFalse($filters->hasAny());
		self::assertFalse($filters->hasPerson());
	}

	// -- the date bounds (D-04-09) ------------------------------------------------

	public function testBothDateBoundsAreInclusiveToTheSecond(): void {
		$filters = $this->filters(1000, 2000);

		self::assertFalse($filters->matchesTime($this->fileWithMTime(999)));
		self::assertTrue($filters->matchesTime($this->fileWithMTime(1000)));
		self::assertTrue($filters->matchesTime($this->fileWithMTime(1500)));
		self::assertTrue($filters->matchesTime($this->fileWithMTime(2000)));
		self::assertFalse($filters->matchesTime($this->fileWithMTime(2001)));
	}

	public function testOneBoundAloneLeavesTheOtherSideOpen(): void {
		$since = $this->filters(1000);
		self::assertTrue($since->matchesTime($this->fileWithMTime(PHP_INT_MAX)));
		self::assertFalse($since->matchesTime($this->fileWithMTime(999)));

		$until = $this->filters(null, 2000);
		self::assertTrue($until->matchesTime($this->fileWithMTime(0)));
		self::assertFalse($until->matchesTime($this->fileWithMTime(2001)));
	}

	// -- the person over the share rows (D-04-10) ---------------------------------

	public function testTheOwnerOfAShareRowCountsWhateverTheShareKind(): void {
		// A link share: share_with is nobody, the kind is neither USER nor
		// GROUP. The owner alone counts (consequence c of D-04-10).
		$this->share(11, 'bob', '', 3);
		$this->share(12, 'alice', 'carol', IShare::TYPE_USER);

		self::assertSame([11 => true], $this->filters(null, null, 'bob')->sharedSubset([11, 12]));
		self::assertSame(1, $this->queries);
	}

	public function testADirectShareCountsOnlyAtShareTypeUser(): void {
		$this->share(11, 'alice', 'bob', IShare::TYPE_USER);
		$this->share(12, 'alice', 'bob', IShare::TYPE_GROUP);

		self::assertSame([11 => true], $this->filters(null, null, 'bob')->sharedSubset([11, 12]));
	}

	public function testAGroupCountsOnlyAtShareTypeGroup(): void {
		$this->share(11, 'alice', 'friends', IShare::TYPE_GROUP);
		$this->share(12, 'alice', 'friends', IShare::TYPE_USER);
		$this->share(13, 'friends', 'carol', IShare::TYPE_USER);

		self::assertSame([11 => true], $this->filters(null, null, null, 'friends')->sharedSubset([11, 12, 13]));
	}

	public function testANeverSharedFileFallsOut(): void {
		$this->share(11, 'bob', '', 3);

		$subset = $this->filters(null, null, 'bob')->sharedSubset([11, 12]);

		self::assertArrayHasKey(11, $subset);
		self::assertArrayNotHasKey(12, $subset);
	}

	// -- the shape of the questions -----------------------------------------------

	public function testOneQueryAnswersAWholeCallAndDuplicatesAreAskedOnce(): void {
		$this->share(11, 'bob', '', IShare::TYPE_USER);

		$subset = $this->filters(null, null, 'bob')->sharedSubset([11, 11, 12, 12, 11]);

		self::assertSame([11 => true], $subset);
		self::assertSame(1, $this->queries);
		self::assertSame([[11, 12]], $this->bands);
		self::assertSame(1, $this->closed, 'every cursor is closed');
	}

	public function testMoreThanAThousandIdsAreAskedInSlices(): void {
		$this->share(1, 'bob', '', IShare::TYPE_USER);
		$this->share(1001, 'bob', '', IShare::TYPE_USER);

		$subset = $this->filters(null, null, 'bob')->sharedSubset(range(1, 1001));

		self::assertSame([1 => true, 1001 => true], $subset);
		self::assertSame(2, $this->queries);
		self::assertSame([1000, 1], array_map(count(...), $this->bands));
	}

	public function testAnEmptyListAsksNothing(): void {
		self::assertSame([], $this->filters(null, null, 'bob')->sharedSubset([]));
		self::assertSame(0, $this->queries);
	}

	public function testTheUserConditionBindsTheUidAndShareTypeUserAsParameters(): void {
		$this->filters(null, null, 'bob')->sharedSubset([11]);

		$values = array_map(static fn (array $param): mixed => $param['value'], array_values($this->params));
		self::assertContains('bob', $values);
		self::assertContains(IShare::TYPE_USER, $values);
		$intArrays = array_filter($this->params, static fn (array $param): bool => $param['type'] === IQueryBuilder::PARAM_INT_ARRAY);
		self::assertCount(1, $intArrays, 'the ids travel as one bound int array, never as text');
	}

	public function testTheGroupConditionBindsTheGidAndShareTypeGroupAsParameters(): void {
		$this->filters(null, null, null, 'friends')->sharedSubset([11]);

		$values = array_map(static fn (array $param): mixed => $param['value'], array_values($this->params));
		self::assertContains('friends', $values);
		self::assertContains(IShare::TYPE_GROUP, $values);
		self::assertNotContains(IShare::TYPE_USER, $values, 'a group never matches a USER share');
	}

	// -- a database that fails ----------------------------------------------------

	public function testADatabaseErrorIsTheEmptySetAndALogLineWithoutAName(): void {
		$this->failing = true;
		$this->share(11, 'bob', '', IShare::TYPE_USER);

		$subset = $this->filters(null, null, 'bob')->sharedSubset([11]);

		self::assertSame([], $subset);
		self::assertCount(1, $this->logged);
		self::assertStringContainsString('RuntimeException', $this->logged[0]);
		self::assertStringNotContainsString('bob', $this->logged[0]);
		self::assertStringNotContainsString('11', $this->logged[0]);
	}
}
