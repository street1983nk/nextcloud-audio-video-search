<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

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
 * occ audio_video_search:status, the line "Preview:" (plan 03-14, D-03-13):
 * the preview jobs counted by reason or state, codes and numbers only, in the
 * fixed order in which ExAppService::coverage hands them over; --json carries
 * byPreview. Every expected line is written out by hand.
 */
#[CoversClass(StatusCommand::class)]
final class StatusCommandTest extends TestCase {
	private const PREVIEW_LINE = 'Preview: queued 2, running 0, waiting 0, complete 3, skipped 0, too_long 0, no_audio 0, damaged 0, '
		. 'protected 0, format_unsupported 0, no_speech 1, unsupported_language 0, disk_full 0, engine_failed 0';

	/** @return array<string, int> in the order ExAppService::coverage returns (its closed list) */
	private static function byPreview(): array {
		return [
			'queued' => 2, 'running' => 0, 'waiting' => 0, 'complete' => 3, 'skipped' => 0,
			'too_long' => 0, 'no_audio' => 0, 'damaged' => 0, 'protected' => 0, 'format_unsupported' => 0,
			'no_speech' => 1, 'unsupported_language' => 0, 'disk_full' => 0, 'engine_failed' => 0,
		];
	}

	/** @return array<string, mixed> */
	private static function coverage(): array {
		return [
			'contents' => 6,
			'transcribed' => 3,
			'files' => 7,
			'byState' => ['active' => 7, 'unreadable' => 0, 'vanished' => 0, 'trashed' => 0],
			'byStage' => ['pending' => 0, 'probing' => 0, 'fetching' => 0, 'keyed' => 7, 'failed' => 0],
			'dueWork' => 0,
			'byPreview' => self::byPreview(),
		];
	}

	/** @param array<string, mixed> $coverage */
	private function statusCommand(array $coverage): StatusCommand {
		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('coverage')->willReturn($coverage);
		$queue = $this->createMock(QueueService::class);
		$queue->method('stats')->willReturn(['ok' => true, 'open' => ['exclude_storage' => 0, 'exclude' => 0, 'delete' => 0, 'trash' => 0, 'restore' => 0, 'content' => 0, 'metadata' => 0]]);
		$crawl = $this->createMock(CrawlMapper::class);
		$crawl->method('progress')->willReturn(['finished' => 1, 'open' => 0]);
		$classifier = $this->createMock(StorageClassifier::class);
		$classifier->method('skipped')->willReturn([]);
		$rescan = $this->createMock(RescanService::class);
		$rescan->method('backgroundRescan')->willReturn(RescanService::BACKGROUND_ON);

		return new StatusCommand($exApp, $queue, $crawl, $classifier, $rescan);
	}

	/**
	 * @param array<string, mixed> $coverage
	 * @param array<string, mixed> $input
	 */
	private function statusText(array $coverage, array $input = []): string {
		$output = new BufferedOutput();
		$code = $this->statusCommand($coverage)->run(new ArrayInput($input), $output);
		self::assertSame(Command::SUCCESS, $code);

		return $output->fetch();
	}

	/** @return list<string> */
	private static function lines(string $text): array {
		return explode("\n", rtrim(str_replace("\r\n", "\n", $text), "\n"));
	}

	public function testTheTextNamesThePreviewJobsByReasonOrStateRightAfterTheStages(): void {
		$lines = self::lines($this->statusText(self::coverage()));

		$at = array_search(self::PREVIEW_LINE, $lines, true);
		self::assertIsInt($at);
		self::assertSame('By stage: pending 0, probing 0, fetching 0, keyed 7, failed 0', $lines[$at - 1]);
		self::assertSame('Queue: exclude_storage 0, exclude 0, delete 0, trash 0, restore 0, content 0, metadata 0', $lines[$at + 1]);
		self::assertCount(1, array_filter($lines, static fn (string $line): bool => str_starts_with($line, 'Preview:')));
	}

	public function testTheOrderOfThePreviewLineIsTheSameOnEveryRun(): void {
		$first = $this->statusText(self::coverage());
		$second = $this->statusText(self::coverage());

		self::assertSame($first, $second);
		self::assertStringContainsString(self::PREVIEW_LINE . "\n", str_replace("\r\n", "\n", $first));
	}

	public function testThePreviewLineHoldsOnlyCodesAndNumbers(): void {
		$text = $this->statusText(self::coverage());
		$line = current(array_filter(self::lines($text), static fn (string $l): bool => str_starts_with($l, 'Preview:')));

		self::assertIsString($line);
		self::assertMatchesRegularExpression('/^Preview: [a-z_]+ \d+(, [a-z_]+ \d+)*$/', $line);
		self::assertStringNotContainsString('/', $text);
	}

	public function testJsonCarriesByPreviewBesideTheOtherCounts(): void {
		$printed = json_decode($this->statusText(self::coverage(), ['--json' => true]), true);

		self::assertIsArray($printed);
		self::assertSame(
			['contents', 'transcribed', 'files', 'byState', 'byStage', 'dueWork', 'byPreview', 'queue', 'crawl', 'skippedStorages', 'backgroundRescan'],
			array_keys($printed),
		);
		self::assertSame(self::byPreview(), $printed['byPreview']);
		self::assertStringNotContainsString('Preview:', $this->statusText(self::coverage(), ['--json' => true]));
	}
}
