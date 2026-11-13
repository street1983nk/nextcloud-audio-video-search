<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\BackgroundJobs\ExternalRescanJob;
use OCA\AudioVideoSearch\BackgroundJobs\SchedulerJob;
use OCA\AudioVideoSearch\Service\JobRegistry;
use OCP\BackgroundJob\IJobList;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The app puts its own background jobs back (plan 02-17b).
 *
 * A cron.php that began before the app was enabled cannot build the jobs of
 * the app and JobList::buildJob (stable33) removes their rows; without the
 * SchedulerJob there is never a first crawl. JobRegistry adds what is
 * missing, the same row the enabling of the app adds (class, argument null).
 */
#[CoversClass(JobRegistry::class)]
final class JobRegistryTest extends TestCase {
	private IJobList&MockObject $jobList;
	private LoggerInterface&MockObject $logger;

	protected function setUp(): void {
		parent::setUp();

		$this->jobList = $this->createMock(IJobList::class);
		$this->logger = $this->createMock(LoggerInterface::class);
	}

	/** @param list<string> $present */
	private function present(array $present): void {
		$this->jobList->method('has')->willReturnCallback(
			static fn (string $job, mixed $argument): bool => $argument === null && in_array($job, $present, true),
		);
	}

	private function registry(): JobRegistry {
		return new JobRegistry($this->jobList, $this->logger);
	}

	public function testAMissingSchedulerJobIsPutBackAndNothingElse(): void {
		$this->present([ExternalRescanJob::class]);
		$this->jobList->expects(self::once())->method('add')->with(SchedulerJob::class, null);
		$this->logger->expects(self::once())->method('warning')->with(
			self::anything(),
			['job' => SchedulerJob::class],
		);

		self::assertSame([SchedulerJob::class], $this->registry()->ensure());
	}

	public function testBothMissingJobsArePutBack(): void {
		$this->present([]);
		$added = [];
		$this->jobList->expects(self::exactly(2))->method('add')->willReturnCallback(
			static function (string $job, mixed $argument) use (&$added): void {
				$added[] = [$job, $argument];
			},
		);
		$this->logger->expects(self::exactly(2))->method('warning');

		self::assertSame([SchedulerJob::class, ExternalRescanJob::class], $this->registry()->ensure());
		self::assertSame([[SchedulerJob::class, null], [ExternalRescanJob::class, null]], $added);
	}

	public function testJobsThatAreThereAreNeverAddedTwice(): void {
		$this->present([SchedulerJob::class, ExternalRescanJob::class]);
		$this->jobList->expects(self::never())->method('add');
		$this->logger->expects(self::never())->method('warning');

		self::assertSame([], $this->registry()->ensure());
	}

	public function testAFailingLookupIsLoggedWithTheClassOnly(): void {
		$this->jobList->method('has')->willThrowException(new \RuntimeException('/var/www/data secret'));
		$this->jobList->expects(self::never())->method('add');
		$this->logger->expects(self::once())->method('warning')->with(
			self::anything(),
			['class' => \RuntimeException::class],
		);

		self::assertSame([], $this->registry()->ensure());
	}

	public function testAFailingAddIsLoggedWithTheClassOnly(): void {
		$this->present([]);
		$this->jobList->method('add')->willThrowException(new \RuntimeException('database gone'));
		$this->logger->expects(self::once())->method('warning')->with(
			self::anything(),
			['class' => \RuntimeException::class],
		);

		self::assertSame([], $this->registry()->ensure());
	}

	public function testTheListIsTheOneOfInfoXml(): void {
		// Read as a string: lib/base.php switches the external entity loader
		// off, so simplexml_load_file cannot open a file inside the suite.
		$xml = file_get_contents(dirname(__DIR__, 2) . '/appinfo/info.xml');
		self::assertIsString($xml);
		$info = simplexml_load_string($xml);
		self::assertNotFalse($info);
		$jobs = [];
		foreach ($info->{'background-jobs'}->job as $job) {
			$jobs[] = trim((string)$job);
		}

		self::assertSame($jobs, JobRegistry::JOBS);
	}
}
