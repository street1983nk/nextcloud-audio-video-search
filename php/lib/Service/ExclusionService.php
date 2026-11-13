<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\Exceptions\AppConfigTypeConflictException;
use OCP\Files\Cache\IFileAccess;
use OCP\Files\Config\IUserMountCache;
use OCP\IAppConfig;
use OCP\IDBConnection;
use OCP\IGroupManager;
use Psr\Log\LoggerInterface;

/**
 * The exclusions: four lists and the one place that compares against them.
 *
 * users    a user: the storages that belong to them are not captured (their
 *          home, an external storage only they have, the storage files_external
 *          builds for them from a configuration of the admin with their own
 *          login, D-02-11), and they get no hits. What others share with them
 *          and the copies other users have of the same share stay (D-02-08).
 * groups   the same for every member of a group.
 * folders  a prefix relative to the root of the mount a file lies on (after
 *          Findling): "privat" leaves out the folder privat of every home and
 *          of every other mount, and not "privatsache". No pattern language.
 * mounts   a mount configuration of files_external, by its mount id: the
 *          switch of the admin for external storages (DISC-02).
 *
 * The lists live in the app config as JSON lists, so they can be set before
 * the backend is installed (D-02-05); occ audio_video_search:exclude writes
 * them through this class, occ config:app:set is the second writer.
 *
 * Privacy first, so every doubt excludes. Lists that cannot be read in full
 * (no JSON list, an entry that is no usable rule, more entries than the
 * ceiling) exclude everything until they are repaired: a rule nobody can read
 * must not turn into "nothing is excluded". A mount cache or a group backend
 * that fails while a rule needs it excludes the storage or the user asked for.
 *
 * QueueService::admissible (queueing and hand over), the content gateway and
 * the search provider all ask here and nowhere else (gate rule 14 in
 * backend/tests/test_php_gates.py). Nothing this class logs names a user, a
 * group, a prefix or a path: list names, codes and classes only (T-02-60).
 */
class ExclusionService {
	public const LIST_USERS = 'excluded_users';
	public const LIST_GROUPS = 'excluded_groups';
	public const LIST_FOLDERS = 'excluded_folders';
	public const LIST_MOUNTS = 'excluded_mounts';

	/** The four lists, in the order of the fingerprint. */
	public const LISTS = [self::LIST_USERS, self::LIST_GROUPS, self::LIST_FOLDERS, self::LIST_MOUNTS];

	/**
	 * How many entries one list may hold and how many bytes one entry may
	 * have (Findling: 64 x 256). Every event of the instance runs through the
	 * comparison, so both numbers are a cost.
	 */
	public const MAX_ENTRIES = 64;
	public const MAX_ENTRY_LENGTH = 256;

	public const RESULT_ADDED = 'added';
	public const RESULT_REMOVED = 'removed';
	public const RESULT_ABSENT = 'absent';

	public const ERROR_EMPTY = 'empty';
	public const ERROR_TOO_LONG = 'too_long';
	public const ERROR_TRAVERSAL = 'traversal';
	public const ERROR_DUPLICATE = 'duplicate';
	public const ERROR_TOO_MANY = 'too_many';
	public const ERROR_INVALID = 'invalid';
	public const ERROR_UNKNOWN_MOUNT = 'unknown_mount';
	/** The mount configurations of files_external cannot be read, so a mount id cannot be looked up. */
	public const ERROR_MOUNTS_UNREADABLE = 'mounts_unreadable';
	public const ERROR_UNREADABLE = 'unreadable';

	/** What the fingerprint is taken over while the lists cannot be read. */
	private const UNREADABLE_MARK = "\0unreadable";

	/** A mount id as occ and the app config hand it over. */
	private const MOUNT_ID = '/^[1-9][0-9]{0,17}$/';

	/** The folder of a home between its storage root and the files of the user. */
	private const HOME_FILES_PREFIX = 'files/';

	/**
	 * The rules in force, read once per instance of this service: null not
	 * read yet, false not readable.
	 *
	 * @var array{lists: array<string, list<string>>, users: array<string, true>, mounts: array<int, true>}|false|null
	 */
	private array|false|null $rules = null;

	/** @var array<int, bool> the verdict on a storage, by storage id */
	private array $storageVerdicts = [];

	/** @var array<string, bool> the verdict on a user, by user id */
	private array $userVerdicts = [];

	public function __construct(
		private IAppConfig $appConfig,
		private IUserMountCache $userMountCache,
		private IGroupManager $groupManager,
		private IFileAccess $fileAccess,
		private StorageService $storageService,
		private IDBConnection $db,
		private LoggerInterface $logger,
	) {
	}

	/**
	 * Is a file of this storage, at this path below the root of its mount,
	 * left out? THE comparison: a folder prefix that covers the path, a
	 * switched off mount configuration of the storage, or an owner of the
	 * storage who is excluded. An empty path asks about the storage alone.
	 */
	public function isExcluded(int $storageId, string $mountRelativePath): bool {
		$rules = $this->rules();
		if ($rules === false) {
			return true;
		}
		if (self::coveredByAPrefix($rules['lists'][self::LIST_FOLDERS], $mountRelativePath)) {
			return true;
		}

		return $this->isExcludedStorage($storageId, $rules);
	}

	/**
	 * The same question for a file id, from the file cache alone: no user is
	 * set up and no storage is touched, so the content gateway can refuse an
	 * excluded file without opening it and without contacting its storage.
	 * A file the cache does not know is not excluded; the caller answers it
	 * as a file that is not there. A cache that cannot be asked excludes.
	 */
	public function isExcludedFile(int $fileId): bool {
		try {
			$entry = $this->fileAccess->getByFileId($fileId);
			if ($entry === null) {
				return false;
			}
			$storageId = (int)$entry->getStorageId();
			$relative = $this->storageService->mountRelativePath($storageId, (string)$entry->getPath());
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: a file could not be checked against the exclusions, treated as excluded', [
				'fileId' => $fileId,
				'class' => $e::class,
			]);

			return true;
		}

		// Outside every walk root (trash bin, versions) no folder rule applies,
		// the rules about the storage still do.
		return $this->isExcluded($storageId, $relative ?? '');
	}

	/**
	 * Is this user excluded, by name or as a member of an excluded group?
	 * The user id is compared without regard to case, as Nextcloud does.
	 */
	public function isExcludedUser(string $uid): bool {
		$rules = $this->rules();
		if ($rules === false) {
			return true;
		}
		if ($uid === '') {
			return false;
		}
		if (isset($rules['users'][mb_strtolower($uid)])) {
			return true;
		}
		$groups = $rules['lists'][self::LIST_GROUPS];
		if ($groups === []) {
			return false;
		}
		if (isset($this->userVerdicts[$uid])) {
			return $this->userVerdicts[$uid];
		}

		$excluded = false;
		try {
			foreach ($groups as $gid) {
				if ($this->groupManager->isInGroup($uid, $gid)) {
					$excluded = true;
					break;
				}
			}
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the groups of a user could not be read, the user is treated as excluded', ['class' => $e::class]);
			$excluded = true;
		}
		$this->userVerdicts[$uid] = $excluded;

		return $excluded;
	}

	/**
	 * The user a storage belongs to, or null when it belongs to nobody alone.
	 *
	 * A home belongs to its user, whoever else has a share of it. An external
	 * storage belongs to a user when files_external built it for this user
	 * alone, which is also the case for a configuration of the admin that logs
	 * in with the credentials of each user (D-02-11): every user then has a
	 * storage of their own on the same share. An external storage several
	 * users have and a team folder belong to nobody. null as well when the
	 * mount cache cannot be read.
	 */
	public function storageOwner(int $storageId): ?string {
		try {
			return $this->storageFacts($storageId)['owner'];
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the mounts of a storage could not be read', ['storage_id' => $storageId, 'class' => $e::class]);

			return null;
		}
	}

	/**
	 * sha256 over the four lists as they are in force, each sorted, so plan
	 * 02-18 can tell whether the rules changed since it last applied them.
	 * The order an admin typed the entries in is no change. Lists that cannot
	 * be read have a fingerprint of their own.
	 */
	public function fingerprint(): string {
		$rules = $this->rules();
		if ($rules === false) {
			return hash('sha256', self::UNREADABLE_MARK);
		}

		$parts = [];
		foreach (self::LISTS as $list) {
			$entries = $rules['lists'][$list];
			sort($entries, SORT_STRING);
			// No entry holds a control character, so line feed and zero byte
			// cannot make two different rule sets join to the same text.
			$parts[] = $list . "\n" . implode("\n", $entries);
		}

		return hash('sha256', implode("\0", $parts));
	}

	/**
	 * The entries of one list as they are in force, or null when the stored
	 * value cannot be read as a list of usable rules.
	 *
	 * @return list<string>|null
	 */
	public function entries(string $list): ?array {
		if (!in_array($list, self::LISTS, true)) {
			return null;
		}
		$stored = $this->stored($list);
		if ($stored === null) {
			return null;
		}
		[$entries, $errors] = $this->judged($list, $stored);
		// The same entry twice is one rule; anything else unusable is a rule
		// nobody can read.
		if (array_diff($errors, [self::ERROR_DUPLICATE]) !== []) {
			return null;
		}

		return $entries;
	}

	/**
	 * Judge a whole list without writing anything: the error codes, empty
	 * when the list fits. Codes and never a value somebody typed.
	 *
	 * @param list<mixed> $entries
	 * @return list<string>
	 */
	public function validate(string $list, array $entries): array {
		if (!in_array($list, self::LISTS, true)) {
			return [self::ERROR_INVALID];
		}

		return $this->judged($list, $entries)[1];
	}

	/** One entry as it is stored and compared, or null when it is no usable rule. */
	public function normalise(string $list, string $entry): ?string {
		return $this->normalised($list, $entry)[0];
	}

	/**
	 * Add one entry to a list: RESULT_ADDED, or the code that refused it.
	 * Nothing is written unless the answer is RESULT_ADDED. A mount id has to
	 * name a mount configuration of files_external; when those cannot be read
	 * (the app is not enabled, its table is missing) the answer says so and
	 * is not "no such mount id".
	 */
	public function add(string $list, string $entry): string {
		$current = $this->entries($list);
		if ($current === null) {
			return self::ERROR_UNREADABLE;
		}
		[$value, $error] = $this->normalised($list, $entry);
		if ($value === null) {
			return $error ?? self::ERROR_INVALID;
		}
		if (self::position($list, $current, $value) !== null) {
			return self::ERROR_DUPLICATE;
		}
		if (count($current) >= self::MAX_ENTRIES) {
			return self::ERROR_TOO_MANY;
		}
		if ($list === self::LIST_MOUNTS) {
			$configured = $this->mountConfigured((int)$value);
			if ($configured === null) {
				return self::ERROR_MOUNTS_UNREADABLE;
			}
			if (!$configured) {
				return self::ERROR_UNKNOWN_MOUNT;
			}
		}

		$current[] = $value;
		$this->write($list, $current);

		return self::RESULT_ADDED;
	}

	/**
	 * Take one entry out of a list: RESULT_REMOVED, RESULT_ABSENT, or
	 * ERROR_UNREADABLE. A mount id is not looked up here, so the rule of a
	 * configuration that was deleted can still be taken back.
	 */
	public function remove(string $list, string $entry): string {
		$current = $this->entries($list);
		if ($current === null) {
			return self::ERROR_UNREADABLE;
		}
		$value = $this->normalised($list, $entry)[0];
		$position = $value === null ? null : self::position($list, $current, $value);
		if ($position === null) {
			return self::RESULT_ABSENT;
		}

		unset($current[$position]);
		$this->write($list, array_values($current));

		return self::RESULT_REMOVED;
	}

	/**
	 * Does files_external know a mount configuration with this id? null when
	 * its table cannot be read: that is not the same as an id nobody
	 * configured, and the admin is told which of the two it was. Protected
	 * only so the unit test can replace the query.
	 */
	protected function mountConfigured(int $mountId): ?bool {
		try {
			$qb = $this->db->getQueryBuilder();
			$qb->select('mount_id')
				->from('external_mounts')
				->where($qb->expr()->eq('mount_id', $qb->createNamedParameter($mountId, IQueryBuilder::PARAM_INT)));
			$result = $qb->executeQuery();
			$row = $result->fetch();
			$result->closeCursor();

			return $row !== false;
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the external storage configuration could not be read', ['class' => $e::class]);

			return null;
		}
	}

	/**
	 * @param array{lists: array<string, list<string>>, users: array<string, true>, mounts: array<int, true>} $rules
	 */
	private function isExcludedStorage(int $storageId, array $rules): bool {
		if ($rules['users'] === [] && $rules['lists'][self::LIST_GROUPS] === [] && $rules['mounts'] === []) {
			// No rule about a storage: no question to the mount cache.
			return false;
		}
		if (isset($this->storageVerdicts[$storageId])) {
			return $this->storageVerdicts[$storageId];
		}

		try {
			$facts = $this->storageFacts($storageId);
			$excluded = false;
			foreach ($facts['mountIds'] as $mountId) {
				// One switched off configuration is enough, also when another
				// one reaches the same storage.
				if (isset($rules['mounts'][$mountId])) {
					$excluded = true;
					break;
				}
			}
			if (!$excluded && $facts['owner'] !== null) {
				$excluded = $this->isExcludedUser($facts['owner']);
			}
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the mounts of a storage could not be read, the storage is treated as excluded', [
				'storage_id' => $storageId,
				'class' => $e::class,
			]);
			$excluded = true;
		}
		$this->storageVerdicts[$storageId] = $excluded;

		return $excluded;
	}

	/**
	 * Whom a storage belongs to and which mount configurations of
	 * files_external reach it, from the mount cache. Mounts of other
	 * providers (a share of a file of this storage, for example) say nothing
	 * about either.
	 *
	 * @return array{owner: ?string, mountIds: list<int>}
	 */
	private function storageFacts(int $storageId): array {
		$home = null;
		$externalUsers = [];
		$mountIds = [];
		foreach ($this->userMountCache->getMountsForStorageId($storageId) as $mount) {
			$provider = $mount->getMountProvider();
			$uid = $mount->getUser()->getUID();
			if (in_array($provider, StorageService::HOME_MOUNT_PROVIDERS, true)) {
				if ($uid !== '') {
					$home ??= $uid;
				}
				continue;
			}
			if ($provider !== StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER) {
				continue;
			}
			if ($uid !== '') {
				$externalUsers[$uid] = true;
			}
			$mountId = $mount->getMountId();
			if ($mountId !== null) {
				$mountIds[$mountId] = true;
			}
		}

		$owner = $home;
		if ($owner === null && count($externalUsers) === 1) {
			$owner = (string)array_key_first($externalUsers);
		}

		return ['owner' => $owner, 'mountIds' => array_keys($mountIds)];
	}

	/**
	 * Does one of the prefixes cover this path: the folder itself or anything
	 * inside it, never a name that only begins the same way. A prefix an admin
	 * wrote with the files folder of a home in front ("files/privat") also
	 * counts without it, because the path of a file in a home is relative to
	 * that folder; counting both leaves out more, never less.
	 *
	 * @param list<string> $prefixes
	 */
	private static function coveredByAPrefix(array $prefixes, string $mountRelativePath): bool {
		if ($prefixes === []) {
			return false;
		}
		$path = self::composed(self::trimmed($mountRelativePath));
		if ($path === '') {
			return false;
		}

		foreach ($prefixes as $prefix) {
			if ($path === $prefix || str_starts_with($path, $prefix . '/')) {
				return true;
			}
			if (!str_starts_with($prefix, self::HOME_FILES_PREFIX)) {
				continue;
			}
			$short = substr($prefix, strlen(self::HOME_FILES_PREFIX));
			if ($path === $short || str_starts_with($path, $short . '/')) {
				return true;
			}
		}

		return false;
	}

	/**
	 * @return array{lists: array<string, list<string>>, users: array<string, true>, mounts: array<int, true>}|false
	 */
	private function rules(): array|false {
		if ($this->rules !== null) {
			return $this->rules;
		}

		$lists = [];
		foreach (self::LISTS as $list) {
			$entries = $this->entries($list);
			if ($entries === null) {
				// The name of the list and nothing of what stands in it.
				$this->logger->warning('Audio & Video Search: stored exclusions cannot be read, so everything is excluded until they are repaired', ['list' => $list]);
				$this->rules = false;

				return false;
			}
			$lists[$list] = $entries;
		}

		$users = [];
		foreach ($lists[self::LIST_USERS] as $uid) {
			$users[mb_strtolower($uid)] = true;
		}
		$mounts = [];
		foreach ($lists[self::LIST_MOUNTS] as $mountId) {
			$mounts[(int)$mountId] = true;
		}
		$this->rules = ['lists' => $lists, 'users' => $users, 'mounts' => $mounts];

		return $this->rules;
	}

	/**
	 * The stored value of one list as PHP values, or null when it is no JSON
	 * list. Read as text, because occ config:app:set stores text and
	 * getValueArray answers an empty list for text that is no JSON, which
	 * would read a broken rule as no rule. A value stored with the type array
	 * is read as that.
	 *
	 * @return list<mixed>|null
	 */
	private function stored(string $list): ?array {
		try {
			$raw = $this->appConfig->getValueString(Application::APP_ID, $list, '');
		} catch (AppConfigTypeConflictException) {
			try {
				$typed = $this->appConfig->getValueArray(Application::APP_ID, $list, []);
			} catch (\Throwable) {
				return null;
			}

			return array_is_list($typed) ? $typed : null;
		} catch (\Throwable) {
			return null;
		}

		if (trim($raw) === '') {
			return [];
		}
		try {
			$decoded = json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
		} catch (\JsonException) {
			return null;
		}

		return is_array($decoded) && array_is_list($decoded) ? $decoded : null;
	}

	/** @param list<string> $entries */
	private function write(string $list, array $entries): void {
		$json = json_encode($entries, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
		try {
			$this->appConfig->setValueString(Application::APP_ID, $list, $json);
		} catch (AppConfigTypeConflictException) {
			// Stored with another type by occ config:app:set: the key is
			// written again as text.
			$this->appConfig->deleteKey(Application::APP_ID, $list);
			$this->appConfig->setValueString(Application::APP_ID, $list, $json);
		}

		$this->rules = null;
		$this->storageVerdicts = [];
		$this->userVerdicts = [];
	}

	/**
	 * The usable entries of a list, each once, and the codes of what was
	 * refused.
	 *
	 * @param list<mixed> $entries
	 * @return array{0: list<string>, 1: list<string>}
	 */
	private function judged(string $list, array $entries): array {
		$errors = [];
		if (count($entries) > self::MAX_ENTRIES) {
			$errors[] = self::ERROR_TOO_MANY;
		}

		$kept = [];
		foreach ($entries as $entry) {
			if (is_int($entry)) {
				// A numeric user id or a mount id written without quotes.
				$entry = (string)$entry;
			}
			if (!is_string($entry)) {
				$errors[] = self::ERROR_INVALID;
				continue;
			}
			[$value, $error] = $this->normalised($list, $entry);
			if ($value === null) {
				$errors[] = $error ?? self::ERROR_INVALID;
				continue;
			}
			if (self::position($list, $kept, $value) !== null) {
				$errors[] = self::ERROR_DUPLICATE;
				continue;
			}
			$kept[] = $value;
		}

		return [$kept, array_values(array_unique($errors))];
	}

	/**
	 * Where a normalised entry stands in a list, or null. User ids are
	 * compared without regard to case.
	 *
	 * @param array<int, string> $entries
	 */
	private static function position(string $list, array $entries, string $value): ?int {
		$wanted = $list === self::LIST_USERS ? mb_strtolower($value) : $value;
		foreach ($entries as $index => $entry) {
			if (($list === self::LIST_USERS ? mb_strtolower($entry) : $entry) === $wanted) {
				return $index;
			}
		}

		return null;
	}

	/**
	 * One entry as it is stored and compared, or the code that refuses it.
	 *
	 * A folder prefix: repeated slashes collapsed, the outer ones dropped,
	 * composed to NFC like the names in the file cache. A segment "." or ".."
	 * is refused and not filtered: filtering "Archiv/../.." down to "Archiv"
	 * would leave out something the admin did not name (T-02-59). The value
	 * only ever reaches str_starts_with, never a file system call.
	 *
	 * Ordinary spaces at the edges are dropped, in every list, and nothing
	 * else is: trim() without a second argument would also drop a zero byte, a
	 * tab, a line feed and a carriage return there, and the entry would be
	 * stored as a rule nobody typed. An entry that holds a control character
	 * anywhere, the edges included, is refused instead of altered (plan
	 * 02-16b), so encoding and control characters are judged on the entry as
	 * it came, not on the shortened value.
	 *
	 * @return array{0: ?string, 1: ?string}
	 */
	private function normalised(string $list, string $entry): array {
		$value = trim($entry, ' ');
		if ($value === '') {
			return [null, self::ERROR_EMPTY];
		}
		if (strlen($value) > self::MAX_ENTRY_LENGTH) {
			return [null, self::ERROR_TOO_LONG];
		}
		if (!mb_check_encoding($entry, 'UTF-8') || preg_match('/[\x00-\x1F\x7F]/', $entry) === 1) {
			return [null, self::ERROR_INVALID];
		}

		if ($list === self::LIST_USERS || $list === self::LIST_GROUPS) {
			return [$value, null];
		}
		if ($list === self::LIST_MOUNTS) {
			return preg_match(self::MOUNT_ID, $value) === 1 ? [$value, null] : [null, self::ERROR_INVALID];
		}
		if ($list !== self::LIST_FOLDERS) {
			return [null, self::ERROR_INVALID];
		}

		$value = self::composed(self::trimmed($value));
		if ($value === '') {
			return [null, self::ERROR_EMPTY];
		}
		foreach (explode('/', $value) as $segment) {
			if ($segment === '..' || $segment === '.') {
				return [null, self::ERROR_TRAVERSAL];
			}
		}

		return [$value, null];
	}

	/**
	 * One path with repeated slashes collapsed and the outer ones gone. A
	 * backslash is a legal character of a file name and stays.
	 */
	private static function trimmed(string $path): string {
		$collapsed = preg_replace('#/+#', '/', $path);

		return trim($collapsed ?? $path, '/');
	}

	/** The value in Unicode normalisation form C, or as it came without intl. */
	private static function composed(string $value): string {
		if (!class_exists(\Normalizer::class)) {
			return $value;
		}
		$composed = \Normalizer::normalize($value, \Normalizer::FORM_C);

		return is_string($composed) ? $composed : $value;
	}
}
