<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Command;

use OCA\AudioVideoSearch\Service\ExAppService;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * occ audio_video_search:reconcile [--reprove]
 *
 * Starts one round of the periodic reconcile of the container at once
 * (DISC-04, plan 02-19) instead of waiting for its next tick: references of
 * vanished files are swept, every mount is walked against its slices, and what
 * differs goes back through the one pre-check of PHP. --reprove asks for a new
 * read proof of every grouped reference (SMB, SFTP) now instead of after
 * seven days (D-02-12).
 *
 * Prints the counters of the round, one per line. Texts are English, as every
 * occ text of Nextcloud; counters and a reason code only, never a path.
 *
 * Exit code: FAILURE when the backend does not answer, SUCCESS otherwise,
 * also for a round the container skipped (the reason is printed).
 */
class ReconcileCommand extends Command {
	public function __construct(
		private ExAppService $exAppService,
	) {
		parent::__construct();
	}

	protected function configure(): void {
		$this
			->setName('audio_video_search:reconcile')
			->setDescription('Run one round of the reconcile of the backend now. Counters only.')
			->addOption('reprove', null, InputOption::VALUE_NONE, 'Renew the read proof of every file on SMB and SFTP storages now');
	}

	protected function execute(InputInterface $input, OutputInterface $output): int {
		$counters = $this->exAppService->reconcileNow((bool)$input->getOption('reprove'));
		if ($counters === null) {
			$output->writeln('<error>Backend not reachable.</error>');
			return Command::FAILURE;
		}

		if ($counters['skippedReason'] !== null) {
			$output->writeln(sprintf('Reconcile skipped: %s', $counters['skippedReason']));
		}
		foreach ($counters as $key => $value) {
			if ($key !== 'skippedReason') {
				$output->writeln(sprintf('%s: %d', $key, $value));
			}
		}

		return Command::SUCCESS;
	}
}
