<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCP\IL10N;

/**
 * The one formatter of byte amounts on the admin page (plan 05-05, UI-SPEC
 * "Einheiten und Zahlenformat", pitfall 9).
 *
 * The container counts in bytes; the page shows GB = 10^9 bytes with one
 * decimal, the decimal separator of the admin language (de and fr a comma,
 * every other language a point) and the unit through the catalogue (T96,
 * "GB", fr "Go").
 *
 * The rounding depends on what the number means:
 *   need       rounded up, and never below 0.1 for a need above zero,
 *   available  rounded down,
 *   size       rounded half up (model sizes and download progress).
 * So a lock never reads "needs 3.0 GB, 3.0 GB available": when the need is
 * above what is available, the rounded need is above the rounded availability.
 *
 * The arithmetic runs in whole tenths of a GB with intdiv; no float is
 * compared anywhere.
 */
final class ResourceFormat {
	public const MODE_NEED = 'need';
	public const MODE_AVAILABLE = 'available';
	public const MODE_SIZE = 'size';

	/** Bytes in a tenth of a GB (10^8). */
	private const TENTH = 100000000;

	/** Languages that write a decimal comma. */
	private const COMMA_LANGUAGES = ['de', 'fr'];

	private function __construct() {
	}

	/**
	 * "4,9 GB", "4.9 GB" or "4,9 Go" for an amount of bytes.
	 *
	 * @throws \InvalidArgumentException for a mode other than need, available or size
	 */
	public static function gigabytes(int $bytes, string $mode, IL10N $l): string {
		$bytes = max(0, $bytes);
		$tenths = match ($mode) {
			self::MODE_NEED => intdiv($bytes + self::TENTH - 1, self::TENTH),
			self::MODE_AVAILABLE => intdiv($bytes, self::TENTH),
			self::MODE_SIZE => intdiv($bytes + intdiv(self::TENTH, 2), self::TENTH),
			default => throw new \InvalidArgumentException('Unknown mode'),
		};

		$number = intdiv($tenths, 10) . self::separator($l) . ($tenths % 10);

		return $l->t('%s GB', [$number]);
	}

	private static function separator(IL10N $l): string {
		$language = strtolower(substr($l->getLanguageCode(), 0, 2));

		return in_array($language, self::COMMA_LANGUAGES, true) ? ',' : '.';
	}
}
