<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Command;

use OCA\AudioVideoSearch\Service\RescanService;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * occ audio_video_search:rescan --storage=<id> | --all
 *
 * Forces the rescan of external storages at once: changes made on the
 * external server itself, which Nextcloud does not see in the background
 * (DISC-04). The logic and the time budget are those of the timed job
 * (RescanService); only the 24 h cadence is left out.
 *
 * --storage=<id> scans exactly this capturable external storage and prints
 * the duration and the number of new and changed entries. --all scans every
 * capturable external storage, within the budget of one run.
 *
 * files_no_background_scan does not stop this command: it is an explicit act
 * of the admin, not a background scan.
 *
 * A storage that is unknown, not external or not capturable is answered with
 * one sentence and nothing else, so the command cannot be used to find out
 * what an id is. Texts are English, as every occ text of Nextcloud. Storage
 * ids, durations and counts only, never a path, a host or a share.
 *
 * Exit code: SUCCESS only when every storage asked for was scanned to its
 * end; INVALID for unusable options; FAILURE otherwise.
 */
class RescanCommand extends Command {
	private const NOT_CAPTURABLE = '<error>Storage not capturable.</error>';

	public function __construct(
		private RescanService $rescanService,
	) {
		parent::__construct();
	}

	protected function configure(): void {
		$this
			->setName('audio_video_search:rescan')
			->setDescription('Rescan external storages for changes made outside Nextcloud. Storage ids, durations and counts only.')
			->addOption('storage', null, InputOption::VALUE_REQUIRED, 'Rescan this capturable external storage (numeric storage id)')
			->addOption('all', null, InputOption::VALUE_NONE, 'Rescan every capturable external storage, at most ' . RescanService::BUDGET_SECONDS . ' seconds per run');
	}

	protected function execute(InputInterface $input, OutputInterface $output): int {
		$storage = $input->getOption('storage');
		$all = (bool)$input->getOption('all');
		if (($storage === null) !== $all) {
			$output->writeln('<error>Give either --storage or --all.</error>');
			return Command::INVALID;
		}

		if ($all) {
			return $this->rescanAll($output);
		}

		$storageId = self::storageIdOf($storage);
		if ($storageId === null) {
			$output->writeln('<error>--storage takes a positive whole number.</error>');
			return Command::INVALID;
		}

		$result = $this->rescanService->rescan($storageId, $this->rescanService->deadline());
		if ($result['status'] === RescanService::STATUS_NOT_CAPTURABLE) {
			$output->writeln(self::NOT_CAPTURABLE);
			return Command::FAILURE;
		}
		$output->writeln(self::line($result));

		return $result['status'] === RescanService::STATUS_SCANNED ? Command::SUCCESS : Command::FAILURE;
	}

	private function rescanAll(OutputInterface $output): int {
		$run = $this->rescanService->run(false);
		if ($run['results'] === [] && $run['waiting'] === 0) {
			$output->writeln('No capturable external storage.');
			return Command::SUCCESS;
		}

		$complete = $run['waiting'] === 0;
		foreach ($run['results'] as $result) {
			$output->writeln(self::line($result));
			if ($result['status'] !== RescanService::STATUS_SCANNED) {
				$complete = false;
			}
		}
		if ($run['waiting'] > 0) {
			$output->writeln(sprintf('Time budget spent, %d storages not started. Run the command again.', $run['waiting']));
		}

		return $complete ? Command::SUCCESS : Command::FAILURE;
	}

	/**
	 * One line per storage: id, what happened, duration and counts.
	 *
	 * @param array{storageId: int, status: string, seconds: int, new: int, changed: int} $result
	 */
	private static function line(array $result): string {
		return match ($result['status']) {
			RescanService::STATUS_SCANNED => sprintf(
				'Storage %d: rescanned in %d s, %d new and %d changed entries.',
				$result['storageId'],
				$result['seconds'],
				$result['new'],
				$result['changed'],
			),
			RescanService::STATUS_PARTIAL => sprintf(
				'Storage %d: time budget spent after %d s, %d new and %d changed entries so far. Run the command again.',
				$result['storageId'],
				$result['seconds'],
				$result['new'],
				$result['changed'],
			),
			RescanService::STATUS_NOT_CAPTURABLE => sprintf('Storage %d: not capturable.', $result['storageId']),
			default => sprintf('Storage %d: rescan failed after %d s.', $result['storageId'], $result['seconds']),
		};
	}

	/** A positive whole number as occ hands it over, or null. */
	private static function storageIdOf(mixed $value): ?int {
		if (!is_string($value) || preg_match('/^[1-9][0-9]{0,17}$/', $value) !== 1) {
			return null;
		}

		return (int)$value;
	}
}
