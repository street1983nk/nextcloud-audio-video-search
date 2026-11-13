<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IRootFolder;
use OCP\Files\Node;
use OCP\Files\Storage\IStorage;

/**
 * The one place that asks whether a user may read a file.
 *
 * The search provider, the playback page, the content gateway and the occ
 * command all ask here, so the question cannot be half asked a second time.
 * backend/tests/test_php_gates.py (rule 4) holds the node lookup by id to this
 * file.
 *
 * There is deliberately no answer to "reachable, but closed" for the pages a
 * user sees. The ACL wrapper of groupfolders can hide a node entirely, and
 * then the lookup answers exactly what it answers for a file that does not
 * exist. Callers answer both the same way.
 *
 * The content gateway alone asks one question more, and only the container
 * hears the answer: whether a file that is listed for the user is closed by a
 * rule of files_accesscontrol and by nothing else (refusedByAccessControl).
 * The container then waits for the rule instead of treating the file as gone.
 *
 * Every lookup that runs on behalf of a user other than the active one belongs
 * inside ReaderContext::actAs, see there.
 */
final class FileAccess {
	/**
	 * The storage wrapper of the app files_accesscontrol, named as a string:
	 * the app is optional and this class must load without it.
	 */
	private const ACCESS_CONTROL_STORAGE = 'OCA\FilesAccessControl\StorageWrapper';
	/** Upper bound of the walk down the storage wrappers, far above any real stack. */
	private const MAX_STORAGE_LAYERS = 32;

	/**
	 * The node behind $fileId in the tree of $userFolder, readable or not, or
	 * null when it is not there for that user.
	 */
	public static function nodeById(Folder $userFolder, int $fileId): ?Node {
		if ($fileId <= 0) {
			return null;
		}

		return $userFolder->getFirstNodeById($fileId);
	}

	/**
	 * The file behind $fileId in the tree of $userFolder, or null when it does
	 * not exist there, is not a file, or is not readable for that user.
	 */
	public static function readableFile(Folder $userFolder, int $fileId): ?File {
		return self::readableNode(self::nodeById($userFolder, $fileId));
	}

	/**
	 * The same question for a node the caller already holds.
	 */
	public static function readableNode(?Node $node): ?File {
		if (!$node instanceof File) {
			return null;
		}

		return $node->isReadable() ? $node : null;
	}

	/**
	 * Whether $node is a file the user sees and that a rule of
	 * files_accesscontrol, and nothing else, keeps them from reading.
	 *
	 * How that app refuses (read at stable33, lib/CacheWrapper.php and
	 * lib/StorageWrapper.php): in web requests it wraps the storage of every
	 * mount. A rule that matches does not hide the file and does not throw at
	 * the lookup; the cache wrapper takes the read permission out of the cache
	 * entry. So the node is found and isReadable() is false, which looks like
	 * any other closed file. The difference is asked at the storage: the
	 * wrapper of the app says "not readable" while the storage right below it
	 * says "readable". The file is not opened for this.
	 *
	 * Everything else is false: no node, a folder, a readable file, no such
	 * wrapper, a file the storage below refuses as well, and any failure while
	 * asking. False keeps the plain 404 of the gateway.
	 */
	public static function refusedByAccessControl(?Node $node): bool {
		if (!$node instanceof File || $node->isReadable()) {
			return false;
		}

		try {
			$layer = $node->getStorage();
			if (!$layer instanceof IStorage || !$layer->instanceOfStorage(self::ACCESS_CONTROL_STORAGE)) {
				return false;
			}
			$path = $node->getInternalPath();

			// Down the wrappers to the one of files_accesscontrol: the last
			// layer that still has it at or below itself.
			for ($depth = 0; $depth < self::MAX_STORAGE_LAYERS; $depth++) {
				if (!method_exists($layer, 'getWrapperStorage')) {
					return false;
				}
				$below = $layer->getWrapperStorage();
				if (!$below instanceof IStorage) {
					return false;
				}
				if (!$below->instanceOfStorage(self::ACCESS_CONTROL_STORAGE)) {
					return !$layer->isReadable($path) && $below->isReadable($path);
				}
				if ($layer instanceof \OC\Files\Storage\Wrapper\Jail) {
					// Below a jail the path is another one; no guess.
					return false;
				}
				$layer = $below;
			}
		} catch (\Throwable) {
			return false;
		}

		return false;
	}

	/**
	 * The path of a node in the cache of its numeric storage, the space the
	 * walk roots of StorageService::mountRoots are written in, or null when it
	 * cannot be told. Never logged.
	 *
	 * The internal path of a node is the path inside the storage of its mount.
	 * When that storage is a jail (a team folder of groupfolders, a share),
	 * the path is the one below the jail, and the cache of the numeric storage
	 * holds it with the root of the jail in front (Cache::moveFromCache and the
	 * other cache events carry that one). So the walk goes down the wrappers
	 * and maps the path at every jail, the way the jail itself does when it
	 * hands a call on. Without a jail the internal path is already that path.
	 */
	public static function storagePath(Node $node): ?string {
		try {
			$path = (string)$node->getInternalPath();
			$layer = $node->getStorage();
			for ($depth = 0; $depth < self::MAX_STORAGE_LAYERS; $depth++) {
				if (!$layer instanceof \OC\Files\Storage\Wrapper\Wrapper) {
					return $path;
				}
				if ($layer instanceof \OC\Files\Storage\Wrapper\Jail) {
					$path = $layer->getUnjailedPath($path);
				}
				$layer = $layer->getWrapperStorage();
			}
		} catch (\Throwable) {
			return null;
		}

		return null;
	}

	/**
	 * The path of a confirmed file relative to the user folder, without a
	 * leading slash. Never logged and never put into an error answer.
	 */
	public static function relativePath(Folder $userFolder, File $file): string {
		return ltrim((string)$userFolder->getRelativePath($file->getPath()), '/');
	}

	/**
	 * The uid of the owner of a file anywhere on the instance, or null.
	 *
	 * For the occ command only, which has no user of its own to ask as. The
	 * answer is a name to ask the readability question as, never a permission:
	 * the caller still asks readableFile() in that user's folder.
	 */
	public static function ownerOf(IRootFolder $rootFolder, int $fileId): ?string {
		if ($fileId <= 0) {
			return null;
		}

		$uid = $rootFolder->getFirstNodeById($fileId)?->getOwner()?->getUID();

		return is_string($uid) && $uid !== '' ? $uid : null;
	}
}
