<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IRootFolder;
use OCP\Files\Node;

/**
 * The one place that asks whether a user may read a file.
 *
 * The search provider, the playback page, the content gateway and the occ
 * command all ask here, so the question cannot be half asked a second time.
 * backend/tests/test_php_gates.py (rule 4) holds the node lookup by id to this
 * file.
 *
 * There is deliberately no answer to "reachable, but closed". The ACL wrapper
 * of groupfolders can hide a node entirely, and then the lookup answers
 * exactly what it answers for a file that does not exist. Callers answer both
 * the same way.
 *
 * Every lookup that runs on behalf of a user other than the active one belongs
 * inside ReaderContext::actAs, see there.
 */
final class FileAccess {
	/**
	 * The file behind $fileId in the tree of $userFolder, or null when it does
	 * not exist there, is not a file, or is not readable for that user.
	 */
	public static function readableFile(Folder $userFolder, int $fileId): ?File {
		if ($fileId <= 0) {
			return null;
		}

		return self::readableNode($userFolder->getFirstNodeById($fileId));
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
