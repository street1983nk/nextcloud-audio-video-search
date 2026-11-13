<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Command\ExcludeCommand;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\Exceptions\AppConfigTypeConflictException;
use OCP\Files\Cache\ICacheEntry;
use OCP\Files\Cache\IFileAccess;
use OCP\Files\Config\ICachedMountInfo;
use OCP\Files\Config\IUserMountCache;
use OCP\IAppConfig;
use OCP\IDBConnection;
use OCP\IGroupManager;
use OCP\IUser;
use OCP\IUserManager;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\ArrayInput;
use Symfony\Component\Console\Output\BufferedOutput;

/**
 * The exclusions (DISC-03, D-02-05, D-02-08, D-02-11) and the switch for
 * external storages (DISC-02): what the four lists leave out, that every
 * doubt excludes, and occ audio_video_search:exclude.
 *
 * Everything is a double. The app config is a small store in this class, the
 * mount cache a table of (user, provider, mount id) per storage:
 *
 *   3   the home of eva, one file of it shared with ana
 *   4   the home of ana, one file of it shared with eva
 *   5   a team folder of ana and eva
 *   7   the storage of ben on the SMB configuration 1 of the admin (login credentials)
 *   8   the storage of ana on the same configuration 1
 *   9   a local external storage, configuration 2, one storage for ana, ben and cem
 *   11  a storage of ana that the configurations 3 and 4 both reach
 */
#[CoversClass(ExclusionService::class)]
#[CoversClass(ExcludeCommand::class)]
final class ExclusionServiceTest extends TestCase {
	private const HOME = 'OC\Files\Mount\LocalHomeMountProvider';
	private const SHARE = 'OCA\Files_Sharing\MountProvider';
	private const TEAM = 'OCA\GroupFolders\Mount\MountProvider';
	private const EXTERNAL = StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER;

	private IAppConfig&MockObject $appConfig;
	private IUserMountCache&MockObject $mountCache;
	private IGroupManager&MockObject $groups;
	private IFileAccess&MockObject $fileAccess;
	private StorageService&MockObject $storage;
	private LoggerInterface&MockObject $logger;

	/** @var array<string, mixed> the app config: text, or another type for a key stored with one */
	private array $stored = [];
	/** @var list<array{string, string}> key and text of every write */
	private array $writes = [];
	/** @var list<string> */
	private array $deleted = [];
	/** @var array<int, list<array{string, string, ?int}>> user, provider and mount id per storage */
	private array $mounts = [];
	private int $mountQueries = 0;
	private bool $mountCacheFails = false;
	/** @var array<string, list<string>> members per group */
	private array $members = [];
	private int $groupQueries = 0;
	private bool $groupsFail = false;
	/** @var array<int, array{int, string}> storage id and internal path per file id */
	private array $cacheEntries = [];
	private bool $fileCacheFails = false;
	/** @var list<int> the mount ids files_external knows */
	private array $configured = [];
	/** @var list<int> */
	private array $lookedUp = [];
	/** @var list<string> every log line with its context, as one text */
	private array $logged = [];

	protected function setUp(): void {
		parent::setUp();

		$this->stored = [];
		$this->writes = [];
		$this->deleted = [];
		$this->mounts = [
			3 => [['ana', self::SHARE, null], ['eva', self::HOME, null]],
			4 => [['ana', self::HOME, null], ['eva', self::SHARE, null]],
			5 => [['ana', self::TEAM, null], ['eva', self::TEAM, null]],
			7 => [['ben', self::EXTERNAL, 1]],
			8 => [['ana', self::EXTERNAL, 1]],
			9 => [['ana', self::EXTERNAL, 2], ['ben', self::EXTERNAL, 2], ['cem', self::EXTERNAL, 2]],
			11 => [['ana', self::EXTERNAL, 3], ['ana', self::EXTERNAL, 4]],
		];
		$this->mountQueries = 0;
		$this->mountCacheFails = false;
		$this->members = [];
		$this->groupQueries = 0;
		$this->groupsFail = false;
		$this->cacheEntries = [];
		$this->fileCacheFails = false;
		$this->configured = [];
		$this->lookedUp = [];
		$this->logged = [];

		$this->appConfig = $this->createMock(IAppConfig::class);
		$this->appConfig->method('getValueString')->willReturnCallback(
			function (string $app, string $key, string $default = ''): string {
				self::assertSame(Application::APP_ID, $app);
				$value = $this->stored[$key] ?? $default;
				if (!is_string($value)) {
					throw new AppConfigTypeConflictException('stored with another type');
				}

				return $value;
			},
		);
		$this->appConfig->method('getValueArray')->willReturnCallback(
			function (string $app, string $key, array $default = []): array {
				self::assertSame(Application::APP_ID, $app);
				$value = $this->stored[$key] ?? $default;
				if (!is_array($value)) {
					throw new AppConfigTypeConflictException('stored with another type');
				}

				return $value;
			},
		);
		$this->appConfig->method('setValueString')->willReturnCallback(
			function (string $app, string $key, string $value): bool {
				self::assertSame(Application::APP_ID, $app);
				if (array_key_exists($key, $this->stored) && !is_string($this->stored[$key])) {
					throw new AppConfigTypeConflictException('stored with another type');
				}
				$this->stored[$key] = $value;
				$this->writes[] = [$key, $value];

				return true;
			},
		);
		$this->appConfig->method('deleteKey')->willReturnCallback(function (string $app, string $key): void {
			unset($this->stored[$key]);
			$this->deleted[] = $key;
		});

		$this->mountCache = $this->createMock(IUserMountCache::class);
		$this->mountCache->method('getMountsForStorageId')->willReturnCallback(function (int $storageId): array {
			$this->mountQueries++;
			if ($this->mountCacheFails) {
				throw new \RuntimeException('mount cache gone for eva');
			}
			$infos = [];
			foreach ($this->mounts[$storageId] ?? [] as [$uid, $provider, $mountId]) {
				$user = $this->createMock(IUser::class);
				$user->method('getUID')->willReturn($uid);
				$info = $this->createMock(ICachedMountInfo::class);
				$info->method('getUser')->willReturn($user);
				$info->method('getMountProvider')->willReturn($provider);
				$info->method('getMountId')->willReturn($mountId);
				$infos[] = $info;
			}

			return $infos;
		});

		$this->groups = $this->createMock(IGroupManager::class);
		$this->groups->method('isInGroup')->willReturnCallback(function (string $uid, string $gid): bool {
			$this->groupQueries++;
			if ($this->groupsFail) {
				throw new \RuntimeException('group backend gone for extern');
			}

			return in_array($uid, $this->members[$gid] ?? [], true);
		});

		$this->fileAccess = $this->createMock(IFileAccess::class);
		$this->fileAccess->method('getByFileId')->willReturnCallback(function (int $fileId): ?ICacheEntry {
			if ($this->fileCacheFails) {
				throw new \RuntimeException('file cache gone for privat/a.mp3');
			}
			if (!isset($this->cacheEntries[$fileId])) {
				return null;
			}
			[$storageId, $internalPath] = $this->cacheEntries[$fileId];
			$entry = $this->createMock(ICacheEntry::class);
			$entry->method('getStorageId')->willReturn($storageId);
			$entry->method('getPath')->willReturn($internalPath);

			return $entry;
		});

		// Homes are walked from their files folder, every other mount from its root.
		$this->storage = $this->createMock(StorageService::class);
		$this->storage->method('mountRelativePath')->willReturnCallback(
			static fn (int $storageId, string $internalPath): ?string => match (true) {
				!in_array($storageId, [3, 4], true) => $internalPath,
				str_starts_with($internalPath, 'files/') => substr($internalPath, 6),
				default => null,
			},
		);

		$this->logger = $this->createMock(LoggerInterface::class);
		foreach (['debug', 'info', 'notice', 'warning', 'error'] as $level) {
			$this->logger->method($level)->willReturnCallback(function (string|\Stringable $message, array $context = []): void {
				$this->logged[] = $message . ' ' . json_encode($context);
			});
		}
	}

	/** The service with the lookup of a mount configuration replaced by $this->configured. */
	private function service(): ExclusionService&MockObject {
		$service = $this->getMockBuilder(ExclusionService::class)
			->setConstructorArgs($this->constructorArguments($this->createMock(IDBConnection::class)))
			->onlyMethods(['mountConfigured'])
			->getMock();
		$service->method('mountConfigured')->willReturnCallback(function (int $mountId): bool {
			$this->lookedUp[] = $mountId;

			return in_array($mountId, $this->configured, true);
		});

		return $service;
	}

	/** @return list<mixed> */
	private function constructorArguments(IDBConnection $db): array {
		return [$this->appConfig, $this->mountCache, $this->groups, $this->fileAccess, $this->storage, $db, $this->logger];
	}

	/** @param list<mixed> $entries */
	private function store(string $list, array $entries): void {
		$this->stored[$list] = json_encode($entries, JSON_THROW_ON_ERROR);
	}

	// -- folders ----------------------------------------------------------------

	public function testAFolderPrefixLeavesOutThatFolderInEveryHomeAndNoNameThatOnlyBeginsTheSame(): void {
		$this->store(ExclusionService::LIST_FOLDERS, ['privat']);
		$this->cacheEntries = [
			31 => [3, 'files/privat/a.mp3'],
			41 => [4, 'files/privat/tief/unten/b.mp3'],
			42 => [4, 'files/privatsache/a.mp3'],
			43 => [4, 'files/Sitzung/privat/a.mp3'],
			51 => [5, 'privat/c.mp3'],
			91 => [9, 'privat'],
		];
		$service = $this->service();

		self::assertTrue($service->isExcludedFile(31));
		self::assertTrue($service->isExcludedFile(41));
		self::assertFalse($service->isExcludedFile(42));
		self::assertFalse($service->isExcludedFile(43));
		self::assertTrue($service->isExcludedFile(51));
		self::assertTrue($service->isExcludedFile(91));

		self::assertTrue($service->isExcluded(4, 'privat/a.mp3'));
		self::assertTrue($service->isExcluded(4, '/privat//a.mp3'));
		self::assertFalse($service->isExcluded(4, 'privatsache/a.mp3'));
		self::assertFalse($service->isExcluded(4, 'Privat/a.mp3'));
		self::assertFalse($service->isExcluded(4, ''));
		// A rule about folders alone asks the mount cache nothing.
		self::assertSame(0, $this->mountQueries);
	}

	public function testAPrefixWrittenWithTheFilesFolderOfAHomeAlsoCountsWithoutIt(): void {
		$this->store(ExclusionService::LIST_FOLDERS, ['files/privat']);
		$service = $this->service();

		self::assertTrue($service->isExcluded(4, 'privat/a.mp3'));
		self::assertTrue($service->isExcluded(9, 'files/privat/a.mp3'));
		self::assertFalse($service->isExcluded(4, 'privatsache/a.mp3'));
		self::assertFalse($service->isExcluded(4, 'filesprivat/a.mp3'));
	}

	/** @return array<string, array{string, string}> */
	public static function unusableFolders(): array {
		return [
			'parent first' => ['../geheim', ExclusionService::ERROR_TRAVERSAL],
			'parent inside' => ['Archiv/../..', ExclusionService::ERROR_TRAVERSAL],
			'parent last' => ['Archiv/..', ExclusionService::ERROR_TRAVERSAL],
			'self first' => ['./Archiv', ExclusionService::ERROR_TRAVERSAL],
			'self inside' => ['Archiv/./x', ExclusionService::ERROR_TRAVERSAL],
			'empty' => ['', ExclusionService::ERROR_EMPTY],
			'blank' => ['   ', ExclusionService::ERROR_EMPTY],
			'slashes only' => ['///', ExclusionService::ERROR_EMPTY],
			'too long' => [str_repeat('a', ExclusionService::MAX_ENTRY_LENGTH + 1), ExclusionService::ERROR_TOO_LONG],
			'line feed' => ["Archiv\nprivat", ExclusionService::ERROR_INVALID],
			'zero byte' => ["Archiv\0", ExclusionService::ERROR_INVALID],
			'not utf-8' => ["Archiv\xFF", ExclusionService::ERROR_INVALID],
		];
	}

	#[DataProvider('unusableFolders')]
	public function testAFolderThatIsNoUsablePrefixIsRefusedAndNeverWritten(string $entry, string $code): void {
		$service = $this->service();

		self::assertSame([$code], $service->validate(ExclusionService::LIST_FOLDERS, [$entry]));
		self::assertNull($service->normalise(ExclusionService::LIST_FOLDERS, $entry));
		self::assertSame($code, $service->add(ExclusionService::LIST_FOLDERS, $entry));
		self::assertSame([], $this->writes);
	}

	/**
	 * Every list, four control characters, three places. The edges are the
	 * point (plan 02-16b): trim() used to drop the character there before
	 * anything looked at it, and the entry was stored without it.
	 *
	 * @return array<string, array{string, string, string}> the list, the entry and the same entry without the character
	 */
	public static function controlCharacters(): array {
		$clean = [
			ExclusionService::LIST_USERS => 'eva',
			ExclusionService::LIST_GROUPS => 'extern',
			ExclusionService::LIST_FOLDERS => 'privat',
			ExclusionService::LIST_MOUNTS => '37',
		];
		$characters = ['zero byte' => "\0", 'tab' => "\t", 'line feed' => "\n", 'carriage return' => "\r"];

		$sets = [];
		foreach ($clean as $list => $entry) {
			foreach ($characters as $name => $character) {
				$sets[$list . ', ' . $name . ' first'] = [$list, $character . $entry, $entry];
				$sets[$list . ', ' . $name . ' last'] = [$list, $entry . $character, $entry];
				$sets[$list . ', ' . $name . ' inside'] = [$list, substr($entry, 0, 1) . $character . substr($entry, 1), $entry];
			}
		}

		return $sets;
	}

	#[DataProvider('controlCharacters')]
	public function testAnEntryWithAControlCharacterIsRefusedInEveryListAtEveryPlaceAndNeverWritten(string $list, string $entry, string $clean): void {
		$this->configured = [37];
		$service = $this->service();

		self::assertSame([ExclusionService::ERROR_INVALID], $service->validate($list, [$entry]));
		self::assertNull($service->normalise($list, $entry));
		self::assertSame(ExclusionService::ERROR_INVALID, $service->add($list, $entry));
		self::assertSame([], $this->writes);
		// Refused before files_external is asked about a mount id.
		self::assertSame([], $this->lookedUp);

		// The rule without the character is in force: the entry with it is
		// not that rule, so it takes nothing out.
		$this->store($list, [$clean]);
		$service = $this->service();
		self::assertSame(ExclusionService::RESULT_ABSENT, $service->remove($list, $entry));
		self::assertSame([$clean], $service->entries($list));
		self::assertSame([], $this->writes);

		// Written by occ config:app:set, such an entry makes the list unreadable.
		$this->store($list, [$clean, $entry]);
		$service = $this->service();
		self::assertNull($service->entries($list));
		self::assertTrue($service->isExcludedUser('ana'));
	}

	public function testOrdinarySpacesAtTheEdgesAreDroppedInEveryListAndNothingElseIs(): void {
		$this->configured = [37];
		$service = $this->service();

		self::assertSame('eva', $service->normalise(ExclusionService::LIST_USERS, '  eva '));
		self::assertSame('eva maria', $service->normalise(ExclusionService::LIST_USERS, ' eva maria '));
		self::assertSame('extern', $service->normalise(ExclusionService::LIST_GROUPS, ' extern  '));
		self::assertSame('privat', $service->normalise(ExclusionService::LIST_FOLDERS, ' privat '));
		self::assertSame('37', $service->normalise(ExclusionService::LIST_MOUNTS, ' 37 '));

		self::assertSame(ExclusionService::RESULT_ADDED, $service->add(ExclusionService::LIST_MOUNTS, ' 37 '));
		self::assertSame('["37"]', $this->stored[ExclusionService::LIST_MOUNTS]);

		// White space that is no space is a control character, not an empty entry.
		foreach (ExclusionService::LISTS as $list) {
			self::assertSame([ExclusionService::ERROR_INVALID], $service->validate($list, ["\t"]), $list);
			self::assertSame([ExclusionService::ERROR_INVALID], $service->validate($list, [" \n "]), $list);
			self::assertSame([ExclusionService::ERROR_EMPTY], $service->validate($list, ['   ']), $list);
		}
	}

	public function testAFolderIsStoredInOneSpelling(): void {
		$service = $this->service();

		self::assertSame('Archiv/2024', $service->normalise(ExclusionService::LIST_FOLDERS, '/Archiv//2024/'));
		self::assertSame('privat', $service->normalise(ExclusionService::LIST_FOLDERS, '  privat  '));
		self::assertSame('a\b', $service->normalise(ExclusionService::LIST_FOLDERS, 'a\b'));
		self::assertSame('...', $service->normalise(ExclusionService::LIST_FOLDERS, '...'));
		self::assertSame(str_repeat('a', 256), $service->normalise(ExclusionService::LIST_FOLDERS, str_repeat('a', 256)));
	}

	public function testADecomposedNameMeetsTheComposedNameOfTheFileCache(): void {
		if (!class_exists(\Normalizer::class)) {
			self::markTestSkipped('intl is not loaded');
		}
		$decomposed = "Cafe\u{0301}";
		$composed = "Caf\u{00E9}";
		$this->store(ExclusionService::LIST_FOLDERS, [$decomposed]);
		$service = $this->service();

		self::assertSame($composed, $service->normalise(ExclusionService::LIST_FOLDERS, $decomposed));
		self::assertTrue($service->isExcluded(4, $composed . '/a.mp3'));
		self::assertTrue($service->isExcluded(4, $decomposed . '/a.mp3'));
	}

	// -- the bounds and duplicates ----------------------------------------------

	public function testAListHoldsSixtyFourEntriesOfTwoHundredFiftySixBytesAndNoMore(): void {
		$full = [];
		for ($i = 0; $i < ExclusionService::MAX_ENTRIES; $i++) {
			$full[] = str_pad('u' . $i, ExclusionService::MAX_ENTRY_LENGTH, 'x');
		}
		$service = $this->service();

		self::assertSame([], $service->validate(ExclusionService::LIST_USERS, $full));
		self::assertSame([ExclusionService::ERROR_TOO_MANY], $service->validate(ExclusionService::LIST_USERS, [...$full, 'one more']));
		self::assertSame([ExclusionService::ERROR_TOO_LONG], $service->validate(ExclusionService::LIST_GROUPS, [str_repeat('g', 257)]));

		$this->store(ExclusionService::LIST_USERS, $full);
		$service = $this->service();
		self::assertSame($full, $service->entries(ExclusionService::LIST_USERS));
		self::assertSame(ExclusionService::ERROR_TOO_MANY, $service->add(ExclusionService::LIST_USERS, 'one more'));
		self::assertSame([], $this->writes);
	}

	public function testTheSameEntryTwiceIsRefused(): void {
		$service = $this->service();

		self::assertSame([ExclusionService::ERROR_DUPLICATE], $service->validate(ExclusionService::LIST_FOLDERS, ['privat', '/privat/']));
		self::assertSame([ExclusionService::ERROR_DUPLICATE], $service->validate(ExclusionService::LIST_USERS, ['Eva', 'eva']));
		self::assertSame([], $service->validate(ExclusionService::LIST_GROUPS, ['Extern', 'extern']));

		$this->store(ExclusionService::LIST_USERS, ['eva']);
		$service = $this->service();
		self::assertSame(ExclusionService::ERROR_DUPLICATE, $service->add(ExclusionService::LIST_USERS, 'EVA'));
		self::assertSame([], $this->writes);
	}

	public function testAStoredListThatNamesAnEntryTwiceIsOneRuleAndStaysReadable(): void {
		$this->store(ExclusionService::LIST_USERS, ['eva', 'eva']);
		$service = $this->service();

		self::assertSame(['eva'], $service->entries(ExclusionService::LIST_USERS));
		self::assertTrue($service->isExcludedUser('eva'));
		self::assertFalse($service->isExcludedUser('ana'));
	}

	// -- users and groups -------------------------------------------------------

	public function testAUserIsExcludedByNameWithoutRegardToCaseAndAsAMemberOfAGroup(): void {
		$this->store(ExclusionService::LIST_USERS, ['Eva']);
		$this->store(ExclusionService::LIST_GROUPS, ['extern']);
		$this->members = ['extern' => ['fritz'], 'team' => ['ana']];
		$service = $this->service();

		self::assertTrue($service->isExcludedUser('eva'));
		self::assertTrue($service->isExcludedUser('EVA'));
		self::assertTrue($service->isExcludedUser('fritz'));
		self::assertFalse($service->isExcludedUser('ana'));
		self::assertFalse($service->isExcludedUser(''));
	}

	public function testWithoutARuleNobodyIsExcludedAndNobodyIsAsked(): void {
		$service = $this->service();

		self::assertFalse($service->isExcludedUser('ana'));
		self::assertFalse($service->isExcluded(7, 'a.mp3'));
		self::assertFalse($service->isExcluded(3, 'privat/a.mp3'));
		self::assertSame(0, $this->groupQueries);
		self::assertSame(0, $this->mountQueries);
		self::assertSame([], $this->logged);
	}

	public function testAStorageBelongsToTheUserOfItsHomeOrToTheOneUserItWasBuiltFor(): void {
		$service = $this->service();

		self::assertSame('eva', $service->storageOwner(3));
		self::assertSame('ana', $service->storageOwner(4));
		self::assertNull($service->storageOwner(5));
		self::assertSame('ben', $service->storageOwner(7));
		self::assertSame('ana', $service->storageOwner(8));
		self::assertNull($service->storageOwner(9));
		self::assertNull($service->storageOwner(99));
	}

	public function testAnExcludedUserLosesTheirOwnStoragesAndNothingOthersShareWithThem(): void {
		$this->store(ExclusionService::LIST_USERS, ['eva']);
		$service = $this->service();

		// Her home, also the file of it she shared with ana.
		self::assertTrue($service->isExcluded(3, 'a.mp3'));
		// The home of ana, of which eva has a share (D-02-08).
		self::assertFalse($service->isExcluded(4, 'a.mp3'));
		// A team folder she is a member of.
		self::assertFalse($service->isExcluded(5, 'a.mp3'));
	}

	public function testAnExcludedGroupTakesTheStoragesOfEachMember(): void {
		$this->store(ExclusionService::LIST_GROUPS, ['extern']);
		$this->members = ['extern' => ['ben']];
		$service = $this->service();

		self::assertTrue($service->isExcluded(7, 'a.mp3'));
		self::assertFalse($service->isExcluded(8, 'a.mp3'));
		self::assertFalse($service->isExcluded(9, 'a.mp3'));
	}

	public function testOnAConfigurationWithTheLoginOfEachUserOnlyTheStorageOfTheExcludedUserGoes(): void {
		// D-02-11: configuration 1 of the admin builds one storage per user.
		$this->store(ExclusionService::LIST_USERS, ['ben']);
		$service = $this->service();

		self::assertTrue($service->isExcluded(7, 'Sitzung/a.mp3'));
		self::assertFalse($service->isExcluded(8, 'Sitzung/a.mp3'));
		// One storage for three users belongs to none of them.
		self::assertFalse($service->isExcluded(9, 'a.mp3'));
	}

	// -- external storages ------------------------------------------------------

	public function testASwitchedOffMountConfigurationTakesEveryStorageBuiltFromIt(): void {
		$this->store(ExclusionService::LIST_MOUNTS, ['1']);
		$service = $this->service();

		self::assertTrue($service->isExcluded(7, 'a.mp3'));
		self::assertTrue($service->isExcluded(8, 'a.mp3'));
		self::assertTrue($service->isExcluded(8, ''));
		self::assertFalse($service->isExcluded(9, 'a.mp3'));
		self::assertFalse($service->isExcluded(3, 'a.mp3'));
	}

	public function testAMountIdWrittenAsANumberIsTheSameRule(): void {
		$this->stored[ExclusionService::LIST_MOUNTS] = '[2]';
		$service = $this->service();

		self::assertSame(['2'], $service->entries(ExclusionService::LIST_MOUNTS));
		self::assertTrue($service->isExcluded(9, 'a.mp3'));
		self::assertFalse($service->isExcluded(7, 'a.mp3'));
	}

	public function testOneSwitchedOffConfigurationIsEnoughWhenTwoReachTheSameStorage(): void {
		$this->store(ExclusionService::LIST_MOUNTS, ['4']);

		self::assertTrue($this->service()->isExcluded(11, 'a.mp3'));
	}

	public function testTheMountCacheIsAskedOncePerStorage(): void {
		$this->store(ExclusionService::LIST_USERS, ['eva']);
		$service = $this->service();

		self::assertTrue($service->isExcluded(3, 'a.mp3'));
		self::assertTrue($service->isExcluded(3, 'b.mp3'));
		self::assertTrue($service->isExcluded(3, 'tief/c.mp3'));
		self::assertSame(1, $this->mountQueries);
	}

	// -- every doubt excludes ---------------------------------------------------

	/** @return array<string, array{string, mixed}> */
	public static function unreadableLists(): array {
		$tooMany = [];
		for ($i = 0; $i <= ExclusionService::MAX_ENTRIES; $i++) {
			$tooMany[] = 'u' . $i;
		}

		return [
			'no json' => [ExclusionService::LIST_USERS, 'eva'],
			'a json text' => [ExclusionService::LIST_USERS, '"eva"'],
			'a json object' => [ExclusionService::LIST_GROUPS, '{"gid":"extern"}'],
			'a list in a list' => [ExclusionService::LIST_USERS, '[["eva"]]'],
			'null as entry' => [ExclusionService::LIST_USERS, '[null]'],
			'true as entry' => [ExclusionService::LIST_GROUPS, '[true]'],
			'an empty entry' => [ExclusionService::LIST_USERS, '["eva",""]'],
			'a traversal' => [ExclusionService::LIST_FOLDERS, '["privat","../x"]'],
			'an entry too long' => [ExclusionService::LIST_FOLDERS, json_encode([str_repeat('a', 257)])],
			'mount id zero' => [ExclusionService::LIST_MOUNTS, '[0]'],
			'mount id as word' => [ExclusionService::LIST_MOUNTS, '["drei"]'],
			'more than the ceiling' => [ExclusionService::LIST_USERS, json_encode($tooMany)],
			'stored as a number' => [ExclusionService::LIST_FOLDERS, 7],
			'stored as a map' => [ExclusionService::LIST_USERS, ['uid' => 'eva']],
		];
	}

	#[DataProvider('unreadableLists')]
	public function testAListThatCannotBeReadInFullExcludesEverything(string $list, mixed $stored): void {
		$this->stored[$list] = $stored;
		$this->cacheEntries = [41 => [4, 'files/a.mp3']];
		$service = $this->service();

		self::assertNull($service->entries($list));
		self::assertTrue($service->isExcluded(4, 'a.mp3'));
		self::assertTrue($service->isExcluded(5, 'a.mp3'));
		self::assertTrue($service->isExcludedFile(41));
		self::assertTrue($service->isExcludedUser('ana'));
		self::assertSame(hash('sha256', "\0unreadable"), $service->fingerprint());
		self::assertSame(ExclusionService::ERROR_UNREADABLE, $service->add($list, 'ben'));
		self::assertSame(ExclusionService::ERROR_UNREADABLE, $service->remove($list, 'ben'));
		self::assertSame([], $this->writes);
		self::assertSame([], $this->deleted);
	}

	public function testAnUnreadableListIsLoggedOnceWithItsNameAndNothingOfItsContent(): void {
		$this->stored[ExclusionService::LIST_FOLDERS] = '["privat","../geheim"]';
		$service = $this->service();

		$service->isExcluded(4, 'a.mp3');
		$service->isExcluded(4, 'b.mp3');
		$service->isExcludedUser('ana');

		self::assertCount(1, $this->logged);
		self::assertStringContainsString(ExclusionService::LIST_FOLDERS, $this->logged[0]);
		self::assertStringNotContainsString('privat', $this->logged[0]);
		self::assertStringNotContainsString('geheim', $this->logged[0]);
	}

	public function testAListStoredWithTheTypeArrayIsReadAndWrittenAgainAsText(): void {
		$this->stored[ExclusionService::LIST_USERS] = ['eva'];
		$service = $this->service();

		self::assertSame(['eva'], $service->entries(ExclusionService::LIST_USERS));
		self::assertTrue($service->isExcludedUser('eva'));

		self::assertSame(ExclusionService::RESULT_ADDED, $service->add(ExclusionService::LIST_USERS, 'ben'));
		self::assertSame([ExclusionService::LIST_USERS], $this->deleted);
		self::assertSame('["eva","ben"]', $this->stored[ExclusionService::LIST_USERS]);
		self::assertTrue($service->isExcludedUser('ben'));
	}

	public function testAMountCacheThatFailsExcludesTheStorage(): void {
		$this->store(ExclusionService::LIST_USERS, ['eva']);
		$this->mountCacheFails = true;
		$service = $this->service();

		self::assertTrue($service->isExcluded(4, 'a.mp3'));
		self::assertNull($service->storageOwner(4));
		self::assertNotSame([], $this->logged);
		foreach ($this->logged as $line) {
			self::assertStringNotContainsString('eva', $line);
		}
	}

	public function testAGroupBackendThatFailsExcludesTheUser(): void {
		$this->store(ExclusionService::LIST_GROUPS, ['extern']);
		$this->groupsFail = true;
		$service = $this->service();

		self::assertTrue($service->isExcludedUser('ana'));
		self::assertNotSame([], $this->logged);
		foreach ($this->logged as $line) {
			self::assertStringNotContainsString('extern', $line);
			self::assertStringNotContainsString('ana', $line);
		}
	}

	public function testAFileIsJudgedFromTheFileCacheAlone(): void {
		$this->store(ExclusionService::LIST_USERS, ['eva']);
		$this->store(ExclusionService::LIST_FOLDERS, ['privat']);
		$this->cacheEntries = [
			// The trash bin of a home lies outside its walk root: no folder
			// rule, but the rule about the user of the home.
			32 => [3, 'files_trashbin/files/a.mp3.d1'],
			44 => [4, 'files_trashbin/files/privat/a.mp3.d1'],
			45 => [4, 'files/a.mp3'],
		];
		$service = $this->service();

		self::assertTrue($service->isExcludedFile(32));
		self::assertFalse($service->isExcludedFile(44));
		self::assertFalse($service->isExcludedFile(45));
		// A file the cache does not know is not excluded: the caller answers it as missing.
		self::assertFalse($service->isExcludedFile(999));
	}

	public function testAFileCacheThatFailsExcludesTheFileAndLogsNoPath(): void {
		$this->fileCacheFails = true;
		$service = $this->service();

		self::assertTrue($service->isExcludedFile(45));
		self::assertCount(1, $this->logged);
		self::assertStringNotContainsString('privat', $this->logged[0]);
	}

	// -- the fingerprint --------------------------------------------------------

	public function testTheFingerprintIsTheSha256OverTheFourSortedLists(): void {
		$empty = $this->service()->fingerprint();
		self::assertSame(
			hash('sha256', "excluded_users\n\0excluded_groups\n\0excluded_folders\n\0excluded_mounts\n"),
			$empty,
		);

		$this->store(ExclusionService::LIST_USERS, ['eva', 'ben']);
		$this->store(ExclusionService::LIST_FOLDERS, ['privat']);
		$first = $this->service()->fingerprint();
		self::assertSame(
			hash('sha256', "excluded_users\nben\neva\0excluded_groups\n\0excluded_folders\nprivat\0excluded_mounts\n"),
			$first,
		);

		$this->store(ExclusionService::LIST_USERS, ['ben', 'eva']);
		self::assertSame($first, $this->service()->fingerprint());

		// The same word in another list is another rule set.
		$this->store(ExclusionService::LIST_FOLDERS, []);
		$this->store(ExclusionService::LIST_GROUPS, ['privat']);
		self::assertNotSame($first, $this->service()->fingerprint());
		self::assertNotSame($empty, $this->service()->fingerprint());
	}

	// -- writing ----------------------------------------------------------------

	public function testAddAndRemoveWriteTheWholeListAsJsonTextAndHoldAtOnce(): void {
		$service = $this->service();
		self::assertFalse($service->isExcludedUser('eva'));

		self::assertSame(ExclusionService::RESULT_ADDED, $service->add(ExclusionService::LIST_USERS, ' eva '));
		self::assertSame(ExclusionService::RESULT_ADDED, $service->add(ExclusionService::LIST_USERS, 'ben'));
		self::assertSame(ExclusionService::RESULT_ADDED, $service->add(ExclusionService::LIST_FOLDERS, '/Sitzungen/nicht öffentlich/'));
		self::assertSame('["eva","ben"]', $this->stored[ExclusionService::LIST_USERS]);
		self::assertSame('["Sitzungen/nicht öffentlich"]', $this->stored[ExclusionService::LIST_FOLDERS]);
		self::assertTrue($service->isExcludedUser('eva'));
		self::assertTrue($service->isExcluded(4, 'Sitzungen/nicht öffentlich/a.mp3'));

		self::assertSame(ExclusionService::RESULT_REMOVED, $service->remove(ExclusionService::LIST_USERS, 'EVA'));
		self::assertSame('["ben"]', $this->stored[ExclusionService::LIST_USERS]);
		self::assertFalse($service->isExcludedUser('eva'));
		self::assertTrue($service->isExcludedUser('ben'));

		$writes = count($this->writes);
		self::assertSame(ExclusionService::RESULT_ABSENT, $service->remove(ExclusionService::LIST_USERS, 'eva'));
		self::assertSame(ExclusionService::RESULT_ABSENT, $service->remove(ExclusionService::LIST_FOLDERS, '../x'));
		self::assertCount($writes, $this->writes);
	}

	public function testAMountIdHasToNameAConfigurationOfFilesExternalToBeAdded(): void {
		$this->configured = [3];
		$service = $this->service();

		self::assertSame(ExclusionService::RESULT_ADDED, $service->add(ExclusionService::LIST_MOUNTS, '3'));
		self::assertSame(ExclusionService::ERROR_UNKNOWN_MOUNT, $service->add(ExclusionService::LIST_MOUNTS, '4'));
		self::assertSame(ExclusionService::ERROR_INVALID, $service->add(ExclusionService::LIST_MOUNTS, 'drei'));
		self::assertSame(ExclusionService::ERROR_INVALID, $service->add(ExclusionService::LIST_MOUNTS, '0'));
		self::assertSame(ExclusionService::ERROR_INVALID, $service->add(ExclusionService::LIST_MOUNTS, '-3'));
		self::assertSame(ExclusionService::ERROR_INVALID, $service->add(ExclusionService::LIST_MOUNTS, '3 OR 1=1'));
		self::assertSame('["3"]', $this->stored[ExclusionService::LIST_MOUNTS]);
		self::assertSame([3, 4], $this->lookedUp);
	}

	public function testTheRuleOfADeletedConfigurationCanStillBeTakenBack(): void {
		$this->store(ExclusionService::LIST_MOUNTS, ['3']);
		$service = $this->service();

		self::assertSame(ExclusionService::RESULT_REMOVED, $service->remove(ExclusionService::LIST_MOUNTS, '3'));
		self::assertSame('[]', $this->stored[ExclusionService::LIST_MOUNTS]);
		self::assertSame([], $this->lookedUp);
	}

	public function testAConfigurationTableThatCannotBeReadKnowsNoMountId(): void {
		$db = $this->createMock(IDBConnection::class);
		$db->method('getQueryBuilder')->willThrowException(new \RuntimeException('no such table: oc_external_mounts'));
		$service = new ExclusionService(...$this->constructorArguments($db));

		self::assertSame(ExclusionService::ERROR_UNKNOWN_MOUNT, $service->add(ExclusionService::LIST_MOUNTS, '3'));
		self::assertSame([], $this->writes);
	}

	public function testANameThatIsNoListIsNeverReadOrWritten(): void {
		$service = $this->service();

		self::assertNull($service->entries('sample_visible'));
		self::assertSame([ExclusionService::ERROR_INVALID], $service->validate('sample_visible', ['x']));
		self::assertNull($service->normalise('sample_visible', 'x'));
		self::assertSame(ExclusionService::ERROR_UNREADABLE, $service->add('sample_visible', 'x'));
		self::assertSame([], $this->writes);
	}

	// -- occ audio_video_search:exclude -----------------------------------------

	/**
	 * @param list<string> $knownUsers
	 * @param list<string> $knownGroups
	 */
	private function command(ExclusionService $service, array $knownUsers = ['eva', 'ben'], array $knownGroups = ['extern']): ExcludeCommand {
		$users = $this->createMock(IUserManager::class);
		$users->method('userExists')->willReturnCallback(static fn (string $uid): bool => in_array($uid, $knownUsers, true));
		$groups = $this->createMock(IGroupManager::class);
		$groups->method('groupExists')->willReturnCallback(static fn (string $gid): bool => in_array($gid, $knownGroups, true));

		return new ExcludeCommand($service, $users, $groups);
	}

	/** @param array<string, mixed> $input */
	private static function runCommand(ExcludeCommand $command, array $input, BufferedOutput $output): int {
		return $command->run(new ArrayInput($input), $output);
	}

	public function testTheCommandIsRegisteredUnderItsNameWithItsSixOptions(): void {
		$command = $this->command($this->createMock(ExclusionService::class));

		self::assertSame('audio_video_search:exclude', $command->getName());
		foreach (['user', 'group', 'folder', 'storage', 'remove', 'list'] as $option) {
			self::assertTrue($command->getDefinition()->hasOption($option), $option);
		}
	}

	public function testAddingAUserWritesThroughTheServiceAndNeverRepeatsTheValue(): void {
		$service = $this->createMock(ExclusionService::class);
		$service->expects(self::once())->method('add')->with(ExclusionService::LIST_USERS, 'eva')->willReturn(ExclusionService::RESULT_ADDED);
		$service->expects(self::never())->method('remove');
		$output = new BufferedOutput();

		$code = self::runCommand($this->command($service), ['--user' => 'eva'], $output);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame("Added to the excluded users.\n", $output->fetch());
	}

	public function testEachOfTheFourOptionsWritesItsOwnList(): void {
		$calls = [];
		$service = $this->createMock(ExclusionService::class);
		$service->method('add')->willReturnCallback(function (string $list, string $entry) use (&$calls): string {
			$calls[] = [$list, $entry];

			return ExclusionService::RESULT_ADDED;
		});
		$output = new BufferedOutput();

		$code = self::runCommand(
			$this->command($service),
			['--user' => 'eva', '--group' => 'extern', '--folder' => 'privat', '--storage' => '3'],
			$output,
		);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame(
			[
				[ExclusionService::LIST_USERS, 'eva'],
				[ExclusionService::LIST_GROUPS, 'extern'],
				[ExclusionService::LIST_FOLDERS, 'privat'],
				[ExclusionService::LIST_MOUNTS, '3'],
			],
			$calls,
		);
		self::assertSame(
			"Added to the excluded users.\nAdded to the excluded groups.\nAdded to the excluded folders.\nAdded to the excluded external storages (mount ids).\n",
			$output->fetch(),
		);
	}

	public function testAUserOrAGroupNobodyKnowsIsExcludedWithANote(): void {
		$service = $this->createMock(ExclusionService::class);
		$service->method('add')->willReturn(ExclusionService::RESULT_ADDED);
		$output = new BufferedOutput();

		$code = self::runCommand($this->command($service), ['--user' => 'evaa', '--group' => 'extren'], $output);

		self::assertSame(Command::SUCCESS, $code);
		$printed = $output->fetch();
		self::assertStringContainsString('Note: no user with this id is known yet.', $printed);
		self::assertStringContainsString('Note: no group with this id is known yet.', $printed);
		self::assertStringNotContainsString('evaa', $printed);
		self::assertStringNotContainsString('extren', $printed);
	}

	public function testRemoveTakesTheEntryOutInsteadOfAddingIt(): void {
		$service = $this->createMock(ExclusionService::class);
		$service->expects(self::once())->method('remove')->with(ExclusionService::LIST_FOLDERS, 'privat')->willReturn(ExclusionService::RESULT_REMOVED);
		$service->expects(self::never())->method('add');
		$output = new BufferedOutput();

		$code = self::runCommand($this->command($service), ['--folder' => 'privat', '--remove' => true], $output);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame("Removed from the excluded folders.\n", $output->fetch());
	}

	/** @return array<string, array{string, string, string, int}> option, result of the service, sentence, exit code */
	public static function answers(): array {
		return [
			'already there' => ['user', ExclusionService::ERROR_DUPLICATE, 'Already in the excluded users, nothing changed.', Command::SUCCESS],
			'not there' => ['group', ExclusionService::RESULT_ABSENT, 'Not in the excluded groups, nothing changed.', Command::SUCCESS],
			'empty' => ['user', ExclusionService::ERROR_EMPTY, '--user needs a value.', Command::INVALID],
			'too long' => ['folder', ExclusionService::ERROR_TOO_LONG, '--folder takes at most 256 bytes.', Command::INVALID],
			'traversal' => ['folder', ExclusionService::ERROR_TRAVERSAL, 'A folder may not hold "." or ".." as a part of its path.', Command::INVALID],
			'unusable characters' => ['group', ExclusionService::ERROR_INVALID, '--group holds characters that cannot be used.', Command::INVALID],
			'no mount id' => ['storage', ExclusionService::ERROR_INVALID, '--storage takes the mount id of an external storage configuration, a positive whole number.', Command::INVALID],
			'unknown mount id' => ['storage', ExclusionService::ERROR_UNKNOWN_MOUNT, 'No external storage configuration has this mount id.', Command::FAILURE],
			'full' => ['user', ExclusionService::ERROR_TOO_MANY, 'The excluded users are full (64 entries).', Command::FAILURE],
			'unreadable' => [
				'folder',
				ExclusionService::ERROR_UNREADABLE,
				'The stored list cannot be read, so everything is excluded until it is repaired. Correct or delete the app config key excluded_folders.',
				Command::FAILURE,
			],
		];
	}

	#[DataProvider('answers')]
	public function testEveryResultOfTheServiceHasItsSentenceAndItsExitCode(string $option, string $result, string $sentence, int $expected): void {
		$service = $this->createMock(ExclusionService::class);
		$service->method('add')->willReturn($result);
		$output = new BufferedOutput();

		$code = self::runCommand($this->command($service), ['--' . $option => 'Wert-17'], $output);

		self::assertSame($expected, $code);
		$printed = $output->fetch();
		self::assertSame($sentence . "\n", $printed);
		self::assertStringNotContainsString('Wert-17', $printed);
	}

	/** @return array<string, array{array<string, mixed>}> */
	public static function unusableCalls(): array {
		return [
			'nothing' => [[]],
			'remove alone' => [['--remove' => true]],
			'remove with list' => [['--remove' => true, '--list' => true]],
		];
	}

	/** @param array<string, mixed> $input */
	#[DataProvider('unusableCalls')]
	public function testACallWithoutAnythingToDoIsInvalidAndTouchesNothing(array $input): void {
		$service = $this->createMock(ExclusionService::class);
		$service->expects(self::never())->method('add');
		$service->expects(self::never())->method('remove');
		$service->expects(self::never())->method('entries');
		$output = new BufferedOutput();

		$code = self::runCommand($this->command($service), $input, $output);

		self::assertSame(Command::INVALID, $code);
		self::assertSame("Give --user, --group, --folder or --storage, or --list.\n", $output->fetch());
	}

	public function testListPrintsTheRulesInForceOneEntryPerLine(): void {
		$this->store(ExclusionService::LIST_USERS, ['eva']);
		$this->store(ExclusionService::LIST_GROUPS, ['extern']);
		$this->store(ExclusionService::LIST_FOLDERS, ['privat', 'Archiv/<alt>']);
		$output = new BufferedOutput();

		$code = self::runCommand($this->command($this->service()), ['--list' => true], $output);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame(
			"Excluded users (1):\n  eva\n"
			. "Excluded groups (1):\n  extern\n"
			. "Excluded folders (2):\n  privat\n  Archiv/<alt>\n"
			. "Excluded external storages (mount ids) (0):\n",
			$output->fetch(),
		);
		self::assertSame([], $this->writes);
	}

	public function testListAfterAChangeShowsTheNewRule(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->command($this->service()), ['--user' => 'eva', '--list' => true], $output);

		self::assertSame(Command::SUCCESS, $code);
		self::assertStringStartsWith("Added to the excluded users.\nExcluded users (1):\n  eva\n", $output->fetch());
	}

	public function testListNamesAListThatCannotBeReadAndFails(): void {
		$this->stored[ExclusionService::LIST_GROUPS] = 'extern';
		$output = new BufferedOutput();

		$code = self::runCommand($this->command($this->service()), ['--list' => true], $output);

		self::assertSame(Command::FAILURE, $code);
		$printed = $output->fetch();
		self::assertStringContainsString(
			'Excluded groups: The stored list cannot be read, so everything is excluded until it is repaired. Correct or delete the app config key excluded_groups.',
			$printed,
		);
		self::assertStringContainsString("Excluded users (0):\n", $printed);
	}
}
