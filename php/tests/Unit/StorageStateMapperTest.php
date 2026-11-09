<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Db\StorageStateMapper;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\IDBConnection;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\TestCase;

/**
 * The classification of a storage against the real database of the throwaway
 * instance (php.yml enables the app, so oc_avs_storage exists).
 */
#[CoversClass(StorageStateMapper::class)]
final class StorageStateMapperTest extends TestCase {
	private IDBConnection $db;
	private StorageStateMapper $mapper;
	private int $now = 2_000_000;

	protected function setUp(): void {
		parent::setUp();

		$this->db = \OCP\Server::get(IDBConnection::class);
		self::assertTrue(
			$this->db->tableExists(StorageStateMapper::TABLE),
			'oc_avs_storage is missing: the suite needs the app enabled so its migrations ran (php.yml)',
		);
		$this->clear();
		$this->mapper = $this->mapper();
	}

	protected function tearDown(): void {
		$this->clear();
		parent::tearDown();
	}

	private function clear(): void {
		$this->db->getQueryBuilder()->delete(StorageStateMapper::TABLE)->executeStatement();
	}

	private function mapper(): StorageStateMapper {
		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturnCallback(fn (): int => $this->now);

		return new StorageStateMapper($this->db, $time);
	}

	/**
	 * @return array{storageId: int, mountId: ?int, provider: string, shareKeyHash: ?string, rootPrefix: ?string, authKind: ?string, capturable: bool, reason: ?string, users: int, checkedAt: ?int}
	 */
	private static function state(int $storageId, bool $capturable, ?string $reason, ?int $mountId = 2): array {
		return [
			'storageId' => $storageId,
			'mountId' => $mountId,
			'provider' => 'OCA\Files_External\Config\ConfigAdapter',
			'shareKeyHash' => $capturable ? hash('sha256', 'smb::nas.local//Medien') : null,
			'rootPrefix' => $capturable ? 'gemeinsam' : null,
			'authKind' => 'password::logincredentials',
			'capturable' => $capturable,
			'reason' => $reason,
			'users' => 1,
			'checkedAt' => 1_999_000,
		];
	}

	public function testAStorageWithoutARowIsUnknown(): void {
		self::assertNull($this->mapper->find(7));
		self::assertSame([], $this->mapper->skipped());
	}

	public function testStoreWritesANewRowAndOverwritesItLater(): void {
		$this->mapper->store(self::state(7, false, 'credentials_missing'));
		self::assertSame(self::state(7, false, 'credentials_missing'), $this->mapper->find(7));

		$this->mapper->store(self::state(7, true, null));
		self::assertSame(self::state(7, true, null), $this->mapper->find(7));
		self::assertSame(self::state(7, true, null), $this->mapper()->find(7));
	}

	public function testSkippedListsOnlyTheStoragesThatAreNotCapturable(): void {
		$this->mapper->store(self::state(9, false, 'unavailable', 5));
		$this->mapper->store(self::state(7, true, null));
		$this->mapper->store(self::state(8, false, 'session_credentials', 2));

		self::assertSame([8, 9], array_column($this->mapper->skipped(), 'storageId'));
	}

	public function testAReadIsRememberedForAMinuteAndAWriteForgetsIt(): void {
		$other = $this->mapper();
		$this->mapper->store(self::state(7, false, 'credentials_missing'));
		self::assertFalse($this->mapper->find(7)['capturable'] ?? true);

		// Another process writes; this one still remembers its read.
		$other->store(self::state(7, true, null));
		self::assertFalse($this->mapper->find(7)['capturable'] ?? true);

		$this->now += StorageStateMapper::MEMO_SECONDS;
		self::assertTrue($this->mapper->find(7)['capturable'] ?? false);
	}
}
