<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Db\QueueMapper;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\IDBConnection;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\TestCase;

/**
 * The work stock against the real database of the throwaway instance.
 *
 * A claim is a conditional update, so a mock of the query builder would only
 * test that the statements were written down; these cases run them. php.yml
 * enables the app before the suite, which runs its migrations and creates
 * oc_avs_queue. The clock is a double, so the lock timeout is exact.
 */
#[CoversClass(QueueMapper::class)]
final class QueueMapperTest extends TestCase {
	private IDBConnection $db;
	private QueueMapper $mapper;
	private int $now = 1_000_000;

	protected function setUp(): void {
		parent::setUp();

		$this->db = \OCP\Server::get(IDBConnection::class);
		self::assertTrue(
			$this->db->tableExists(QueueMapper::TABLE),
			'oc_avs_queue is missing: the suite needs the app enabled so its migrations ran (php.yml)',
		);
		$this->clear();
		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturnCallback(fn (): int => $this->now);
		$this->mapper = new QueueMapper($this->db, $time);
	}

	protected function tearDown(): void {
		$this->clear();
		parent::tearDown();
	}

	private function clear(): void {
		$this->db->getQueryBuilder()->delete(QueueMapper::TABLE)->executeStatement();
	}

	/** @return list<array{kind: string, file: ?int, storage: int, attempts: int, locked: ?int, dirty: int}> */
	private function rows(): array {
		$qb = $this->db->getQueryBuilder();
		$qb->select('kind', 'file_id', 'storage_id', 'attempts', 'locked_at', 'dirty')
			->from(QueueMapper::TABLE)
			->orderBy('id', 'ASC');
		$result = $qb->executeQuery();
		$rows = [];
		while (($row = $result->fetch()) !== false) {
			$rows[] = [
				'kind' => (string)$row['kind'],
				'file' => $row['file_id'] === null ? null : (int)$row['file_id'],
				'storage' => (int)$row['storage_id'],
				'attempts' => (int)$row['attempts'],
				'locked' => $row['locked_at'] === null ? null : (int)$row['locked_at'],
				'dirty' => (int)$row['dirty'],
			];
		}
		$result->closeCursor();

		return $rows;
	}

	private function token(string $char): string {
		return str_repeat($char, 32);
	}

	public function testTheClaimTakesAtMostTheLimitInTheOrderOfTheKinds(): void {
		$this->mapper->enqueue(QueueMapper::KIND_METADATA, 1, 3);
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 2, 3);
		$this->mapper->enqueue(QueueMapper::KIND_DELETE, 3, 3);
		$this->mapper->enqueue(QueueMapper::KIND_EXCLUDE_STORAGE, null, 9);
		$this->mapper->enqueue(QueueMapper::KIND_RESTORE, 4, 3);

		$claimed = $this->mapper->claim(3, $this->token('a'));

		self::assertSame(
			[QueueMapper::KIND_EXCLUDE_STORAGE, QueueMapper::KIND_DELETE, QueueMapper::KIND_RESTORE],
			array_column($claimed, 'kind'),
		);
		self::assertSame([null, 3, 4], array_column($claimed, 'fileId'));
		self::assertSame([1, 1, 1], array_column($claimed, 'attempts'));
	}

	public function testAClaimedRowIsFreeAgainOnlyAfterTheLockTimeout(): void {
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 3);
		self::assertCount(1, $this->mapper->claim(5, $this->token('a')));

		self::assertSame([], $this->mapper->claim(5, $this->token('b')));
		$this->now += QueueMapper::LOCK_TIMEOUT - 1;
		self::assertSame([], $this->mapper->claim(5, $this->token('c')));
		$this->now += 1;
		$again = $this->mapper->claim(5, $this->token('d'));

		self::assertCount(1, $again);
		self::assertSame(2, $again[0]['attempts']);
	}

	public function testAnEventOnAClaimedRowMarksItDirtyAndTheAckFreesIt(): void {
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 3);
		$claimed = $this->mapper->claim(5, $this->token('a'));
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 3);

		self::assertSame(1, $this->rows()[0]['dirty']);
		self::assertSame(0, $this->mapper->acknowledge($this->token('a'), [$claimed[0]['id']]));
		$rows = $this->rows();
		self::assertCount(1, $rows);
		self::assertSame(0, $rows[0]['dirty']);
		self::assertNull($rows[0]['locked']);
		self::assertCount(1, $this->mapper->claim(5, $this->token('b')));
	}

	public function testAnEventOnAFreeRowAddsNothing(): void {
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 3);
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 3);

		$rows = $this->rows();
		self::assertCount(1, $rows);
		self::assertSame(0, $rows[0]['dirty']);
	}

	public function testTheAckDeletesCleanRowsOfItsOwnTokenOnly(): void {
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 3);
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 8, 3);
		$claimed = $this->mapper->claim(1, $this->token('a'));

		self::assertSame(0, $this->mapper->acknowledge($this->token('b'), [$claimed[0]['id']]));
		self::assertSame(1, $this->mapper->acknowledge($this->token('a'), [$claimed[0]['id']]));
		self::assertSame([8], array_column($this->rows(), 'file'));
	}

	public function testContentReplacesADeleteOfTheSameFileAndTheOtherWayRound(): void {
		$this->mapper->enqueue(QueueMapper::KIND_DELETE, 7, 3);
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 4);

		self::assertSame([[QueueMapper::KIND_CONTENT, 4]], array_map(static fn (array $r): array => [$r['kind'], $r['storage']], $this->rows()));

		$this->mapper->enqueue(QueueMapper::KIND_DELETE, 7, 4);

		self::assertSame([[QueueMapper::KIND_DELETE, 4]], array_map(static fn (array $r): array => [$r['kind'], $r['storage']], $this->rows()));
	}

	public function testUnlockGivesTheRowBackAndTakesTheAttemptBack(): void {
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 3);
		$claimed = $this->mapper->claim(5, $this->token('a'));

		self::assertSame(0, $this->mapper->unlock($this->token('b'), [$claimed[0]['id']]));
		self::assertSame(1, $this->mapper->unlock($this->token('a'), [$claimed[0]['id']]));
		$rows = $this->rows();
		self::assertSame(0, $rows[0]['attempts']);
		self::assertNull($rows[0]['locked']);
	}

	public function testAStorageJobWithoutAFileIsQueuedOnce(): void {
		$this->mapper->enqueue(QueueMapper::KIND_EXCLUDE_STORAGE, null, 5);
		$this->mapper->enqueue(QueueMapper::KIND_EXCLUDE_STORAGE, null, 5);
		$this->mapper->enqueue(QueueMapper::KIND_EXCLUDE_STORAGE, null, 6);

		self::assertSame([5, 6], array_column($this->rows(), 'storage'));
	}

	public function testDropRemovesOnlyRowsOfTheToken(): void {
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 3);
		$claimed = $this->mapper->claim(5, $this->token('a'));

		self::assertSame(0, $this->mapper->drop($this->token('b'), [$claimed[0]['id']]));
		self::assertSame(1, $this->mapper->drop($this->token('a'), [$claimed[0]['id']]));
		self::assertSame([], $this->rows());
	}

	public function testOpenByKindNamesEveryKind(): void {
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 7, 3);
		$this->mapper->enqueue(QueueMapper::KIND_CONTENT, 8, 3);
		$this->mapper->enqueue(QueueMapper::KIND_EXCLUDE, 9, 3);

		$open = $this->mapper->openByKind();

		self::assertSame(QueueMapper::KINDS, array_keys($open));
		self::assertSame(2, $open[QueueMapper::KIND_CONTENT]);
		self::assertSame(1, $open[QueueMapper::KIND_EXCLUDE]);
		self::assertSame(0, $open[QueueMapper::KIND_DELETE]);
	}

	public function testAnUnknownKindIsRefused(): void {
		$this->expectException(\InvalidArgumentException::class);

		$this->mapper->enqueue('transcribe', 7, 3);
	}
}
