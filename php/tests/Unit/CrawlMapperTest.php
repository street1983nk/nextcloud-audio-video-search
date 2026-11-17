<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\IDBConnection;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\TestCase;

/**
 * The first crawl per mount against the real database of the throwaway
 * instance (php.yml enables the app, so oc_avs_crawl exists).
 */
#[CoversClass(CrawlMapper::class)]
final class CrawlMapperTest extends TestCase {
	private IDBConnection $db;
	private CrawlMapper $mapper;
	private int $now = 2_000_000;

	protected function setUp(): void {
		parent::setUp();

		$this->db = \OCP\Server::get(IDBConnection::class);
		self::assertTrue(
			$this->db->tableExists(CrawlMapper::TABLE),
			'oc_avs_crawl is missing: the suite needs the app enabled so its migrations ran (php.yml)',
		);
		$this->clear();
		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturnCallback(fn (): int => $this->now);
		$this->mapper = new CrawlMapper($this->db, $time);
	}

	protected function tearDown(): void {
		$this->clear();
		parent::tearDown();
	}

	private function clear(): void {
		$this->db->getQueryBuilder()->delete(CrawlMapper::TABLE)->executeStatement();
	}

	public function testUpsertCreatesOnceAndKeepsAnExistingRow(): void {
		self::assertTrue($this->mapper->upsert(3, 11));
		$this->mapper->advance(3, 11, 40);
		self::assertFalse($this->mapper->upsert(3, 11));

		self::assertSame(
			['storageId' => 3, 'rootId' => 11, 'lastFileId' => 40, 'generation' => 0, 'startedAt' => 2_000_000, 'finishedAt' => null],
			$this->mapper->find(3, 11),
		);
	}

	public function testTheCursorNeverMovesBack(): void {
		$this->mapper->upsert(3, 11);
		$this->mapper->advance(3, 11, 40);
		$this->mapper->advance(3, 11, 20);

		self::assertSame(40, $this->mapper->find(3, 11)['lastFileId'] ?? null);
	}

	public function testFinishAndResetStartANewGeneration(): void {
		$this->mapper->upsert(3, 11);
		$this->mapper->advance(3, 11, 40);
		$this->now += 60;
		$this->mapper->finish(3, 11);
		self::assertSame(2_000_060, $this->mapper->find(3, 11)['finishedAt'] ?? null);

		$this->now += 60;
		$this->mapper->reset(3, 11);

		self::assertSame(
			['storageId' => 3, 'rootId' => 11, 'lastFileId' => 0, 'generation' => 1, 'startedAt' => 2_000_120, 'finishedAt' => null],
			$this->mapper->find(3, 11),
		);
	}

	public function testAnUnknownMountHasNoRow(): void {
		self::assertNull($this->mapper->find(4, 12));
	}

	public function testProgressCountsFinishedAndOpenCrawls(): void {
		self::assertSame(['finished' => 0, 'open' => 0], $this->mapper->progress());

		$this->mapper->upsert(3, 11);
		$this->mapper->upsert(4, 12);
		$this->mapper->upsert(5, 13);
		$this->mapper->finish(4, 12);

		self::assertSame(['finished' => 1, 'open' => 2], $this->mapper->progress());
	}
}
