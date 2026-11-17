<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Command;

use OCA\AudioVideoSearch\Service\ExAppService;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * occ audio_video_search:files [--state=...] [--all] [--json]
 *
 * The work stock of the container: every file id it knows with its content
 * id, storage id, state, stage and reason code (D-02-06, RESEARCH Pattern 4).
 * Ids and codes only, never a path or a name; an admin who wants to know
 * which file an id is runs occ info:file <id> himself.
 *
 * --json prints the answer of the container as it came (after the checks of
 * ExAppService); --all follows the pages until the last one and prints them
 * as one list. Texts are English, as every occ text of Nextcloud.
 */
class FilesCommand extends Command {
	/** Ten million files at 1000 per page; a container that never ends a list stops here. */
	public const MAX_PAGES = 10000;

	private const NOT_REACHABLE = '<error>Backend not reachable.</error>';

	public function __construct(
		private ExAppService $exAppService,
	) {
		parent::__construct();
	}

	protected function configure(): void {
		$this
			->setName('audio_video_search:files')
			->setDescription('List the work stock of the backend: file ids with state, stage and reason. Ids and codes only.')
			->addOption('state', null, InputOption::VALUE_REQUIRED, 'Only files in this state: ' . implode(', ', ExAppService::WORK_STATES))
			->addOption('all', null, InputOption::VALUE_NONE, 'Follow every page instead of printing the first ' . ExAppService::WORKSTOCK_MAX_LIMIT)
			->addOption('json', null, InputOption::VALUE_NONE, 'Print JSON');
	}

	protected function execute(InputInterface $input, OutputInterface $output): int {
		$state = $input->getOption('state');
		if ($state !== null && (!is_string($state) || !in_array($state, ExAppService::WORK_STATES, true))) {
			$output->writeln('<error>--state takes one of: ' . implode(', ', ExAppService::WORK_STATES) . '.</error>');
			return Command::INVALID;
		}

		$query = $state === null ? [] : ['state' => $state];
		$page = $this->exAppService->workstock($query);
		if ($page === null) {
			$output->writeln(self::NOT_REACHABLE);
			return Command::FAILURE;
		}

		$files = $page['files'];
		$next = $page['next'];
		if ($input->getOption('all')) {
			for ($pages = 1; $next !== null; $pages++) {
				if ($pages >= self::MAX_PAGES) {
					$output->writeln('<error>The backend did not end its list.</error>');
					return Command::FAILURE;
				}
				$after = $next;
				$page = $this->exAppService->workstock($query + ['after' => $after]);
				if ($page === null) {
					$output->writeln(self::NOT_REACHABLE);
					return Command::FAILURE;
				}
				// A page has to move forward; one that does not would repeat forever.
				if ($page['next'] !== null && $page['next'] <= $after) {
					$output->writeln('<error>The backend did not end its list.</error>');
					return Command::FAILURE;
				}
				array_push($files, ...$page['files']);
				$next = $page['next'];
			}
		}

		if ($input->getOption('json')) {
			$output->writeln((string)json_encode(['files' => $files, 'next' => $next], JSON_UNESCAPED_SLASHES));
			return Command::SUCCESS;
		}

		foreach ($files as $file) {
			$output->writeln(sprintf(
				'%d media %s storage %d %s %s%s',
				$file['fileId'],
				$file['mediaId'] === null ? '-' : (string)$file['mediaId'],
				$file['storageId'],
				$file['state'],
				$file['stage'],
				$file['reason'] === null ? '' : ' ' . $file['reason'],
			));
		}
		if ($next !== null) {
			$output->writeln('More files follow; use --all.');
		}

		return Command::SUCCESS;
	}
}
