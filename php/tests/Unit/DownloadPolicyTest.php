<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Service\DownloadPolicy;
use OCP\Files\File;
use OCP\Files\Storage\ISharedStorage;
use OCP\Files\Storage\IStorage;
use OCP\Share\IAttributes;
use OCP\Share\IShare;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The one verdict about the download switch of a received share, and the two
 * readings of it: playback fails open (WebDAV checks the attribute again),
 * export fails closed (nothing checks after the export routes).
 */
#[CoversClass(DownloadPolicy::class)]
final class DownloadPolicyTest extends TestCase {
	/** @var list<string> every log line with its context, as one text */
	private array $logged = [];

	protected function setUp(): void {
		parent::setUp();

		$this->logged = [];
	}

	private function policy(): DownloadPolicy {
		$logger = $this->createMock(LoggerInterface::class);
		foreach (['debug', 'info', 'notice', 'warning', 'error'] as $level) {
			$logger->method($level)->willReturnCallback(function (string|\Stringable $message, array $context = []): void {
				$this->logged[] = $message . ' ' . json_encode($context);
			});
		}

		return new DownloadPolicy($logger);
	}

	private function file(IStorage $storage): File&MockObject {
		$file = $this->createMock(File::class);
		$file->method('getName')->willReturn('Personalsitzung.webm');
		$file->method('getStorage')->willReturn($storage);

		return $file;
	}

	private function plainStorage(): IStorage&MockObject {
		$storage = $this->createMock(IStorage::class);
		$storage->method('instanceOfStorage')->willReturn(false);

		return $storage;
	}

	/** A received share whose download switch is set to $download (null: not set). */
	private function sharedStorage(?bool $download): ISharedStorage&MockObject {
		$attributes = $this->createMock(IAttributes::class);
		$attributes->method('getAttribute')->willReturnCallback(
			static fn (string $scope, string $key): ?bool => $scope === 'permissions' && $key === 'download' ? $download : null,
		);
		$share = $this->createMock(IShare::class);
		$share->method('getAttributes')->willReturn($attributes);

		$storage = $this->createMock(ISharedStorage::class);
		$storage->method('instanceOfStorage')->willReturnCallback(
			static fn (string $class): bool => $class === ISharedStorage::class,
		);
		$storage->method('getShare')->willReturn($share);

		return $storage;
	}

	private function brokenStorage(): ISharedStorage&MockObject {
		$storage = $this->createMock(ISharedStorage::class);
		$storage->method('instanceOfStorage')->willReturnCallback(
			static fn (string $class): bool => $class === ISharedStorage::class,
		);
		$storage->method('getShare')->willThrowException(new \RuntimeException('share table away for Personalsitzung.webm'));

		return $storage;
	}

	// -- the four verdicts of decide ------------------------------------------------

	public function testAFileOutsideAReceivedShareIsAllowed(): void {
		$verdict = $this->policy()->decide($this->file($this->plainStorage()), 7);

		self::assertSame(DownloadPolicy::ALLOWED, $verdict);
		self::assertSame([], $this->logged);
	}

	public function testAShareWithTheDownloadSwitchOffIsBlocked(): void {
		self::assertSame(DownloadPolicy::BLOCKED, $this->policy()->decide($this->file($this->sharedStorage(false)), 7));
	}

	/** @return array<string, array{?bool}> */
	public static function openSwitches(): array {
		return [
			'attribute not set' => [null],
			'attribute true' => [true],
		];
	}

	#[DataProvider('openSwitches')]
	public function testAShareWithoutABlockingAttributeIsAllowed(?bool $download): void {
		self::assertSame(DownloadPolicy::ALLOWED, $this->policy()->decide($this->file($this->sharedStorage($download)), 7));
	}

	public function testAnAttributeThatCannotBeReadIsUnknownAndLogsNeitherNameNorPath(): void {
		$verdict = $this->policy()->decide($this->file($this->brokenStorage()), 7);

		self::assertSame(DownloadPolicy::UNKNOWN, $verdict);
		self::assertCount(1, $this->logged);
		self::assertStringContainsString('"fileId":7', $this->logged[0]);
		self::assertStringContainsString('RuntimeException', $this->logged[0]);
		self::assertStringNotContainsString('Personalsitzung', $this->logged[0]);
	}

	// -- the two readings -------------------------------------------------------------

	public function testPlaybackFailsOpenAndBlocksOnlyTheBlockedVerdict(): void {
		$policy = $this->policy();

		self::assertTrue($policy->allowsPlayback($this->file($this->plainStorage()), 7));
		self::assertTrue($policy->allowsPlayback($this->file($this->sharedStorage(null)), 7));
		self::assertTrue($policy->allowsPlayback($this->file($this->brokenStorage()), 7));
		self::assertFalse($policy->allowsPlayback($this->file($this->sharedStorage(false)), 7));
	}

	public function testExportFailsClosedAndAllowsOnlyTheAllowedVerdict(): void {
		$policy = $this->policy();

		self::assertTrue($policy->allowsExport($this->file($this->plainStorage()), 7));
		self::assertTrue($policy->allowsExport($this->file($this->sharedStorage(true)), 7));
		self::assertFalse($policy->allowsExport($this->file($this->sharedStorage(false)), 7));
		self::assertFalse($policy->allowsExport($this->file($this->brokenStorage()), 7));
	}
}
