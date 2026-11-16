<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCP\Files\Folder;
use OCP\Files\NotPermittedException;
use OCP\Lock\ILockingProvider;
use OCP\Lock\LockedException;
use Psr\Log\LoggerInterface;

/**
 * Creates the sidecar file next to the medium, and never over anything.
 *
 * Folder::newFile silently overwrites an existing file: with a content it
 * ends in view->file_put_contents on the full path, with no existence check
 * of its own (lib/private/Files/Node/Folder.php, stable34, lines 171 to
 * 194). A draft must never replace a subtitle somebody corrected (D-04-05),
 * so the existence question and the creation run here, under one exclusive
 * lock of this app, and newFile is never called for a name that exists.
 *
 * The lock key names no user and no path in the clear:
 * avs-sidecar/{numeric storage id}/{sha1 of the internal path of the target}.
 * It covers only this app against itself: two parallel sidecar requests for
 * the same target serialise, the second one sees the file of the first and
 * reports it. A foreign client that creates the same name between the check
 * and the creation stays possible for milliseconds; that rest is carried in
 * SECURITY.md as an accepted risk (plan 04-13), because the server offers no
 * create-only primitive here.
 *
 * The caller runs write() as the user (ReaderContext::actAs), so quota, ACL
 * and the permission wrappers answer as in the Files app; a refusal of the
 * storage is an answer, not an exception of this class. Nothing here logs a
 * name, a path or the lock key.
 */
final class SidecarWriter {
	public const CREATED = 'created';
	public const EXISTS = 'exists';
	public const BUSY = 'busy';
	public const NOT_WRITABLE = 'not_writable';

	/** The file name limit of the common storages, in bytes. */
	public const MAX_NAME_BYTES = 255;

	public function __construct(
		private ILockingProvider $locking,
		private LoggerInterface $logger,
	) {
	}

	/**
	 * One attempt to create $name in $parent: CREATED when the file is new,
	 * EXISTS when the name is taken (nothing is written, the file stays byte
	 * for byte), BUSY when another request holds the lock of this target
	 * right now, NOT_WRITABLE when the storage refuses the creation.
	 *
	 * The name is built elsewhere (ExportController::downloadName, NFC) and
	 * only checked here: a value that is empty, a dot name, longer than 255
	 * bytes or carries a slash or backslash is a programming error and throws.
	 *
	 * @throws \InvalidArgumentException when $name is no plain file name
	 */
	public function write(Folder $parent, string $name, string $content): string {
		if (!self::plainName($name)) {
			throw new \InvalidArgumentException('the sidecar name is no plain file name');
		}

		$key = $this->lockKey($parent, $name);
		try {
			$this->locking->acquireLock($key, ILockingProvider::LOCK_EXCLUSIVE);
		} catch (LockedException) {
			// Another request is creating this very target right now: no
			// second write, the caller reports the collision (D-04-05).
			return self::BUSY;
		}

		try {
			if ($parent->nodeExists($name)) {
				return self::EXISTS;
			}
			try {
				$parent->newFile($name, $content);
			} catch (NotPermittedException $e) {
				// isCreatable said yes, the storage says no: quota, ACL or a
				// wrapper deeper down. An answer, not an error of this app.
				$this->logger->info('Audio & Video Search: the storage refused to create the sidecar', [
					'class' => $e::class,
				]);

				return self::NOT_WRITABLE;
			}

			return self::CREATED;
		} finally {
			$this->locking->releaseLock($key, ILockingProvider::LOCK_EXCLUSIVE);
		}
	}

	/**
	 * The lock key of one target: the numeric storage id and the hashed
	 * internal path, so the key is stable across users of the same storage
	 * and carries no readable path into the lock table.
	 */
	private function lockKey(Folder $parent, string $name): string {
		$storageId = $parent->getStorage()->getCache()->getNumericStorageId();

		return 'avs-sidecar/' . $storageId . '/' . sha1($parent->getInternalPath() . '/' . $name);
	}

	/** A non-empty single path segment of at most 255 bytes, and no dot name. */
	private static function plainName(string $name): bool {
		return $name !== '' && $name !== '.' && $name !== '..'
			&& !str_contains($name, '/') && !str_contains($name, '\\')
			&& strlen($name) <= self::MAX_NAME_BYTES;
	}
}
