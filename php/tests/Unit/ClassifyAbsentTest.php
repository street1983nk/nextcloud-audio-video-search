<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Service\StorageService;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\Files\Cache\ICacheEntry;
use OCP\Files\Cache\IFileAccess;
use OCP\IDBConnection;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;

/**
 * Which storages the container may forget at once (plan 02-19, T-02-70).
 *
 * oc_storages is the real table of the throwaway instance: the cases write
 * their own rows under an id this suite owns and delete them again. The
 * mount set is a double of IFileAccess, the capturability a closure.
 *
 * gone: no row in oc_storages. deselected: the row is there, but the storage
 * is not in the mount set or not capturable. present: everything else. Only
 * the asked ids come back.
 */
#[CoversClass(StorageService::class)]
final class ClassifyAbsentTest extends TestCase {
	private const ID_PREFIX = 'avs-classify-test::';

	private IDBConnection $db;
	private IFileAccess&MockObject $fileAccess;
	/** @var list<int> storages in oc_storages, in the mount set */
	private array $mounted = [];
	/** @var int a storage in oc_storages, in no mount */
	private int $unmounted = 0;
	/** @var int a numeric id that had a row and has none any more */
	private int $deleted = 0;

	protected function setUp(): void {
		parent::setUp();

		$this->db = \OCP\Server::get(IDBConnection::class);
		$this->clear();
		$this->mounted = [$this->storageRow('a'), $this->storageRow('b')];
		$this->unmounted = $this->storageRow('c');
		$this->deleted = $this->storageRow('d');
		$qb = $this->db->getQueryBuilder();
		$qb->delete('storages')->where($qb->expr()->eq('numeric_id', $qb->createNamedParameter($this->deleted, IQueryBuilder::PARAM_INT)))->executeStatement();

		$this->fileAccess = $this->createMock(IFileAccess::class);
		$mounted = $this->mounted;
		$this->fileAccess->method('getDistinctMounts')->willReturnCallback(static function () use ($mounted): \Generator {
			foreach ($mounted as $index => $storageId) {
				yield ['storage_id' => $storageId, 'root_id' => 100 + $index, 'overridden_root' => 100 + $index];
			}
		});
		$this->fileAccess->method('getByFileIdInStorage')->willReturn($this->createMock(ICacheEntry::class));
	}

	protected function tearDown(): void {
		$this->clear();
		parent::tearDown();
	}

	private function clear(): void {
		$qb = $this->db->getQueryBuilder();
		$qb->delete('storages')->where($qb->expr()->like('id', $qb->createNamedParameter(self::ID_PREFIX . '%')))->executeStatement();
	}

	private function storageRow(string $name): int {
		$qb = $this->db->getQueryBuilder();
		$qb->insert('storages')->values([
			'id' => $qb->createNamedParameter(self::ID_PREFIX . $name . '-' . bin2hex(random_bytes(4))),
			'available' => $qb->createNamedParameter(1, IQueryBuilder::PARAM_INT),
		])->executeStatement();

		return $qb->getLastInsertId();
	}

	private function service(?IDBConnection $db = null): StorageService {
		return new StorageService($this->fileAccess, $db ?? $this->db);
	}

	/** @return \Closure(int): bool */
	private static function capturable(int ...$not): \Closure {
		return static fn (int $storageId): bool => !in_array($storageId, $not, true);
	}

	public function testAStorageWithoutARowIsGone(): void {
		$answer = $this->service()->classifyAbsent([$this->deleted], self::capturable());

		self::assertSame(['gone' => [$this->deleted], 'deselected' => [], 'present' => []], $answer);
	}

	public function testAStorageOutsideTheMountSetIsDeselected(): void {
		$answer = $this->service()->classifyAbsent([$this->unmounted], self::capturable());

		self::assertSame(['gone' => [], 'deselected' => [$this->unmounted], 'present' => []], $answer);
	}

	public function testAStorageThatIsNotCapturableIsDeselected(): void {
		[$a, $b] = $this->mounted;

		$answer = $this->service()->classifyAbsent([$a, $b], self::capturable($b));

		self::assertSame(['gone' => [], 'deselected' => [$b], 'present' => [$a]], $answer);
	}

	public function testOnlyTheAskedIdsComeBackSortedOnceAndPositive(): void {
		[$a, $b] = $this->mounted;
		$asked = [$b, $this->deleted, 0, -4, $a, $b, $this->unmounted];

		$answer = $this->service()->classifyAbsent($asked, self::capturable());

		self::assertSame([$this->deleted], $answer['gone']);
		self::assertSame([$this->unmounted], $answer['deselected']);
		$present = [$a, $b];
		sort($present);
		self::assertSame($present, $answer['present']);
	}

	public function testAnEmptyListAsksNothing(): void {
		$db = $this->createMock(IDBConnection::class);
		$db->expects(self::never())->method('getQueryBuilder');

		self::assertSame(['gone' => [], 'deselected' => [], 'present' => []], $this->service($db)->classifyAbsent([0, -1], self::capturable()));
	}

	public function testTheLookupRunsInBandsOf200(): void {
		$builders = 0;
		$db = $this->createMock(IDBConnection::class);
		$db->method('getQueryBuilder')->willReturnCallback(function () use (&$builders) {
			$builders++;

			return $this->db->getQueryBuilder();
		});
		$asked = range($this->deleted + 1_000_000, $this->deleted + 1_000_449);
		$asked[] = $this->mounted[0];

		$answer = $this->service($db)->classifyAbsent($asked, self::capturable());

		self::assertSame(3, $builders);
		self::assertSame(StorageService::ABSENT_LOOKUP_BAND, 200);
		self::assertCount(450, $answer['gone']);
		self::assertSame([$this->mounted[0]], $answer['present']);
	}

	public function testTheCapturabilityIsAskedOnlyForStoragesOfTheMountSet(): void {
		$asked = [];
		$capturable = static function (int $storageId) use (&$asked): bool {
			$asked[] = $storageId;

			return true;
		};

		$this->service()->classifyAbsent([$this->deleted, $this->unmounted, $this->mounted[0]], $capturable);

		self::assertSame([$this->mounted[0]], $asked);
	}
}
