<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Db\StorageStateMapper;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCA\AudioVideoSearch\Service\StorageClassifier;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\App\IAppManager;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\Files\Config\ICachedMountInfo;
use OCP\Files\Config\IUserMountCache;
use OCP\Files\Mount\IMountManager;
use OCP\Files\Mount\IMountPoint;
use OCP\Files\Storage\IStorage;
use OCP\IDBConnection;
use OCP\IUser;
use OCP\IUserManager;
use OCP\IUserSession;
use OCP\Security\ICredentialsManager;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * Capturable or not, decided from the configuration before anything is
 * queued (D-02-03, 02-RESEARCH.md Befund 3).
 *
 * Everything is a double. The configuration of files_external comes from the
 * three protected lookups, which the doubles replace; the two cases about a
 * switched off app and a broken query run the real lookups.
 */
#[CoversClass(StorageClassifier::class)]
final class StorageClassifierTest extends TestCase {
	private const STORAGE = 7;
	private const MOUNT = 2;
	private const NOW = 2_000_000;

	private IUserMountCache&MockObject $mountCache;
	private IMountManager&MockObject $mountManager;
	private IAppManager&MockObject $apps;
	private ICredentialsManager&MockObject $credentials;
	private IDBConnection&MockObject $db;
	private StorageStateMapper&MockObject $states;
	private LoggerInterface&MockObject $logger;
	/** @var array<int, array{backend: string, auth: string, type: int}> */
	private array $configs = [];
	/** @var array<int, array{backend: string, auth: string, type: int}> */
	private array $never = [];
	/** @var list<string> */
	private array $setUpAs = [];
	private ?IUser $active = null;

	protected function setUp(): void {
		parent::setUp();

		$this->configs = [];
		$this->never = [];
		$this->setUpAs = [];
		$this->active = null;
		$this->mountCache = $this->createMock(IUserMountCache::class);
		$this->mountManager = $this->createMock(IMountManager::class);
		$this->apps = $this->createMock(IAppManager::class);
		$this->apps->method('isEnabledForAnyone')->willReturn(true);
		$this->credentials = $this->createMock(ICredentialsManager::class);
		$this->db = $this->createMock(IDBConnection::class);
		$this->states = $this->createMock(StorageStateMapper::class);
		$this->logger = $this->createMock(LoggerInterface::class);
	}

	private function user(string $uid): IUser&MockObject {
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn($uid);

		return $user;
	}

	/** The classifier with the configuration lookups replaced, or the real ones. */
	private function classifier(bool $realLookups = false): StorageClassifier {
		$session = $this->createMock(IUserSession::class);
		$session->method('getUser')->willReturnCallback(fn (): ?IUser => $this->active);
		$session->method('setVolatileActiveUser')->willReturnCallback(function (?IUser $user): void {
			$this->active = $user;
		});
		$users = $this->createMock(IUserManager::class);
		$users->method('get')->willReturnCallback(fn (string $uid): IUser => $this->user($uid));
		$time = $this->createMock(ITimeFactory::class);
		$time->method('getTime')->willReturn(self::NOW);
		$arguments = [
			$this->mountCache,
			$this->mountManager,
			$this->apps,
			$this->credentials,
			$this->db,
			$this->states,
			new ReaderContext($session, $users),
			$time,
			$this->logger,
		];
		if ($realLookups) {
			return new StorageClassifier(...$arguments);
		}

		$classifier = $this->getMockBuilder(StorageClassifier::class)
			->setConstructorArgs($arguments)
			->onlyMethods(['mountConfigs', 'neverConfigs', 'usersOfMounts'])
			->getMock();
		$classifier->method('mountConfigs')->willReturnCallback(
			fn (array $mountIds): array => array_intersect_key($this->configs, array_flip($mountIds)),
		);
		$classifier->method('neverConfigs')->willReturnCallback(fn (): array => $this->never);
		$classifier->method('usersOfMounts')->willReturnCallback(
			static fn (array $mountIds): array => array_fill_keys($mountIds, 1),
		);

		return $classifier;
	}

	/** @param list<array{string, int}> $mounts uid and mount id per row of oc_mounts */
	private function mounts(array $mounts, string $provider = StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER): void {
		$infos = [];
		foreach ($mounts as [$uid, $mountId]) {
			$info = $this->createMock(ICachedMountInfo::class);
			$info->method('getUser')->willReturn($this->user($uid));
			$info->method('getMountId')->willReturn($mountId);
			$info->method('getMountProvider')->willReturn($provider);
			$info->method('getStorageId')->willReturn(self::STORAGE);
			$infos[] = $info;
		}
		$this->mountCache->method('getMountsForStorageId')->with(self::STORAGE)->willReturn($infos);
	}

	private function config(string $auth, int $mountId = self::MOUNT, string $backend = 'smb', int $type = 1): void {
		$this->configs[$mountId] = ['backend' => $backend, 'auth' => $auth, 'type' => $type];
	}

	/** The probe finds this storage, as the active user. */
	private function storage(string $id = 'smb::ana@nas.local//Medien//', bool $available = true, ?int $numericId = self::STORAGE, bool $failed = false): IStorage&MockObject {
		$storage = $this->createMock(IStorage::class);
		$storage->method('getId')->willReturn($id);
		$storage->method('getAvailability')->willReturn(['available' => $available, 'last_checked' => 1]);
		$storage->method('instanceOfStorage')->willReturn($failed);
		$mount = $this->createMock(IMountPoint::class);
		$mount->method('getStorage')->willReturn($storage);
		$mount->method('getNumericStorageId')->willReturn($numericId);
		$this->mountManager->method('getMountFromMountInfo')->willReturnCallback(function () use ($mount): IMountPoint {
			$this->setUpAs[] = $this->active?->getUID() ?? '-';

			return $mount;
		});

		return $storage;
	}

	/** @return list<array{string}> */
	public static function neverCapturable(): array {
		return [['password::sessioncredentials'], ['smb::kerberosapache']];
	}

	#[DataProvider('neverCapturable')]
	public function testSessionAuthenticationIsNeverCapturableAndNothingIsAskedOrSetUp(string $auth): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->config($auth);
		$this->credentials->expects(self::never())->method('retrieve');
		$this->mountManager->expects(self::never())->method('getMountFromMountInfo');

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertFalse($state['capturable']);
		self::assertSame(StorageClassifier::REASON_SESSION_CREDENTIALS, $state['reason']);
		self::assertSame(self::MOUNT, $state['mountId']);
		self::assertSame($auth, $state['authKind']);
		self::assertSame(1, $state['users']);
		self::assertNull($state['shareKeyHash']);
	}

	public function testLoginCredentialsWithoutStoredCredentialsAreMissing(): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->config('password::logincredentials');
		$this->credentials->expects(self::once())->method('retrieve')
			->with('ana', 'password::logincredentials/credentials')->willReturn(null);
		$this->mountManager->expects(self::never())->method('getMountFromMountInfo');

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertFalse($state['capturable']);
		self::assertSame(StorageClassifier::REASON_CREDENTIALS_MISSING, $state['reason']);
	}

	/** @return array<string, array{string, int, array{string, string}}> */
	public static function stored(): array {
		return [
			'log-in credentials' => ['password::logincredentials', 1, ['ana', 'password::logincredentials/credentials']],
			'user provided' => ['password::userprovided', 1, ['ana', 'password::userprovided/' . self::MOUNT]],
			'global, admin mount' => ['password::global', 1, ['', 'password::global']],
			'global, personal mount' => ['password::global', 2, ['ana', 'password::global']],
			'global, user entered' => ['password::global::user', 1, ['ana', 'password::global']],
		];
	}

	/** @param array{string, string} $key */
	#[DataProvider('stored')]
	public function testStoredCredentialsAreLookedUpUnderTheKeyOfTheirAuthentication(string $auth, int $type, array $key): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->config($auth, type: $type);
		$this->credentials->expects(self::once())->method('retrieve')->with($key[0], $key[1])->willReturn(['user' => 'ana', 'password' => 'x']);
		$this->storage();

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertTrue($state['capturable']);
		self::assertNull($state['reason']);
	}

	public function testFixedCredentialsGoStraightToTheProbeAsTheUserOfTheMount(): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->config('password::password');
		$this->credentials->expects(self::never())->method('retrieve');
		$this->storage();

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertTrue($state['capturable']);
		self::assertSame(['ana'], $this->setUpAs);
		self::assertNull($this->active);
	}

	public function testACapturableSmbStorageStoresTheHashOfTheShareKeyAndTheRoot(): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->config('password::password');
		$this->storage('smb::ana@nas.local//Medien//gemeinsam/');

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertSame(StorageService::shareKeyHash('smb::nas.local//Medien'), $state['shareKeyHash']);
		self::assertSame('gemeinsam', $state['rootPrefix']);
		self::assertSame(StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER, $state['provider']);
		self::assertSame(self::NOW, $state['checkedAt']);
		self::assertStringNotContainsString('nas.local', (string)json_encode($state));
	}

	public function testALocalExternalStorageIsCapturableWithoutAShareKey(): void {
		$this->mounts([['ana', self::MOUNT], ['cem', self::MOUNT]]);
		$this->config('null::null', backend: 'local');
		$this->storage('local::/srv/medien/');

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertTrue($state['capturable']);
		self::assertNull($state['shareKeyHash']);
		self::assertNull($state['rootPrefix']);
		self::assertSame(2, $state['users']);
		self::assertSame(['ana'], $this->setUpAs);
	}

	/** @return array<string, array{string, bool, ?int, bool}> */
	public static function unavailable(): array {
		return [
			'failed storage by id' => ['failedstorage', true, self::STORAGE, false],
			'failed storage wrapped' => ['smb::ana@nas.local//Medien//', true, self::STORAGE, true],
			'not available' => ['smb::ana@nas.local//Medien//', false, self::STORAGE, false],
			'another storage behind the mount' => ['smb::ana@nas.local//Medien//', true, 99, false],
		];
	}

	#[DataProvider('unavailable')]
	public function testAProbeThatFindsNoUsableStorageMeansUnavailable(string $id, bool $available, ?int $numericId, bool $failed): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->config('password::password');
		$this->storage($id, $available, $numericId, $failed);

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertFalse($state['capturable']);
		self::assertSame(StorageClassifier::REASON_UNAVAILABLE, $state['reason']);
		self::assertNull($state['shareKeyHash']);
	}

	public function testAProbeThatThrowsMeansUnavailableAndTheActiveUserIsBack(): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->config('password::password');
		$this->mountManager->method('getMountFromMountInfo')->willThrowException(new \RuntimeException('smb://ana:secret@nas.local/Medien timed out'));
		$this->logger->expects(self::once())->method('info')->with(
			self::anything(),
			self::callback(static fn (array $context): bool => !str_contains((string)json_encode($context), 'nas.local')),
		);

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertSame(StorageClassifier::REASON_UNAVAILABLE, $state['reason']);
		self::assertNull($this->active);
	}

	public function testFilesExternalSwitchedOffMeansUnavailable(): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->apps = $this->createMock(IAppManager::class);
		$this->apps->method('isEnabledForAnyone')->with('files_external')->willReturn(false);
		$this->db->expects(self::never())->method('getQueryBuilder');
		$this->mountManager->expects(self::never())->method('getMountFromMountInfo');

		$state = $this->classifier(true)->classify(self::STORAGE);

		self::assertFalse($state['capturable']);
		self::assertSame(StorageClassifier::REASON_UNAVAILABLE, $state['reason']);
	}

	public function testAConfigurationQueryThatThrowsMeansUnavailable(): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->db->method('getQueryBuilder')->willThrowException(new \RuntimeException('table external_mounts missing'));
		$this->mountManager->expects(self::never())->method('getMountFromMountInfo');

		$state = $this->classifier(true)->classify(self::STORAGE);

		self::assertFalse($state['capturable']);
		self::assertSame(StorageClassifier::REASON_UNAVAILABLE, $state['reason']);
	}

	public function testAStorageWithoutExternalMountsOrWithoutItsConfigurationIsUnavailable(): void {
		$this->mounts([['ana', self::MOUNT]], 'OCA\GroupFolders\Mount\MountProvider');
		self::assertSame(StorageClassifier::REASON_UNAVAILABLE, $this->classifier()->classify(self::STORAGE)['reason']);
	}

	public function testAConfigurationThatIsGoneIsUnavailable(): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->mountManager->expects(self::never())->method('getMountFromMountInfo');

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertFalse($state['capturable']);
		self::assertSame(StorageClassifier::REASON_UNAVAILABLE, $state['reason']);
		self::assertNull($state['mountId']);
	}

	public function testTwoConfigurationsOfOneStoragePreferTheOneThatWorksInTheBackground(): void {
		$this->mounts([['ana', 3], ['ana', 2]]);
		$this->config('password::sessioncredentials', 2);
		$this->config('password::logincredentials', 3);
		$this->credentials->method('retrieve')->willReturn(['user' => 'ana', 'password' => 'x']);
		$this->storage();

		$state = $this->classifier()->classify(self::STORAGE);

		self::assertTrue($state['capturable']);
		self::assertSame(3, $state['mountId']);
	}

	public function testTheFirstUserWithStoredCredentialsIsTheOneProbed(): void {
		$this->mounts([['cem', self::MOUNT], ['ben', self::MOUNT]]);
		$this->config('password::logincredentials');
		$this->credentials->method('retrieve')->willReturnCallback(static fn (string $uid): ?array => $uid === 'cem' ? ['user' => 'cem'] : null);
		$this->storage();

		self::assertTrue($this->classifier()->classify(self::STORAGE)['capturable']);
		self::assertSame(['cem'], $this->setUpAs);
	}

	public function testABrokenCredentialsStoreMeansUnavailableNotMissing(): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->config('password::logincredentials');
		$this->credentials->method('retrieve')->willThrowException(new \RuntimeException('cannot decrypt'));

		self::assertSame(StorageClassifier::REASON_UNAVAILABLE, $this->classifier()->classify(self::STORAGE)['reason']);
	}

	/**
	 * @return array{storageId: int, mountId: ?int, provider: string, shareKeyHash: ?string, rootPrefix: ?string, authKind: ?string, capturable: bool, reason: ?string, users: int, checkedAt: ?int}
	 */
	private static function row(bool $capturable, ?string $reason, int $checkedAt, ?int $mountId = self::MOUNT, string $auth = 'password::logincredentials', int $users = 1): array {
		return [
			'storageId' => self::STORAGE,
			'mountId' => $mountId,
			'provider' => StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER,
			'shareKeyHash' => null,
			'rootPrefix' => null,
			'authKind' => $auth,
			'capturable' => $capturable,
			'reason' => $reason,
			'users' => $users,
			'checkedAt' => $checkedAt,
		];
	}

	public function testDueIsNewOldOrSkippedForWantOfCredentials(): void {
		$classifier = $this->classifier();

		self::assertTrue($classifier->isDue(null));
		self::assertFalse($classifier->isDue(self::row(true, null, self::NOW - 3600)));
		self::assertTrue($classifier->isDue(self::row(true, null, self::NOW - StorageClassifier::RECHECK_SECONDS)));
		self::assertFalse($classifier->isDue(self::row(false, StorageClassifier::REASON_UNAVAILABLE, self::NOW - 3600)));
		self::assertTrue($classifier->isDue(self::row(false, StorageClassifier::REASON_CREDENTIALS_MISSING, self::NOW - 60)));
		self::assertTrue($classifier->isDue(self::row(false, StorageClassifier::REASON_SESSION_CREDENTIALS, self::NOW - 60)));
	}

	public function testRefreshWritesTheResultAndSaysWhenTheStorageBecameCapturable(): void {
		$this->mounts([['ana', self::MOUNT]]);
		$this->config('password::logincredentials');
		$this->credentials->method('retrieve')->willReturn(['user' => 'ana']);
		$this->storage();
		$this->states->method('find')->willReturn(self::row(false, StorageClassifier::REASON_CREDENTIALS_MISSING, self::NOW - 300));
		$this->states->expects(self::once())->method('store')->with(self::callback(
			static fn (array $state): bool => $state['capturable'] === true && $state['storageId'] === self::STORAGE,
		));

		self::assertSame(['capturable' => true, 'becameCapturable' => true, 'checked' => true], $this->classifier()->refresh(self::STORAGE));
	}

	public function testRefreshOfAStorageThatIsNotDueOnlyReads(): void {
		$this->states->method('find')->willReturn(self::row(true, null, self::NOW - 60));
		$this->states->expects(self::never())->method('store');
		$this->mountCache->expects(self::never())->method('getMountsForStorageId');

		self::assertSame(['capturable' => true, 'becameCapturable' => false, 'checked' => false], $this->classifier()->refresh(self::STORAGE));
	}

	public function testRefreshWithoutTimeLeftOnlyReadsAndAnUnknownStorageStaysNotCapturable(): void {
		$this->states->method('find')->willReturn(null);
		$this->states->expects(self::never())->method('store');

		self::assertSame(['capturable' => false, 'becameCapturable' => false, 'checked' => false], $this->classifier()->refresh(self::STORAGE, false));
	}

	public function testSkippedListsConfigurationsWithReasonAndUsersAndNeverAPath(): void {
		$this->states->method('skipped')->willReturn([
			self::row(false, StorageClassifier::REASON_CREDENTIALS_MISSING, 1, 4, 'password::logincredentials', 1),
			self::row(false, StorageClassifier::REASON_CREDENTIALS_MISSING, 1, 4, 'password::logincredentials', 1),
			self::row(false, StorageClassifier::REASON_UNAVAILABLE, 1, 5, 'password::password', 2),
		]);
		$this->config('password::logincredentials', 4, 'smb');
		$this->config('password::password', 5, 'sftp');
		$this->config('password::sessioncredentials', 2, 'smb');
		$this->never = [2 => ['backend' => 'smb', 'auth' => 'password::sessioncredentials', 'type' => 1]];

		$skipped = $this->classifier()->skipped();

		self::assertSame([
			['mountId' => 2, 'backend' => 'smb', 'authKind' => 'password::sessioncredentials', 'reason' => 'session_credentials', 'users' => 1],
			['mountId' => 4, 'backend' => 'smb', 'authKind' => 'password::logincredentials', 'reason' => 'credentials_missing', 'users' => 2],
			['mountId' => 5, 'backend' => 'sftp', 'authKind' => 'password::password', 'reason' => 'unavailable', 'users' => 2],
		], $skipped);
		foreach ($skipped as $entry) {
			self::assertSame(['mountId', 'backend', 'authKind', 'reason', 'users'], array_keys($entry));
		}
	}

	public function testASessionConfigurationThatIsAlsoClassifiedIsListedOnce(): void {
		$this->states->method('skipped')->willReturn([
			self::row(false, StorageClassifier::REASON_SESSION_CREDENTIALS, 1, 2, 'password::sessioncredentials', 3),
		]);
		$this->config('password::sessioncredentials', 2, 'smb');
		$this->never = [2 => ['backend' => 'smb', 'auth' => 'password::sessioncredentials', 'type' => 1]];

		self::assertSame(
			[['mountId' => 2, 'backend' => 'smb', 'authKind' => 'password::sessioncredentials', 'reason' => 'session_credentials', 'users' => 3]],
			$this->classifier()->skipped(),
		);
	}

	public function testAnIdentifierThatLooksLikeFreeTextIsPrintedAsUnknown(): void {
		$this->states->method('skipped')->willReturn([
			self::row(false, StorageClassifier::REASON_UNAVAILABLE, 1, 6, 'smb://nas.local/Medien weird'),
		]);
		$this->config('x', 6, '/srv/medien');

		$entry = $this->classifier()->skipped()[0];

		self::assertSame('unknown', $entry['backend']);
		self::assertSame('unknown', $entry['authKind']);
	}
}
