<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Service\StorageService;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

/**
 * The share key and the prefilter key (D-02-01, 02-RESEARCH.md Befund 6).
 *
 * The share key is cut from the full storage id string of the storage object,
 * never from oc_storages.id (that column keeps an md5 above 64 characters).
 * The root of the configuration moves into the path, so two configurations of
 * the same share with different roots meet on the same key. Pure functions,
 * no doubles.
 */
#[CoversClass(StorageService::class)]
final class ShareKeyTest extends TestCase {
	/** @return array<string, array{string, array{0: string, 1: string}}> */
	public static function grouped(): array {
		return [
			'smb, root empty' => ['smb::ana@nas.local//Medien/', ['smb::nas.local//Medien', '']],
			'smb, root empty as NC writes it' => ['smb::ana@nas.local//Medien//', ['smb::nas.local//Medien', '']],
			'smb, root gemeinsam' => ['smb::ana@nas.local//Medien//gemeinsam/', ['smb::nas.local//Medien', 'gemeinsam']],
			'smb, root two levels' => ['smb::ben@nas.local//Medien//a/b/', ['smb::nas.local//Medien', 'a/b']],
			'smb, login name with @' => ['smb::ana@firma.de@nas.local//Medien//', ['smb::nas.local//Medien', '']],
			'smb, anonymous login' => ['smb::@nas.local//Medien//', ['smb::nas.local//Medien', '']],
			'smb, long id beyond 64 characters' => [
				'smb::verwaltung.mustermann@nas.example.local//Daten//Projekte/Sitzungen/2026/',
				['smb::nas.example.local//Daten', 'Projekte/Sitzungen/2026'],
			],
			'sftp with port' => ['sftp::ana@host:2222//data/', ['sftp::host:2222', 'data']],
			'sftp without port, root empty' => ['sftp::ana@host//', ['sftp::host', '']],
		];
	}

	/** @param array{0: string, 1: string} $expected */
	#[DataProvider('grouped')]
	public function testTheShareKeyDropsTheLoginAndMovesTheRootIntoThePath(string $storageId, array $expected): void {
		self::assertSame($expected, StorageService::shareKey($storageId));
	}

	public function testTwoUsersOfTheSameShareMeetOnOneKey(): void {
		self::assertSame(
			StorageService::shareKey('smb::ana@nas.local//Medien//'),
			StorageService::shareKey('smb::ben@nas.local//Medien//'),
		);
	}

	/** @return array<string, array{string}> */
	public static function notGrouped(): array {
		return [
			'amazon' => ['amazon::external::0123456789abcdef0123456789abcdef'],
			'local' => ['local::/srv/medien/'],
			'webdav' => ['webdav::ana@cloud.example//remote.php/webdav/'],
			'home' => ['home::ana'],
			'object' => ['object::user:ana'],
			'failed' => ['failedstorage'],
			'smb, empty host' => ['smb::ana@//Medien//'],
			'smb, no login part' => ['smb::nas.local//Medien//'],
			'smb, without //' => ['smb::ana@nas.local/Medien/'],
			'smb, empty share' => ['smb::ana@nas.local//'],
			'smb, share starts with a slash' => ['smb::ana@nas.local///Medien/'],
			'sftp, without //' => ['sftp::ana@host/data/'],
			'sftp, empty host' => ['sftp::ana@//data/'],
			'empty' => [''],
			'smb, zero byte' => ["smb::ana@nas.local//Med\0ien//"],
		];
	}

	#[DataProvider('notGrouped')]
	public function testEveryOtherStorageHasNoShareKey(string $storageId): void {
		self::assertNull(StorageService::shareKey($storageId));
	}

	public function testTheStoredHashIsTheSha256OfTheShareKey(): void {
		self::assertSame(hash('sha256', 'smb::nas.local//Medien'), StorageService::shareKeyHash('smb::nas.local//Medien'));
		self::assertMatchesRegularExpression('/^[0-9a-f]{64}$/', StorageService::shareKeyHash('sftp::host'));
	}

	private static function hashOf(string $storageId): string {
		$key = StorageService::shareKey($storageId);
		self::assertNotNull($key);

		return StorageService::shareKeyHash($key[0]);
	}

	public function testTwoUsersWithTheSamePathSizeAndStorageMtimeGetTheSamePrefilterKey(): void {
		$ana = StorageService::shareKey('smb::ana@nas.local//Medien//');
		$ben = StorageService::shareKey('smb::ben@nas.local//Medien//');
		self::assertNotNull($ana);
		self::assertNotNull($ben);

		$first = StorageService::prefilterKey(StorageService::shareKeyHash($ana[0]), $ana[1], 'Sitzung/a.webm', 4096, 1700000000);
		$second = StorageService::prefilterKey(StorageService::shareKeyHash($ben[0]), $ben[1], 'Sitzung/a.webm', 4096, 1700000000);

		self::assertNotNull($first);
		self::assertMatchesRegularExpression('/^[0-9a-f]{64}$/', $first);
		self::assertSame($first, $second);
	}

	public function testTheRootOfTheConfigurationIsPartOfThePath(): void {
		$withRoot = StorageService::shareKey('smb::ana@nas.local//Medien//gemeinsam/');
		$withoutRoot = StorageService::shareKey('smb::ana@nas.local//Medien//');
		self::assertNotNull($withRoot);
		self::assertNotNull($withoutRoot);

		self::assertSame(
			StorageService::prefilterKey(StorageService::shareKeyHash($withRoot[0]), $withRoot[1], 'z.webm', 10, 20),
			StorageService::prefilterKey(StorageService::shareKeyHash($withoutRoot[0]), $withoutRoot[1], 'gemeinsam/z.webm', 10, 20),
		);
	}

	public function testAnotherSizeAnotherMtimeAnotherPathOrAnotherShareGivesAnotherKey(): void {
		$hash = self::hashOf('smb::ana@nas.local//Medien//');
		$base = StorageService::prefilterKey($hash, '', 'a.webm', 4096, 1700000000);

		self::assertNotSame($base, StorageService::prefilterKey($hash, '', 'a.webm', 4097, 1700000000));
		self::assertNotSame($base, StorageService::prefilterKey($hash, '', 'a.webm', 4096, 1700000001));
		self::assertNotSame($base, StorageService::prefilterKey($hash, '', 'b.webm', 4096, 1700000000));
		self::assertNotSame($base, StorageService::prefilterKey(self::hashOf('smb::ana@nas.local//Andere//'), '', 'a.webm', 4096, 1700000000));
		self::assertNotSame($base, StorageService::prefilterKey(self::hashOf('sftp::ana@nas.local//'), '', 'a.webm', 4096, 1700000000));
	}

	public function testTheFieldsCannotRunIntoEachOther(): void {
		$hash = self::hashOf('smb::ana@nas.local//Medien//');

		// "a/b" + "c" and "a" + "b/c" are the same path on purpose; a size that
		// is glued to the path is not.
		self::assertSame(
			StorageService::prefilterKey($hash, 'a/b', 'c.webm', 1, 2),
			StorageService::prefilterKey($hash, 'a', 'b/c.webm', 1, 2),
		);
		self::assertNotSame(
			StorageService::prefilterKey($hash, '', 'a.webm1', 2, 3),
			StorageService::prefilterKey($hash, '', 'a.webm', 12, 3),
		);
	}

	public function testAZeroByteABrokenHashOrAnUnknownSizeGivesNoKey(): void {
		$hash = self::hashOf('smb::ana@nas.local//Medien//');

		self::assertNull(StorageService::prefilterKey($hash, '', "a\0.webm", 1, 2));
		self::assertNull(StorageService::prefilterKey($hash, "gemein\0sam", 'a.webm', 1, 2));
		self::assertNull(StorageService::prefilterKey('not-a-hash', '', 'a.webm', 1, 2));
		self::assertNull(StorageService::prefilterKey($hash, '', 'a.webm', -1, 2));
		self::assertNull(StorageService::prefilterKey($hash, '', '', 1, 2));
	}
}
