<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Command\SampleCommand;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IRootFolder;
use OCP\IConfig;
use OCP\IUser;
use OCP\IUserManager;
use OCP\IUserSession;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\ArrayInput;
use Symfony\Component\Console\Output\BufferedOutput;

/**
 * The debug seed: only with debug => true, only for a file that exists and is
 * readable, and --remove only ever removes a test result.
 */
#[CoversClass(SampleCommand::class)]
final class SampleCommandTest extends TestCase {
	private bool $debug = true;

	/** @var array<mixed>|null what the container answers to /sample */
	private ?array $sampleAnswer = null;

	/** @var array<mixed>|null what the container answers to /sample/remove */
	private ?array $removeAnswer = null;

	/** @var list<array{string, string, int, ?int}> method, uid, fileId, atMs */
	private array $calls = [];

	private BufferedOutput $output;

	protected function setUp(): void {
		parent::setUp();

		$this->debug = true;
		$this->sampleAnswer = ['result' => 'published', 'mediaId' => 3, 'indexRev' => 9];
		$this->removeAnswer = ['result' => 'removed', 'mediaId' => 3];
		$this->calls = [];
		$this->output = new BufferedOutput();
	}

	private function command(): SampleCommand {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('sample')->willReturnCallback(function (string $uid, int $fileId, int $atMs): ?array {
			$this->calls[] = ['sample', $uid, $fileId, $atMs];

			return $this->sampleAnswer;
		});
		$exApp->method('removeSample')->willReturnCallback(function (string $uid, int $fileId): ?array {
			$this->calls[] = ['removeSample', $uid, $fileId, null];

			return $this->removeAnswer;
		});

		$owner = $this->createMock(IUser::class);
		$owner->method('getUID')->willReturn('alice');
		$file = $this->createMock(File::class);
		$file->method('isReadable')->willReturn(true);
		$file->method('getOwner')->willReturn($owner);
		$file->method('getPath')->willReturn('/alice/files/Geheim/Sitzung.mp4');

		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturnCallback(static fn (int $id): ?File => $id === 11 ? $file : null);
		$root = $this->createMock(IRootFolder::class);
		$root->method('getFirstNodeById')->willReturnCallback(static fn (int $id): ?File => $id === 11 ? $file : null);
		$root->method('getUserFolder')->willReturnCallback(static function (string $uid) use ($userFolder): Folder {
			if ($uid !== 'alice' && $uid !== 'bob') {
				throw new \OC\User\NoUserException($uid);
			}

			return $userFolder;
		});

		$config = $this->createMock(IConfig::class);
		$config->method('getSystemValueBool')->willReturnCallback(
			fn (string $key, bool $default = false): bool => $key === 'debug' ? $this->debug : $default,
		);

		return new SampleCommand(
			$exApp,
			$root,
			new ReaderContext($this->createMock(IUserSession::class), $this->createMock(IUserManager::class)),
			$config,
		);
	}

	/** @param array<string, mixed> $input */
	private function runCommand(array $input): int {
		return $this->command()->run(new ArrayInput($input), $this->output);
	}

	public function testWithoutDebugModeNothingIsCreated(): void {
		$this->debug = false;

		self::assertSame(Command::FAILURE, $this->runCommand(['fileId' => '11']));
		self::assertStringContainsString('Debug mode is off', $this->output->fetch());
		self::assertSame([], $this->calls);
	}

	public function testANonNumericFileIdIsInvalid(): void {
		self::assertSame(Command::INVALID, $this->runCommand(['fileId' => 'abc']));
		self::assertSame(Command::INVALID, $this->runCommand(['fileId' => '0']));
		self::assertSame(Command::INVALID, $this->runCommand(['fileId' => '-4']));
		self::assertSame([], $this->calls);
	}

	public function testAnUnknownFileFailsWithoutAPath(): void {
		self::assertSame(Command::FAILURE, $this->runCommand(['fileId' => '12']));
		$text = $this->output->fetch();
		self::assertStringContainsString('File not found or not readable.', $text);
		self::assertStringNotContainsString('/', $text);
		self::assertSame([], $this->calls);
	}

	public function testAnUnknownUserFailsLikeAnUnknownFile(): void {
		self::assertSame(Command::FAILURE, $this->runCommand(['fileId' => '11', '--user' => 'ghost']));
		self::assertStringContainsString('File not found or not readable.', $this->output->fetch());
		self::assertSame([], $this->calls);
	}

	public function testASuccessReportsMediaAndRevisionAtTheDefaultMark(): void {
		self::assertSame(Command::SUCCESS, $this->runCommand(['fileId' => '11']));
		$text = $this->output->fetch();
		self::assertStringContainsString('published', $text);
		self::assertStringContainsString('media 3', $text);
		self::assertStringNotContainsString('Sitzung', $text);
		self::assertSame([['sample', 'alice', 11, 42000]], $this->calls);
	}

	public function testAtIsSecondsWithUpToThreeDecimals(): void {
		$this->runCommand(['fileId' => '11', '--at' => '42']);
		$this->runCommand(['fileId' => '11', '--at' => '1.5']);
		$this->runCommand(['fileId' => '11', '--at' => '754.205']);

		self::assertSame([42000, 1500, 754205], array_column($this->calls, 3));
	}

	public function testAtOutsideItsRangeIsInvalid(): void {
		self::assertSame(Command::INVALID, $this->runCommand(['fileId' => '11', '--at' => '86401']));
		self::assertSame(Command::INVALID, $this->runCommand(['fileId' => '11', '--at' => '1.2345']));
		self::assertSame(Command::INVALID, $this->runCommand(['fileId' => '11', '--at' => '-1']));
		self::assertSame(Command::INVALID, $this->runCommand(['fileId' => '11', '--at' => 'soon']));
		self::assertSame([], $this->calls);
	}

	public function testTheUserOptionChoosesWhoIsAsked(): void {
		$this->runCommand(['fileId' => '11', '--user' => 'bob']);

		self::assertSame('bob', $this->calls[0][1]);
	}

	public function testABackendErrorFailsWithItsCode(): void {
		$this->sampleAnswer = ['error' => 'gateway_denied'];

		self::assertSame(Command::FAILURE, $this->runCommand(['fileId' => '11']));
		self::assertStringContainsString('gateway_denied', $this->output->fetch());
	}

	public function testNoAnswerFails(): void {
		$this->sampleAnswer = null;

		self::assertSame(Command::FAILURE, $this->runCommand(['fileId' => '11']));
	}

	public function testRemoveCallsRemoveSampleAndReportsRemoved(): void {
		self::assertSame(Command::SUCCESS, $this->runCommand(['fileId' => '11', '--remove' => true]));
		self::assertStringContainsString('removed', $this->output->fetch());
		self::assertSame([['removeSample', 'alice', 11, null]], $this->calls);
	}

	public function testRemoveOfNothingIsASuccessWithAHint(): void {
		$this->removeAnswer = ['result' => 'not_found', 'mediaId' => null];

		self::assertSame(Command::SUCCESS, $this->runCommand(['fileId' => '11', '--remove' => true]));
		self::assertStringContainsString('not_found', $this->output->fetch());
	}

	public function testRemoveNeverRemovesARealTranscript(): void {
		$this->removeAnswer = ['result' => 'not_sample', 'mediaId' => 3];

		self::assertSame(Command::FAILURE, $this->runCommand(['fileId' => '11', '--remove' => true]));
		self::assertStringContainsString('not a test result', $this->output->fetch());
	}

	public function testRemoveTogetherWithAtIsInvalid(): void {
		self::assertSame(Command::INVALID, $this->runCommand(['fileId' => '11', '--remove' => true, '--at' => '5']));
		self::assertSame([], $this->calls);
	}

	public function testRemoveWithoutDebugModeFailsLikeCreating(): void {
		$this->debug = false;

		self::assertSame(Command::FAILURE, $this->runCommand(['fileId' => '11', '--remove' => true]));
		self::assertStringContainsString('Debug mode is off', $this->output->fetch());
		self::assertSame([], $this->calls);
	}
}
