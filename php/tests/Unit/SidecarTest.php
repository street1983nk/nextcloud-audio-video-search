<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Service\SidecarWriter;
use OCP\Files\Cache\ICache;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\NotPermittedException;
use OCP\Files\Storage\IStorage;
use OCP\Lock\ILockingProvider;
use OCP\Lock\LockedException;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The sidecar writer: never over an existing file, the existence question
 * and the creation under one exclusive lock, the lock released whatever
 * happens after it was taken. The folder and the locking provider are
 * doubles that keep a protocol of every call, so the order itself is the
 * assertion.
 */
#[CoversClass(SidecarWriter::class)]
final class SidecarTest extends TestCase {
	private const STORAGE_ID = 42;
	private const PARENT_PATH = 'files/Aufnahmen';

	/** @var list<string> every call of the folder and the locking provider, in order */
	private array $calls = [];

	/** @var array<string, string> the files of the folder, name to content */
	private array $stored = [];

	private bool $lockTaken = false;

	private bool $storageRefuses = false;

	private ?\Throwable $existenceFails = null;

	/** @var list<string> every log line with its context, as one text */
	private array $logged = [];

	protected function setUp(): void {
		parent::setUp();

		$this->calls = [];
		$this->stored = [];
		$this->lockTaken = false;
		$this->storageRefuses = false;
		$this->existenceFails = null;
		$this->logged = [];
	}

	private function writer(): SidecarWriter {
		$locking = $this->createMock(ILockingProvider::class);
		$locking->method('acquireLock')->willReturnCallback(function (string $path, int $type): void {
			if ($this->lockTaken) {
				throw new LockedException($path);
			}
			$this->calls[] = 'acquireLock ' . $path . ' ' . $type;
		});
		$locking->method('releaseLock')->willReturnCallback(function (string $path, int $type): void {
			$this->calls[] = 'releaseLock ' . $path . ' ' . $type;
		});

		$logger = $this->createMock(LoggerInterface::class);
		foreach (['debug', 'info', 'notice', 'warning', 'error'] as $level) {
			$logger->method($level)->willReturnCallback(function (string|\Stringable $message, array $context = []): void {
				$this->logged[] = $message . ' ' . json_encode($context);
			});
		}

		return new SidecarWriter($locking, $logger);
	}

	private function folder(): Folder&MockObject {
		$cache = $this->createMock(ICache::class);
		$cache->method('getNumericStorageId')->willReturn(self::STORAGE_ID);
		$storage = $this->createMock(IStorage::class);
		$storage->method('getCache')->willReturn($cache);

		$folder = $this->createMock(Folder::class);
		$folder->method('getStorage')->willReturn($storage);
		$folder->method('getInternalPath')->willReturn(self::PARENT_PATH);
		$folder->method('nodeExists')->willReturnCallback(function (string $name): bool {
			$this->calls[] = 'nodeExists ' . $name;
			if ($this->existenceFails !== null) {
				throw $this->existenceFails;
			}

			return array_key_exists($name, $this->stored);
		});
		$folder->method('newFile')->willReturnCallback(function (string $name, mixed $content = null): File {
			$this->calls[] = 'newFile ' . $name;
			if ($this->storageRefuses) {
				throw new NotPermittedException('no create permission');
			}
			$this->stored[$name] = (string)$content;

			return $this->createMock(File::class);
		});

		return $folder;
	}

	/** The key the writer must lock for one name: storage id and hashed target path. */
	private static function lockKey(string $name): string {
		return 'avs-sidecar/' . self::STORAGE_ID . '/' . sha1(self::PARENT_PATH . '/' . $name);
	}

	// -- the happy path and its order --------------------------------------------------

	public function testANewFileIsCreatedUnderTheLockInTheRightOrder(): void {
		$result = $this->writer()->write($this->folder(), 'sitzung.de.vtt', "WEBVTT\n\nNOTE\nEntwurf\n\n");

		self::assertSame(SidecarWriter::CREATED, $result);
		self::assertSame("WEBVTT\n\nNOTE\nEntwurf\n\n", $this->stored['sitzung.de.vtt']);
		$key = self::lockKey('sitzung.de.vtt');
		$exclusive = ILockingProvider::LOCK_EXCLUSIVE;
		self::assertSame([
			'acquireLock ' . $key . ' ' . $exclusive,
			'nodeExists sitzung.de.vtt',
			'newFile sitzung.de.vtt',
			'releaseLock ' . $key . ' ' . $exclusive,
		], $this->calls);
	}

	public function testAnUmlautNameAndA255ByteNameAreTakenAsTheyAre(): void {
		self::assertSame(SidecarWriter::CREATED, $this->writer()->write($this->folder(), 'Übung.fr.vtt', 'a'));

		$longest = str_repeat('a', 251) . '.vtt';
		self::assertSame(255, strlen($longest));
		self::assertSame(SidecarWriter::CREATED, $this->writer()->write($this->folder(), $longest, 'b'));
	}

	// -- never over an existing file (D-04-05) ------------------------------------------

	public function testAnExistingFileStaysByteForByteAndNewFileIsNeverCalled(): void {
		$this->stored['sitzung.de.vtt'] = "WEBVTT\n\nder alte, korrigierte Untertitel\n";
		$before = hash('sha256', $this->stored['sitzung.de.vtt']);

		$result = $this->writer()->write($this->folder(), 'sitzung.de.vtt', "WEBVTT\n\nder neue Entwurf\n");

		self::assertSame(SidecarWriter::EXISTS, $result);
		self::assertSame($before, hash('sha256', $this->stored['sitzung.de.vtt']));
		$key = self::lockKey('sitzung.de.vtt');
		$exclusive = ILockingProvider::LOCK_EXCLUSIVE;
		self::assertSame([
			'acquireLock ' . $key . ' ' . $exclusive,
			'nodeExists sitzung.de.vtt',
			'releaseLock ' . $key . ' ' . $exclusive,
		], $this->calls);
	}

	// -- the lock ------------------------------------------------------------------------

	public function testATakenLockIsBusyAndNothingIsAskedOrWritten(): void {
		$this->lockTaken = true;

		$result = $this->writer()->write($this->folder(), 'sitzung.de.vtt', 'x');

		self::assertSame(SidecarWriter::BUSY, $result);
		self::assertSame([], $this->calls);
		self::assertSame([], $this->stored);
	}

	public function testTheLockIsReleasedWhenTheExistenceQuestionThrows(): void {
		$this->existenceFails = new \RuntimeException('the storage is gone');

		try {
			$this->writer()->write($this->folder(), 'sitzung.de.vtt', 'x');
			self::fail('the storage error must reach the caller');
		} catch (\RuntimeException $e) {
			self::assertSame($this->existenceFails, $e);
		}

		$key = self::lockKey('sitzung.de.vtt');
		$exclusive = ILockingProvider::LOCK_EXCLUSIVE;
		self::assertSame([
			'acquireLock ' . $key . ' ' . $exclusive,
			'nodeExists sitzung.de.vtt',
			'releaseLock ' . $key . ' ' . $exclusive,
		], $this->calls);
	}

	// -- the storage refuses -------------------------------------------------------------

	public function testARefusedCreationIsNotWritableTheLockIsReleasedAndTheLogNamesTheClassOnly(): void {
		$this->storageRefuses = true;

		$result = $this->writer()->write($this->folder(), 'sitzung.de.vtt', 'x');

		self::assertSame(SidecarWriter::NOT_WRITABLE, $result);
		self::assertSame([], $this->stored);
		$key = self::lockKey('sitzung.de.vtt');
		$exclusive = ILockingProvider::LOCK_EXCLUSIVE;
		self::assertSame([
			'acquireLock ' . $key . ' ' . $exclusive,
			'nodeExists sitzung.de.vtt',
			'newFile sitzung.de.vtt',
			'releaseLock ' . $key . ' ' . $exclusive,
		], $this->calls);
		self::assertCount(1, $this->logged);
		self::assertStringContainsString('NotPermittedException', $this->logged[0]);
		self::assertStringNotContainsString('sitzung', $this->logged[0]);
		self::assertStringNotContainsString(self::PARENT_PATH, $this->logged[0]);
		self::assertStringNotContainsString($key, $this->logged[0]);
	}

	// -- the name is checked, not built --------------------------------------------------

	/** @return array<string, array{string}> */
	public static function brokenNames(): array {
		return [
			'a slash' => ['Aufnahmen/sitzung.de.vtt'],
			'a backslash' => ['sitzung\\alt.de.vtt'],
			'the parent' => ['..'],
			'the dot' => ['.'],
			'empty' => [''],
			'256 bytes with umlauts' => [str_repeat('ä', 126) . '.vtt'],
		];
	}

	#[DataProvider('brokenNames')]
	public function testANameThatIsNoPlainFileNameThrowsBeforeAnyLock(string $name): void {
		$writer = $this->writer();
		$folder = $this->folder();

		$this->expectException(\InvalidArgumentException::class);
		try {
			$writer->write($folder, $name, 'x');
		} finally {
			self::assertSame([], $this->calls);
			self::assertSame([], $this->stored);
		}
	}

	public function testTheOverlongProbeIsReally256Bytes(): void {
		self::assertSame(256, strlen(str_repeat('ä', 126) . '.vtt'));
	}
}
