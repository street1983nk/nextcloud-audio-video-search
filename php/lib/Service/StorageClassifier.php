<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCA\AudioVideoSearch\Db\StorageStateMapper;
use OCP\App\IAppManager;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\Files\Config\ICachedMountInfo;
use OCP\Files\Config\IUserMountCache;
use OCP\Files\Mount\IMountManager;
use OCP\Files\Storage\IStorage;
use OCP\IDBConnection;
use OCP\Security\ICredentialsManager;
use Psr\Log\LoggerInterface;

/**
 * Can an external storage be captured in the background? Decided before a
 * single file is queued, from the configuration, never from a failed
 * download (D-02-03, 02-RESEARCH.md Befund 3).
 *
 * In the background files_external builds every configuration per user; an
 * authentication that needs the web session throws there and leaves a
 * FailedStorage, while the cache rows of an earlier web session stay in
 * oc_filecache. Crawling them would end in one failed download per file.
 *
 * The order of the checks:
 * 1. files_external enabled and its configuration readable, else unavailable;
 * 2. the authentication of the configuration: session and Apache Kerberos are
 *    never capturable (NEVER), without a call to the credentials store and
 *    without a setup of the storage;
 * 3. stored credentials where the authentication needs them, else
 *    credentials_missing;
 * 4. a probe of the storage as one of its users: mount set up from the
 *    mount cache, the same numeric storage, no FailedStorage, available.
 *    Wrong passwords, a server that is down and Kerberos without a ticket end
 *    here as unavailable, once per storage and not once per file.
 *
 * The share key is cut here, from the full id of the probed storage object,
 * and stored as its sha256 only (T-02-40). Nothing this class logs or returns
 * names a path, a host, a share or a mount point (T-02-44).
 */
class StorageClassifier {
	/** Authentications that never work without the web session of the user. */
	public const NEVER = ['password::sessioncredentials', 'smb::kerberosapache'];

	public const REASON_SESSION_CREDENTIALS = 'session_credentials';
	public const REASON_CREDENTIALS_MISSING = 'credentials_missing';
	public const REASON_UNAVAILABLE = 'unavailable';
	/** Set by the admin switch of plan 02-16, never by this class. */
	public const REASON_SWITCHED_OFF = 'switched_off';

	/** The closed list of reasons in avs_storage.reason. */
	public const REASONS = [
		self::REASON_SESSION_CREDENTIALS,
		self::REASON_CREDENTIALS_MISSING,
		self::REASON_UNAVAILABLE,
		self::REASON_SWITCHED_OFF,
	];

	/** A classified storage is checked again after this many seconds. */
	public const RECHECK_SECONDS = 86400;

	/** The sentence occ audio_video_search:status prints below skipped storages. */
	public const HINT = 'Stored credentials (Log-in credentials, save in database) make these storages capturable.';

	/** files_external writes this for a configuration of the admin (StorageConfig::MOUNT_TYPE_ADMIN). */
	private const MOUNT_TYPE_ADMIN = 1;

	private const FAILED_STORAGE = 'OC\Files\Storage\FailedStorage';

	/** What an identifier of files_external may look like before it is printed. */
	private const IDENTIFIER = '/^[A-Za-z0-9_:.\\\\-]{1,64}$/';

	public function __construct(
		private IUserMountCache $userMountCache,
		private IMountManager $mountManager,
		private IAppManager $appManager,
		private ICredentialsManager $credentials,
		private IDBConnection $db,
		private StorageStateMapper $storageStates,
		private ReaderContext $readerContext,
		private ITimeFactory $timeFactory,
		private LoggerInterface $logger,
	) {
	}

	/**
	 * The classification of one external storage, not written.
	 *
	 * @return array{storageId: int, mountId: ?int, provider: string, shareKeyHash: ?string, rootPrefix: ?string, authKind: ?string, capturable: bool, reason: ?string, users: int, checkedAt: ?int}
	 */
	public function classify(int $storageId): array {
		$state = [
			'storageId' => $storageId,
			'mountId' => null,
			'provider' => StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER,
			'shareKeyHash' => null,
			'rootPrefix' => null,
			'authKind' => null,
			'capturable' => false,
			'reason' => self::REASON_UNAVAILABLE,
			'users' => 0,
			'checkedAt' => $this->timeFactory->getTime(),
		];

		/** @var array<int, list<ICachedMountInfo>> $byMount mount id => mounts of it, one per user */
		$byMount = [];
		$uids = [];
		foreach ($this->userMountCache->getMountsForStorageId($storageId) as $info) {
			if ($info->getMountProvider() !== StorageService::EXTERNAL_STORAGE_MOUNT_PROVIDER) {
				continue;
			}
			$uid = $info->getUser()->getUID();
			$mountId = $info->getMountId();
			if ($uid === '' || $mountId === null) {
				continue;
			}
			$uids[$uid] = true;
			$byMount[$mountId][] = $info;
		}
		$state['users'] = count($uids);
		if ($byMount === []) {
			return $state;
		}
		ksort($byMount);

		$configs = $this->mountConfigs(array_keys($byMount));
		if ($configs === null) {
			return $state;
		}
		$mountId = $this->chosenMount(array_keys($byMount), $configs);
		if ($mountId === null) {
			return $state;
		}
		$auth = $configs[$mountId]['auth'];
		$state['mountId'] = $mountId;
		$state['authKind'] = $auth;
		if (in_array($auth, self::NEVER, true)) {
			$state['reason'] = self::REASON_SESSION_CREDENTIALS;
			return $state;
		}

		$reader = null;
		$mounts = $byMount[$mountId];
		usort($mounts, static fn (ICachedMountInfo $a, ICachedMountInfo $b): int => strcmp($a->getUser()->getUID(), $b->getUser()->getUID()));
		foreach ($mounts as $info) {
			$present = $this->credentialsPresent($auth, $info->getUser()->getUID(), $mountId, $configs[$mountId]['type'] === self::MOUNT_TYPE_ADMIN);
			if ($present === null) {
				// The credentials store could not be read.
				return $state;
			}
			if ($present) {
				$reader = $info;
				break;
			}
		}
		if ($reader === null) {
			$state['reason'] = self::REASON_CREDENTIALS_MISSING;
			return $state;
		}

		$storage = $this->probe($reader, $storageId);
		if ($storage === null) {
			return $state;
		}

		$shareKey = StorageService::shareKey((string)$storage->getId());
		$state['capturable'] = true;
		$state['reason'] = null;
		if ($shareKey !== null) {
			$state['shareKeyHash'] = StorageService::shareKeyHash($shareKey[0]);
			$state['rootPrefix'] = $shareKey[1];
		}

		return $state;
	}

	/**
	 * Classify a storage again when it is due and write the result.
	 * $mayCheck false (the time budget of the run is spent) only reads.
	 *
	 * @return array{capturable: bool, becameCapturable: bool, checked: bool}
	 */
	public function refresh(int $storageId, bool $mayCheck = true): array {
		$before = $this->storageStates->find($storageId);
		if (!$mayCheck || !$this->isDue($before)) {
			return ['capturable' => $before !== null && $before['capturable'], 'becameCapturable' => false, 'checked' => false];
		}

		$state = $this->classify($storageId);
		$this->storageStates->store($state);

		return [
			'capturable' => $state['capturable'],
			'becameCapturable' => $state['capturable'] && ($before === null || !$before['capturable']),
			'checked' => true,
		];
	}

	/**
	 * Due: never classified, older than RECHECK_SECONDS, or skipped for want
	 * of credentials. The last two checks are cheap (no remote access unless
	 * credentials appeared), so they run every time: a user who logs in with
	 * "save in database" is picked up by the next run.
	 *
	 * @param array{storageId: int, mountId: ?int, provider: string, shareKeyHash: ?string, rootPrefix: ?string, authKind: ?string, capturable: bool, reason: ?string, users: int, checkedAt: ?int}|null $state
	 */
	public function isDue(?array $state): bool {
		if ($state === null || $state['checkedAt'] === null) {
			return true;
		}
		if (!$state['capturable'] && in_array($state['reason'], [self::REASON_SESSION_CREDENTIALS, self::REASON_CREDENTIALS_MISSING], true)) {
			return true;
		}

		return $this->timeFactory->getTime() - $state['checkedAt'] >= self::RECHECK_SECONDS;
	}

	/**
	 * The skipped storages for occ audio_video_search:status, one entry per
	 * mount configuration, reason and authentication: the classified storages
	 * that are not capturable, plus every configuration whose authentication
	 * is in NEVER. The second part is read from the configuration itself,
	 * because files_external drops a mount that failed in the background from
	 * the mount cache, so a session storage may never reach avs_storage.
	 *
	 * Ids, identifiers of files_external, codes and counts only: no mount
	 * point, no host, no share, no path (T-02-44).
	 *
	 * @return list<array{mountId: ?int, backend: string, authKind: string, reason: string, users: int}>
	 */
	public function skipped(): array {
		try {
			$rows = $this->storageStates->skipped();
		} catch (\Throwable $e) {
			$this->logger->error('Audio & Video Search: the storage classification could not be read', ['exception' => $e]);
			$rows = [];
		}

		/** @var array<string, array{mountId: ?int, backend: string, authKind: string, reason: string, users: int}> $entries */
		$entries = [];
		foreach ($rows as $row) {
			$reason = in_array($row['reason'], self::REASONS, true) ? (string)$row['reason'] : self::REASON_UNAVAILABLE;
			$auth = self::identifier($row['authKind']);
			$key = ($row['mountId'] ?? 'none') . '|' . $reason . '|' . $auth;
			if (!isset($entries[$key])) {
				$entries[$key] = ['mountId' => $row['mountId'], 'backend' => 'unknown', 'authKind' => $auth, 'reason' => $reason, 'users' => 0];
			}
			$entries[$key]['users'] += $row['users'];
		}

		$never = $this->neverConfigs();
		$missing = [];
		foreach ($never as $mountId => $config) {
			$key = $mountId . '|' . self::REASON_SESSION_CREDENTIALS . '|' . self::identifier($config['auth']);
			if (!isset($entries[$key])) {
				$entries[$key] = ['mountId' => $mountId, 'backend' => 'unknown', 'authKind' => self::identifier($config['auth']), 'reason' => self::REASON_SESSION_CREDENTIALS, 'users' => 0];
				$missing[] = $mountId;
			}
		}
		$users = $this->usersOfMounts($missing);

		$mountIds = array_values(array_unique(array_filter(array_column($entries, 'mountId'), static fn (?int $id): bool => $id !== null)));
		$configs = ($mountIds === [] ? [] : $this->mountConfigs($mountIds)) ?? [];
		foreach ($entries as $key => $entry) {
			$mountId = $entry['mountId'];
			if ($mountId !== null && isset($configs[$mountId])) {
				$entries[$key]['backend'] = self::identifier($configs[$mountId]['backend']);
			}
			if ($mountId !== null && in_array($mountId, $missing, true)) {
				$entries[$key]['users'] = $users[$mountId] ?? 0;
			}
		}

		$list = array_values($entries);
		usort($list, static fn (array $a, array $b): int => [$a['mountId'] ?? 0, $a['reason']] <=> [$b['mountId'] ?? 0, $b['reason']]);

		return $list;
	}

	/**
	 * The configuration to classify a storage by: the first one, by mount id,
	 * whose authentication can work in the background; only when every one
	 * needs the session, the first of those. Two configurations reach the same
	 * storage when they name the same share with the same login.
	 *
	 * @param list<int> $mountIds ascending
	 * @param array<int, array{backend: string, auth: string, type: int}> $configs
	 */
	private function chosenMount(array $mountIds, array $configs): ?int {
		$fallback = null;
		foreach ($mountIds as $mountId) {
			if (!isset($configs[$mountId])) {
				continue;
			}
			if (!in_array($configs[$mountId]['auth'], self::NEVER, true)) {
				return $mountId;
			}
			$fallback ??= $mountId;
		}

		return $fallback;
	}

	/**
	 * Does the credentials store hold what this authentication needs?
	 * true or false, or null when the store could not be read. Fixed
	 * credentials and no credentials need nothing stored: true, the probe
	 * decides. Keys after files_external (02-RESEARCH.md Befund 3).
	 */
	private function credentialsPresent(string $auth, string $uid, int $mountId, bool $adminMount): ?bool {
		$key = match ($auth) {
			'password::logincredentials' => [$uid, 'password::logincredentials/credentials'],
			'password::userprovided' => [$uid, 'password::userprovided/' . $mountId],
			'password::global' => [$adminMount ? '' : $uid, 'password::global'],
			'password::global::user' => [$uid, 'password::global'],
			default => null,
		};
		if ($key === null) {
			return true;
		}

		try {
			return $this->credentials->retrieve($key[0], $key[1]) !== null;
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the credentials store could not be read for an external storage', [
				'mount_id' => $mountId,
				'class' => $e::class,
			]);

			return null;
		}
	}

	/**
	 * Set the mount up as its user and look at the storage object: the same
	 * numeric storage, no FailedStorage, available. null for anything else.
	 */
	private function probe(ICachedMountInfo $info, int $storageId): ?IStorage {
		try {
			return $this->readerContext->actAs(
				$info->getUser()->getUID(),
				function () use ($info, $storageId): ?IStorage {
					$mount = $this->mountManager->getMountFromMountInfo($info);
					if ($mount === null || $mount->getNumericStorageId() !== $storageId) {
						return null;
					}
					$storage = $mount->getStorage();
					if ($storage === null || $storage->getId() === 'failedstorage' || $storage->instanceOfStorage(self::FAILED_STORAGE)) {
						return null;
					}
					$availability = $storage->getAvailability();

					return ($availability['available'] ?? false) === true ? $storage : null;
				},
			);
		} catch (\Throwable $e) {
			$this->logger->info('Audio & Video Search: an external storage could not be probed', [
				'storage_id' => $storageId,
				'class' => $e::class,
			]);

			return null;
		}
	}

	/**
	 * backend, authentication and type per mount id from oc_external_mounts;
	 * null when files_external is off or the table cannot be read, which
	 * makes the storage unavailable, never capturable. This and the two
	 * lookups below are protected only so the unit test can replace them.
	 *
	 * @param list<int> $mountIds
	 * @return array<int, array{backend: string, auth: string, type: int}>|null
	 */
	protected function mountConfigs(array $mountIds): ?array {
		try {
			if (!$this->appManager->isEnabledForAnyone('files_external')) {
				return null;
			}
			$qb = $this->db->getQueryBuilder();
			$qb->select('mount_id', 'storage_backend', 'auth_backend', 'type')
				->from('external_mounts')
				->where($qb->expr()->in('mount_id', $qb->createNamedParameter($mountIds, IQueryBuilder::PARAM_INT_ARRAY)));

			return $this->configRows($qb);
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the external storage configuration could not be read', ['class' => $e::class]);

			return null;
		}
	}

	/**
	 * Every configuration whose authentication is in NEVER, by mount id.
	 *
	 * @return array<int, array{backend: string, auth: string, type: int}>
	 */
	protected function neverConfigs(): array {
		try {
			if (!$this->appManager->isEnabledForAnyone('files_external')) {
				return [];
			}
			$qb = $this->db->getQueryBuilder();
			$qb->select('mount_id', 'storage_backend', 'auth_backend', 'type')
				->from('external_mounts')
				->where($qb->expr()->in('auth_backend', $qb->createNamedParameter(self::NEVER, IQueryBuilder::PARAM_STR_ARRAY)))
				->orderBy('mount_id', 'ASC');

			return $this->configRows($qb);
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the external storage configuration could not be read', ['class' => $e::class]);

			return [];
		}
	}

	/** @return array<int, array{backend: string, auth: string, type: int}> */
	private function configRows(IQueryBuilder $qb): array {
		$result = $qb->executeQuery();
		$configs = [];
		while (($row = $result->fetch()) !== false) {
			$configs[(int)$row['mount_id']] = [
				'backend' => (string)$row['storage_backend'],
				'auth' => (string)$row['auth_backend'],
				'type' => (int)$row['type'],
			];
		}
		$result->closeCursor();

		return $configs;
	}

	/**
	 * How many users the mount cache knows per mount id. Counts only.
	 *
	 * @param list<int> $mountIds
	 * @return array<int, int>
	 */
	protected function usersOfMounts(array $mountIds): array {
		if ($mountIds === []) {
			return [];
		}
		try {
			$qb = $this->db->getQueryBuilder();
			$qb->select('mount_id', 'user_id')
				->from('mounts')
				->where($qb->expr()->in('mount_id', $qb->createNamedParameter($mountIds, IQueryBuilder::PARAM_INT_ARRAY)));
			$result = $qb->executeQuery();
			$seen = [];
			while (($row = $result->fetch()) !== false) {
				$seen[(int)$row['mount_id']][(string)$row['user_id']] = true;
			}
			$result->closeCursor();
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the users of external storages could not be counted', ['class' => $e::class]);

			return [];
		}

		return array_map('count', $seen);
	}

	/** An identifier of files_external as printed, or "unknown". */
	private static function identifier(?string $value): string {
		return $value !== null && preg_match(self::IDENTIFIER, $value) === 1 ? $value : 'unknown';
	}
}
