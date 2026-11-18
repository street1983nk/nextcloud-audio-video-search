<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Service\ResourceFormat;
use OCP\IL10N;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

/**
 * Bytes as GB = 10^9 with one decimal (UI-SPEC "Einheiten und Zahlenformat"):
 * need rounded up, available rounded down, sizes rounded half up; the
 * decimal comma in de and fr, the unit through T96 ("GB", fr "Go").
 */
#[CoversClass(ResourceFormat::class)]
final class ResourceFormatTest extends TestCase {
	private function l10n(string $language): IL10N {
		$l = $this->createMock(IL10N::class);
		$l->method('getLanguageCode')->willReturn($language);
		$l->method('t')->willReturnCallback(
			static function (string $text, array $parameters = []) use ($language): string {
				$translated = ($text === '%s GB' && $language === 'fr') ? '%s Go' : $text;

				return vsprintf($translated, $parameters);
			},
		);

		return $l;
	}

	/** @return array<string, array{int, string, string, string}> */
	public static function cases(): array {
		return [
			'need 4.5 GiB rounds up' => [4831838208, ResourceFormat::MODE_NEED, 'de', '4,9 GB'],
			'need 4.5 GiB in en' => [4831838208, ResourceFormat::MODE_NEED, 'en', '4.9 GB'],
			'need 4.5 GiB in fr' => [4831838208, ResourceFormat::MODE_NEED, 'fr', '4,9 Go'],
			'need in de_DE' => [4831838208, ResourceFormat::MODE_NEED, 'de_DE', '4,9 GB'],
			'available exact' => [3100000000, ResourceFormat::MODE_AVAILABLE, 'de', '3,1 GB'],
			'available rounds down' => [3149999999, ResourceFormat::MODE_AVAILABLE, 'de', '3,1 GB'],
			'available just below a tenth' => [3199999999, ResourceFormat::MODE_AVAILABLE, 'de', '3,1 GB'],
			'size turbo' => [1617884929, ResourceFormat::MODE_SIZE, 'de', '1,6 GB'],
			'size large-v3' => [3087284237, ResourceFormat::MODE_SIZE, 'de', '3,1 GB'],
			'size half rounds up' => [1650000000, ResourceFormat::MODE_SIZE, 'en', '1.7 GB'],
			'size in fr' => [3087284237, ResourceFormat::MODE_SIZE, 'fr', '3,1 Go'],
			'need of one byte' => [1, ResourceFormat::MODE_NEED, 'de', '0,1 GB'],
			'need of zero' => [0, ResourceFormat::MODE_NEED, 'de', '0,0 GB'],
			'available of zero' => [0, ResourceFormat::MODE_AVAILABLE, 'de', '0,0 GB'],
			'size of zero' => [0, ResourceFormat::MODE_SIZE, 'de', '0,0 GB'],
			'negative is zero' => [-5, ResourceFormat::MODE_AVAILABLE, 'de', '0,0 GB'],
			'ten and more' => [12345678901, ResourceFormat::MODE_AVAILABLE, 'en', '12.3 GB'],
		];
	}

	#[DataProvider('cases')]
	public function testTheAmountIsFormatted(int $bytes, string $mode, string $language, string $expected): void {
		self::assertSame($expected, ResourceFormat::gigabytes($bytes, $mode, $this->l10n($language)));
	}

	/** @return array<string, array{int, int}> */
	public static function lockPairs(): array {
		return [
			'one byte apart on a tenth' => [3000000001, 3000000000],
			'within one tenth' => [3060000000, 3040000000],
			'far apart' => [5368709120, 3328599654],
			'exactly a tenth apart' => [3100000000, 3000000000],
		];
	}

	#[DataProvider('lockPairs')]
	public function testALockNeverShowsTheSameNumberTwice(int $need, int $available): void {
		$l = $this->l10n('de');

		self::assertGreaterThan($available, $need);
		self::assertNotSame(
			ResourceFormat::gigabytes($need, ResourceFormat::MODE_NEED, $l),
			ResourceFormat::gigabytes($available, ResourceFormat::MODE_AVAILABLE, $l),
		);
	}

	public function testAnUnknownModeIsRefused(): void {
		$this->expectException(\InvalidArgumentException::class);

		ResourceFormat::gigabytes(1, 'gibibytes', $this->l10n('de'));
	}
}
