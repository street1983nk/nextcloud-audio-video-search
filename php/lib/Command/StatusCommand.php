<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Command;

use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\QueueService;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * occ audio_video_search:status [--json]
 *
 * "X of Y contents transcribed (N files)" (D-02-06): both numbers count
 * contents by content key, the file count stands beside them. Below them the
 * parts: due work and the work stock by state and by stage in the container,
 * the PHP queue by kind, and how many first crawls are finished. Numbers and
 * codes only. The admin page shows the same numbers from phase 9 on.
 *
 * --json: the fields of GET /coverage of the container (contents,
 * transcribed, files, byState, byStage, dueWork) plus queue {ok, open} and
 * crawl {finished, open} of the PHP app; the acceptance test reads it
 * (ci/discovery/compare.sh). Texts are English, as every occ text.
 */
class StatusCommand extends Command {
	public function __construct(
		private ExAppService $exAppService,
		private QueueService $queueService,
		private CrawlMapper $crawlMapper,
	) {
		parent::__construct();
	}

	protected function configure(): void {
		$this
			->setName('audio_video_search:status')
			->setDescription('Show how many contents are transcribed, with the work stock, the queue and the first crawls. Numbers only.')
			->addOption('json', null, InputOption::VALUE_NONE, 'Print JSON');
	}

	protected function execute(InputInterface $input, OutputInterface $output): int {
		$coverage = $this->exAppService->coverage();
		if ($coverage === null) {
			$output->writeln('<error>Backend not reachable.</error>');
			return Command::FAILURE;
		}

		$queue = $this->queueService->stats();
		$crawl = $this->crawlMapper->progress();

		if ($input->getOption('json')) {
			$output->writeln((string)json_encode($coverage + ['queue' => $queue, 'crawl' => $crawl], JSON_UNESCAPED_SLASHES));
			return Command::SUCCESS;
		}

		$output->writeln(sprintf(
			'%d of %d contents transcribed (%d files)',
			$coverage['transcribed'],
			$coverage['contents'],
			$coverage['files'],
		));
		$output->writeln(sprintf('Due work: %d', $coverage['dueWork']));
		$output->writeln('By state: ' . self::listed($coverage['byState']));
		$output->writeln('By stage: ' . self::listed($coverage['byStage']));
		$output->writeln(($queue['ok'] ? 'Queue: ' : 'Queue (could not be read): ') . self::listed($queue['open']));
		$output->writeln(sprintf('First crawls: %d finished, %d open', $crawl['finished'], $crawl['open']));

		return Command::SUCCESS;
	}

	/** @param array<string, int> $counts */
	private static function listed(array $counts): string {
		$parts = [];
		foreach ($counts as $code => $count) {
			$parts[] = $code . ' ' . $count;
		}

		return implode(', ', $parts);
	}
}
