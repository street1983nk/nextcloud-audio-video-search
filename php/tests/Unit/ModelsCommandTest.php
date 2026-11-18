<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Command\ModelsCommand;
use OCA\AudioVideoSearch\Service\ExAppService;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\ArrayInput;
use Symfony\Component\Console\Output\BufferedOutput;

/**
 * occ audio_video_search:models [--verify] (plan 05-05): one line per model,
 * codes and numbers only, exit 0, 1 or 2. Every expected line is written out
 * by hand.
 */
#[CoversClass(ModelsCommand::class)]
final class ModelsCommandTest extends TestCase {
	/** @return list<array<string, mixed>> */
	private static function modelList(string $turboState = 'present'): array {
		return [
			['id' => 'parakeet', 'state' => 'in_image', 'doneBytes' => 0, 'totalBytes' => 670000000, 'needFreeBytes' => null],
			['id' => 'silero', 'state' => 'in_image', 'doneBytes' => 0, 'totalBytes' => 640000, 'needFreeBytes' => null],
			['id' => 'whisper-turbo', 'state' => $turboState, 'doneBytes' => 1621665983, 'totalBytes' => 1621665983, 'needFreeBytes' => null],
			['id' => 'whisper-large-v3', 'state' => 'not_needed', 'doneBytes' => 0, 'totalBytes' => 3090835702, 'needFreeBytes' => null],
		];
	}

	/**
	 * @param array<string, mixed> $input
	 * @return array{int, string}
	 */
	private function invoke(ExAppService $exApp, array $input = []): array {
		$output = new BufferedOutput();
		$code = (new ModelsCommand($exApp))->run(new ArrayInput($input), $output);

		return [$code, str_replace("\r\n", "\n", $output->fetch())];
	}

	public function testEveryModelIsOneLineAndAllUsableIsExitZero(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->expects(self::once())->method('resources')->willReturn(['models' => self::modelList()]);
		$exApp->expects(self::never())->method('verifyModels');

		[$code, $text] = $this->invoke($exApp);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame(
			"parakeet: in_image (0/670000000)\n"
			. "silero: in_image (0/640000)\n"
			. "whisper-turbo: present (1621665983/1621665983)\n"
			. "whisper-large-v3: not_needed (0/3090835702)\n",
			$text,
		);
	}

	public function testVerifyAsksTheBackendToCheckNow(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->expects(self::never())->method('resources');
		$exApp->expects(self::once())->method('verifyModels')->willReturn(['models' => self::modelList()]);

		[$code] = $this->invoke($exApp, ['--verify' => true]);

		self::assertSame(Command::SUCCESS, $code);
	}

	/** @return array<string, array{string}> */
	public static function failedStates(): array {
		return [
			'wrong digest download' => ['wrong_digest_download'],
			'wrong digest placed' => ['wrong_digest_placed'],
			'offline missing' => ['offline_missing'],
			'failed' => ['failed'],
		];
	}

	#[DataProvider('failedStates')]
	public function testAFailedModelIsExitOne(string $state): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('verifyModels')->willReturn(['models' => self::modelList($state)]);

		[$code, $text] = $this->invoke($exApp, ['--verify' => true]);

		self::assertSame(Command::FAILURE, $code);
		self::assertStringContainsString("whisper-turbo: {$state} (1621665983/1621665983)\n", $text);
	}

	/** @return array<string, array{string}> */
	public static function waitingStates(): array {
		return [
			'waiting' => ['waiting'],
			'downloading' => ['downloading'],
			'verifying' => ['verifying'],
			'disk full' => ['disk_full'],
		];
	}

	#[DataProvider('waitingStates')]
	public function testAModelOnItsWayIsNoFailure(string $state): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('resources')->willReturn(['models' => self::modelList($state)]);

		[$code] = $this->invoke($exApp);

		self::assertSame(Command::SUCCESS, $code);
	}

	public function testASilentBackendIsExitTwo(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('resources')->willReturn(null);
		$exApp->method('verifyModels')->willReturn(null);

		[$code, $text] = $this->invoke($exApp);
		[$verifyCode] = $this->invoke($exApp, ['--verify' => true]);

		self::assertSame(2, $code);
		self::assertSame(2, $verifyCode);
		self::assertSame("Backend not reachable.\n", $text);
	}

	public function testTheOutputCarriesNoPathNoHostNoAddress(): void {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('resources')->willReturn(['models' => self::modelList()]);

		[, $text] = $this->invoke($exApp);

		// The only slash of a line is the one between the two numbers.
		foreach (explode("\n", rtrim($text, "\n")) as $line) {
			self::assertMatchesRegularExpression('/^[a-z0-9-]+: [a-z_]+ \(\d+\/\d+\)$/', $line);
		}
		self::assertStringNotContainsString('http', $text);
		self::assertStringNotContainsString('.', $text);
	}
}
