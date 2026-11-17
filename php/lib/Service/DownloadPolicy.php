<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCP\Files\File;
use OCP\Files\Storage\ISharedStorage;
use Psr\Log\LoggerInterface;

/**
 * The download switch of a received share, answered once for every route.
 *
 * A file that does not sit in a received share is ALLOWED. In a received
 * share the attribute decides: download set to false is BLOCKED, the
 * attribute missing or true is ALLOWED. Mirrors the server: Share20\Manager
 * and the ViewOnlyPlugin of WebDAV read the same attribute, so the verdict
 * here is the verdict WebDAV enforces. IShare has a canDownload helper for
 * this question, but only since 33.0.1; this app supports 33.0.0, so the
 * attribute is read directly, as the server itself does.
 *
 * When the attribute cannot be read the verdict is UNKNOWN, and the two
 * callers part ways:
 *
 * - Playback treats UNKNOWN like ALLOWED (fail open, the behaviour the
 *   playback page always had): the medium plays over WebDAV, where the
 *   ViewOnlyPlugin checks the same attribute a second time, and play.js maps
 *   a 403 of WebDAV to the blocked notice. Nothing leaves the server that
 *   WebDAV would not hand out anyway.
 * - Export treats UNKNOWN like BLOCKED (fail closed): the export routes hand
 *   the transcript out themselves, there is no second check behind them, so
 *   a verdict that cannot be read must not open the door (SRCH-04, T-04-30).
 *
 * The log carries the file id and the exception class, never a name or a
 * path (gate rule 6).
 */
final class DownloadPolicy {
	public const ALLOWED = 'allowed';
	public const BLOCKED = 'blocked';
	public const UNKNOWN = 'unknown';

	public function __construct(
		private LoggerInterface $logger,
	) {
	}

	/** One of ALLOWED, BLOCKED or UNKNOWN for this file, as decided above. */
	public function decide(File $file, int $fileId): string {
		try {
			$storage = $file->getStorage();
			if (!$storage->instanceOfStorage(ISharedStorage::class)) {
				return self::ALLOWED;
			}

			/** @var ISharedStorage $storage */
			return $storage->getShare()->getAttributes()?->getAttribute('permissions', 'download') !== false
				? self::ALLOWED
				: self::BLOCKED;
		} catch (\Throwable $e) {
			$this->logger->info('Audio & Video Search: the share rules of a file could not be read', [
				'fileId' => $fileId,
				'class' => $e::class,
			]);

			return self::UNKNOWN;
		}
	}

	/**
	 * False only for a share whose download switch is off. UNKNOWN plays,
	 * because WebDAV checks the same attribute again before any byte leaves.
	 */
	public function allowsPlayback(File $file, int $fileId): bool {
		return $this->decide($file, $fileId) !== self::BLOCKED;
	}

	/**
	 * True only for a clear ALLOWED. UNKNOWN blocks the export: these routes
	 * hand the transcript out themselves and nothing checks after them.
	 */
	public function allowsExport(File $file, int $fileId): bool {
		return $this->decide($file, $fileId) === self::ALLOWED;
	}
}
