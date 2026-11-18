<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Command;

use OCA\AudioVideoSearch\Service\ExAppService;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * occ audio_video_search:models [--verify]
 *
 * The state of every speech model of the container (plan 05-05, D-05-07),
 * one line each: "<id>: <state> (<doneBytes>/<totalBytes>)". Without the
 * option it reads the last known state of GET /resources; with --verify the
 * container checks every file against its sha256 now, the step after an
 * admin placed the files for the offline mode (occ itself cannot write into
 * the volume of the container).
 *
 * Codes and numbers only, never a path, a host or an address (T-05-12).
 * Exit 0 when no model is in a failed state, 1 when one is
 * (wrong_digest_download, wrong_digest_placed, offline_missing, failed), 2
 * when the container does not answer. Texts are English, as every occ text.
 */
class ModelsCommand extends Command {
	/** The states that mean a model is not usable and needs the admin. */
	public const FAILED_STATES = ['wrong_digest_download', 'wrong_digest_placed', 'offline_missing', 'failed'];

	public const EXIT_NO_BACKEND = 2;

	public function __construct(
		private ExAppService $exAppService,
	) {
		parent::__construct();
	}

	protected function configure(): void {
		$this
			->setName('audio_video_search:models')
			->setDescription('Show the state of the speech models of the backend. With --verify the backend checks every model file against its sha256 now.')
			->addOption('verify', null, InputOption::VALUE_NONE, 'Check every model file against its sha256 now');
	}

	protected function execute(InputInterface $input, OutputInterface $output): int {
		if ($input->getOption('verify') === true) {
			$models = $this->exAppService->verifyModels()['models'] ?? null;
		} else {
			$models = $this->exAppService->resources()['models'] ?? null;
		}
		if (!is_array($models)) {
			$output->writeln('<error>Backend not reachable.</error>');
			return self::EXIT_NO_BACKEND;
		}

		$failed = false;
		foreach ($models as $model) {
			$output->writeln(sprintf('%s: %s (%d/%d)', $model['id'], $model['state'], $model['doneBytes'], $model['totalBytes']));
			$failed = $failed || in_array($model['state'], self::FAILED_STATES, true);
		}

		return $failed ? Command::FAILURE : Command::SUCCESS;
	}
}
