<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\Command\FilesCommand;
use OCA\AudioVideoSearch\Command\StatusCommand;
use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\RescanService;
use OCA\AudioVideoSearch\Service\StorageClassifier;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\TestCase;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\ArrayInput;
use Symfony\Component\Console\Output\BufferedOutput;

/**
 * occ audio_video_search:files and :status: what the admin and the
 * acceptance test (ci/discovery/compare.sh) read. Ids, codes and numbers
 * only; a backend that does not answer is a failure with one sentence.
 */
#[CoversClass(FilesCommand::class)]
#[CoversClass(StatusCommand::class)]
final class FilesCommandTest extends TestCase {
	/** @var list<array<string, mixed>> the queries the command sent */
	private array $queries = [];

	/** @param array<int, array{files: list<array<string, mixed>>, next: ?int}|null> $pages keyed by after */
	private function filesCommand(array $pages): FilesCommand {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('workstock')->willReturnCallback(function (array $query) use ($pages): ?array {
			$this->queries[] = $query;

			return $pages[$query['after'] ?? 0] ?? null;
		});

		return new FilesCommand($exApp);
	}

	/** @return array<string, mixed> */
	private static function entry(int $fileId, string $state = 'active', ?string $reason = null): array {
		return ['fileId' => $fileId, 'mediaId' => $state === 'active' ? 3 : null, 'storageId' => 2, 'state' => $state, 'stage' => $state === 'active' ? 'keyed' : 'failed', 'reason' => $reason];
	}

	/** @param array<string, mixed> $input */
	private static function runCommand(Command $command, array $input, BufferedOutput $output): int {
		return $command->run(new ArrayInput($input), $output);
	}

	public function testJsonPrintsTheAnswerOfTheContainer(): void {
		$output = new BufferedOutput();
		$page = ['files' => [self::entry(11)], 'next' => null];

		$code = self::runCommand($this->filesCommand([0 => $page]), ['--json' => true], $output);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame($page, json_decode($output->fetch(), true));
		self::assertSame([[]], $this->queries);
	}

	public function testAllFollowsNextUntilTheLastPage(): void {
		$output = new BufferedOutput();
		$pages = [
			0 => ['files' => [self::entry(11), self::entry(12)], 'next' => 12],
			12 => ['files' => [self::entry(20, 'unreadable', 'read_denied')], 'next' => 20],
			20 => ['files' => [], 'next' => null],
		];

		$code = self::runCommand($this->filesCommand($pages), ['--json' => true, '--all' => true, '--state' => 'active'], $output);

		self::assertSame(Command::SUCCESS, $code);
		$printed = json_decode($output->fetch(), true);
		self::assertSame([11, 12, 20], array_column($printed['files'], 'fileId'));
		self::assertNull($printed['next']);
		self::assertSame(
			[['state' => 'active'], ['state' => 'active', 'after' => 12], ['state' => 'active', 'after' => 20]],
			$this->queries,
		);
	}

	public function testWithoutAllOnlyTheFirstPageIsAskedAndTheRestIsAnnounced(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->filesCommand([0 => ['files' => [self::entry(11)], 'next' => 11]]), [], $output);

		self::assertSame(Command::SUCCESS, $code);
		$text = $output->fetch();
		self::assertStringContainsString('11 media 3 storage 2 active keyed', $text);
		self::assertStringContainsString('More files follow; use --all.', $text);
		self::assertCount(1, $this->queries);
	}

	public function testAStateOutsideTheListIsInvalidWithoutACall(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->filesCommand([]), ['--state' => 'deleted'], $output);

		self::assertSame(Command::INVALID, $code);
		self::assertSame([], $this->queries);
	}

	public function testAnUnreachableBackendIsAFailure(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->filesCommand([]), ['--json' => true], $output);

		self::assertSame(Command::FAILURE, $code);
		self::assertStringContainsString('Backend not reachable.', $output->fetch());
	}

	public function testAPageThatFailsHalfwayIsAFailureAndNoHalfList(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->filesCommand([0 => ['files' => [self::entry(11)], 'next' => 11]]), ['--json' => true, '--all' => true], $output);

		self::assertSame(Command::FAILURE, $code);
		self::assertStringNotContainsString('fileId', $output->fetch());
	}

	public function testAListThatDoesNotMoveForwardStops(): void {
		$output = new BufferedOutput();
		$pages = [0 => ['files' => [self::entry(11)], 'next' => 11], 11 => ['files' => [self::entry(11)], 'next' => 11]];

		$code = self::runCommand($this->filesCommand($pages), ['--all' => true], $output);

		self::assertSame(Command::FAILURE, $code);
		self::assertStringContainsString('did not end its list', $output->fetch());
	}

	// -- status -------------------------------------------------------------------

	/** @return array<string, mixed> */
	private static function coverage(): array {
		return [
			'contents' => 4,
			'transcribed' => 1,
			'files' => 6,
			'byState' => ['active' => 6, 'unreadable' => 1, 'vanished' => 0, 'trashed' => 0],
			'byStage' => ['pending' => 3, 'probing' => 0, 'fetching' => 0, 'keyed' => 3, 'failed' => 1],
			'dueWork' => 3,
		];
	}

	/**
	 * @param array<string, mixed>|null $coverage
	 * @param list<array{mountId: ?int, backend: string, authKind: string, reason: string, users: int}> $skipped
	 */
	private function statusCommand(?array $coverage, bool $queueOk = true, array $skipped = [], string $backgroundRescan = RescanService::BACKGROUND_ON): StatusCommand {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('coverage')->willReturn($coverage);
		$queue = $this->createMock(QueueService::class);
		$queue->method('stats')->willReturn(['ok' => $queueOk, 'open' => ['exclude_storage' => 0, 'exclude' => 0, 'delete' => 0, 'trash' => 0, 'restore' => 0, 'content' => 2, 'metadata' => 0]]);
		$crawl = $this->createMock(CrawlMapper::class);
		$crawl->method('progress')->willReturn(['finished' => 3, 'open' => 1]);

		$classifier = $this->createMock(StorageClassifier::class);
		$classifier->method('skipped')->willReturn($skipped);

		$rescan = $this->createMock(RescanService::class);
		$rescan->method('backgroundRescan')->willReturn($backgroundRescan);

		return new StatusCommand($exApp, $queue, $crawl, $classifier, $rescan);
	}

	public function testStatusJsonCarriesTheCoverageTheQueueAndTheCrawls(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->statusCommand(self::coverage()), ['--json' => true], $output);

		self::assertSame(Command::SUCCESS, $code);
		$printed = json_decode($output->fetch(), true);
		self::assertSame(
			['contents', 'transcribed', 'files', 'byState', 'byStage', 'dueWork', 'queue', 'crawl', 'skippedStorages', 'backgroundRescan'],
			array_keys($printed),
		);
		self::assertSame(3, $printed['dueWork']);
		self::assertTrue($printed['queue']['ok']);
		self::assertSame(2, $printed['queue']['open']['content']);
		self::assertSame(['finished' => 3, 'open' => 1], $printed['crawl']);
		self::assertSame([], $printed['skippedStorages']);
		self::assertSame('on', $printed['backgroundRescan']);
	}

	public function testStatusJsonSaysWhenTheBackgroundRescanIsDisabledByConfiguration(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->statusCommand(self::coverage(), true, [], RescanService::BACKGROUND_DISABLED), ['--json' => true], $output);

		self::assertSame(Command::SUCCESS, $code);
		self::assertSame('disabled_by_config', json_decode($output->fetch(), true)['backgroundRescan']);
	}

	public function testStatusTextSaysWhetherTheBackgroundRescanIsOnOrDisabledByConfiguration(): void {
		$on = new BufferedOutput();
		$off = new BufferedOutput();

		self::runCommand($this->statusCommand(self::coverage()), [], $on);
		self::runCommand($this->statusCommand(self::coverage(), true, [], RescanService::BACKGROUND_DISABLED), [], $off);

		$text = $on->fetch();
		self::assertStringContainsString('Rescan of external storages: background rescan on', $text);
		self::assertStringNotContainsString('disabled', $text);
		self::assertStringContainsString('Rescan of external storages: background rescan disabled by configuration', $off->fetch());
	}

	/** @return list<array{mountId: ?int, backend: string, authKind: string, reason: string, users: int}> */
	private static function skipped(): array {
		return [
			['mountId' => 2, 'backend' => 'smb', 'authKind' => 'password::sessioncredentials', 'reason' => 'session_credentials', 'users' => 1],
			['mountId' => 4, 'backend' => 'sftp', 'authKind' => 'password::logincredentials', 'reason' => 'credentials_missing', 'users' => 3],
		];
	}

	public function testStatusJsonListsTheSkippedStoragesAsTheAcceptanceTestReadsThem(): void {
		$output = new BufferedOutput();

		self::runCommand($this->statusCommand(self::coverage(), true, self::skipped()), ['--json' => true], $output);

		$printed = json_decode($output->fetch(), true);
		self::assertSame(self::skipped(), $printed['skippedStorages']);
	}

	public function testStatusTextNamesEachSkippedStorageWithoutAPathAndTheHint(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->statusCommand(self::coverage(), true, self::skipped()), [], $output);

		self::assertSame(Command::SUCCESS, $code);
		$text = $output->fetch();
		self::assertStringContainsString('Skipped external storages: 2', $text);
		self::assertStringContainsString('mount 2: backend smb, authentication password::sessioncredentials, reason session_credentials, users 1', $text);
		self::assertStringContainsString('mount 4: backend sftp, authentication password::logincredentials, reason credentials_missing, users 3', $text);
		self::assertStringContainsString('Stored credentials (Log-in credentials, save in database) make these storages capturable.', $text);
	}

	public function testStatusTextWithoutSkippedStoragesSaysNoneAndNoHint(): void {
		$output = new BufferedOutput();

		self::runCommand($this->statusCommand(self::coverage()), [], $output);

		$text = $output->fetch();
		self::assertStringContainsString('Skipped external storages: none', $text);
		self::assertStringNotContainsString('Stored credentials', $text);
	}

	public function testStatusTextSaysXOfYContentsWithTheFiles(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->statusCommand(self::coverage(), false), [], $output);

		self::assertSame(Command::SUCCESS, $code);
		$text = $output->fetch();
		self::assertStringContainsString('1 of 4 contents transcribed (6 files)', $text);
		self::assertStringContainsString('Due work: 3', $text);
		self::assertStringContainsString('By state: active 6, unreadable 1', $text);
		self::assertStringContainsString('By stage: pending 3', $text);
		self::assertStringContainsString('Queue (could not be read): ', $text);
		self::assertStringContainsString('First crawls: 3 finished, 1 open', $text);
	}

	public function testStatusOfAnUnreachableBackendIsAFailure(): void {
		$output = new BufferedOutput();

		$code = self::runCommand($this->statusCommand(null), ['--json' => true], $output);

		self::assertSame(Command::FAILURE, $code);
		self::assertSame("Backend not reachable.\n", $output->fetch());
	}
}
