<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Command;

use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\RescanService;
use OCA\AudioVideoSearch\Service\StorageClassifier;
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
 * the PHP queue by kind, and how many first crawls are finished. Then the
 * external storages that are skipped (D-02-03): per mount configuration its
 * id, backend, authentication, reason and number of users, and the sentence
 * that stored credentials make them capturable. Last the background rescan
 * of external storages (plan 02-14): on, or "background rescan disabled by
 * configuration" when the admin set files_no_background_scan. Numbers, ids
 * and codes only, never a mount point, a host, a share or a path (T-02-44).
 * The admin page shows the same numbers from phase 9 on.
 *
 * --json: the fields of GET /coverage of the container (contents,
 * transcribed, files, byState, byStage, dueWork) plus queue {ok, open} and
 * crawl {finished, open}, skippedStorages [{mountId, backend, authKind,
 * reason, users}] and backgroundRescan ("on" or "disabled_by_config") of the
 * PHP app; the acceptance test reads it (ci/discovery/compare.sh). Texts are
 * English, as every occ text.
 */
class StatusCommand extends Command {
	public function __construct(
		private ExAppService $exAppService,
		private QueueService $queueService,
		private CrawlMapper $crawlMapper,
		private StorageClassifier $classifier,
		private RescanService $rescanService,
	) {
		parent::__construct();
	}

	protected function configure(): void {
		$this
			->setName('audio_video_search:status')
			->setDescription('Show how many contents are transcribed, with the work stock, the queue, the first crawls, the skipped external storages and the background rescan. Numbers only.')
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
		$skipped = $this->classifier->skipped();
		$backgroundRescan = $this->rescanService->backgroundRescan();

		if ($input->getOption('json')) {
			$output->writeln((string)json_encode($coverage + ['queue' => $queue, 'crawl' => $crawl, 'skippedStorages' => $skipped, 'backgroundRescan' => $backgroundRescan], JSON_UNESCAPED_SLASHES));
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
		if ($skipped === []) {
			$output->writeln('Skipped external storages: none');
		} else {
			$output->writeln(sprintf('Skipped external storages: %d', count($skipped)));
			foreach ($skipped as $entry) {
				$output->writeln(sprintf(
					'  mount %s: backend %s, authentication %s, reason %s, users %d',
					$entry['mountId'] === null ? 'unknown' : (string)$entry['mountId'],
					$entry['backend'],
					$entry['authKind'],
					$entry['reason'],
					$entry['users'],
				));
			}
			$output->writeln(StorageClassifier::HINT);
		}
		$output->writeln('Rescan of external storages: ' . (
			$backgroundRescan === RescanService::BACKGROUND_DISABLED ? 'background rescan disabled by configuration' : 'background rescan on'
		));

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
