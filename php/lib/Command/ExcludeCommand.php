<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Command;

use OCA\AudioVideoSearch\Service\ExclusionService;
use OCP\IGroupManager;
use OCP\IUserManager;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Formatter\OutputFormatter;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * occ audio_video_search:exclude --user=<uid> | --group=<gid> | --folder=<prefix> | --storage=<mount id> [--remove] [--list]
 *
 * The exclusions of the capture (DISC-03, D-02-05, D-02-08) and the switch
 * for external storages (DISC-02). What each of the four means is written at
 * ExclusionService. Several of the four options may be given at once; with
 * --remove each of them is taken out of its list instead of added. --list
 * prints the rules in force, after any change of the same call.
 *
 * The command writes the app config and nothing else. A rule holds from the
 * next event, crawl slice, hand over and download on; removing what was
 * captured before the rule existed is the work of plan 02-18.
 *
 * Texts are English, as every occ text of Nextcloud. An answer to a change
 * never repeats the value; only --list prints the rules, to the admin who
 * asked for them. Nothing here is logged.
 *
 * Exit code: SUCCESS when every change was made or was already in place;
 * INVALID for unusable options or values; FAILURE when a list is full, a
 * mount id names no configuration, the configurations of files_external
 * cannot be read, or the stored lists cannot be read.
 */
class ExcludeCommand extends Command {
	/** Option name => the list it writes. */
	private const OPTIONS = [
		'user' => ExclusionService::LIST_USERS,
		'group' => ExclusionService::LIST_GROUPS,
		'folder' => ExclusionService::LIST_FOLDERS,
		'storage' => ExclusionService::LIST_MOUNTS,
	];

	/** What a list is called in a sentence. */
	private const LABELS = [
		ExclusionService::LIST_USERS => 'excluded users',
		ExclusionService::LIST_GROUPS => 'excluded groups',
		ExclusionService::LIST_FOLDERS => 'excluded folders',
		ExclusionService::LIST_MOUNTS => 'excluded external storages (mount ids)',
	];

	public function __construct(
		private ExclusionService $exclusionService,
		private IUserManager $userManager,
		private IGroupManager $groupManager,
	) {
		parent::__construct();
	}

	protected function configure(): void {
		$this
			->setName('audio_video_search:exclude')
			->setDescription('Exclude users, groups, folders or external storages from the capture, or list the exclusions.')
			->addOption('user', null, InputOption::VALUE_REQUIRED, 'A user id: the storages of this user are not captured and the user gets no hits')
			->addOption('group', null, InputOption::VALUE_REQUIRED, 'A group id: the same for every member of the group')
			->addOption('folder', null, InputOption::VALUE_REQUIRED, 'A folder relative to the root of each mount, for example "private" for that folder in every home')
			->addOption('storage', null, InputOption::VALUE_REQUIRED, 'The mount id of an external storage configuration (occ files_external:list)')
			->addOption('remove', null, InputOption::VALUE_NONE, 'Take the given entries out of their lists instead of adding them')
			->addOption('list', null, InputOption::VALUE_NONE, 'Print the exclusions in force');
	}

	protected function execute(InputInterface $input, OutputInterface $output): int {
		$changes = [];
		foreach (self::OPTIONS as $option => $list) {
			$value = $input->getOption($option);
			if ($value === null) {
				continue;
			}
			if (!is_string($value)) {
				$output->writeln(sprintf('<error>--%s takes one value.</error>', $option));
				return Command::INVALID;
			}
			$changes[] = [$option, $list, $value];
		}
		$remove = (bool)$input->getOption('remove');
		$show = (bool)$input->getOption('list');
		if ($changes === [] && ($remove || !$show)) {
			$output->writeln('<error>Give --user, --group, --folder or --storage, or --list.</error>');
			return Command::INVALID;
		}

		$code = Command::SUCCESS;
		foreach ($changes as [$option, $list, $value]) {
			$result = $remove
				? $this->exclusionService->remove($list, $value)
				: $this->exclusionService->add($list, $value);
			[$sentence, $outcome] = self::answer($option, $list, $result);
			$output->writeln($sentence);
			if ($result === ExclusionService::RESULT_ADDED) {
				$this->noteUnknown($list, $value, $output);
			}
			$code = max($code, $outcome);
		}

		if ($show) {
			$code = max($code, $this->show($output));
		}

		return $code;
	}

	/**
	 * A rule for a user or a group nobody knows excludes nobody; a typing
	 * error would stay unnoticed without this note. The rule is kept: a user
	 * may be excluded before the account exists (D-02-05).
	 */
	private function noteUnknown(string $list, string $value, OutputInterface $output): void {
		if ($list === ExclusionService::LIST_USERS && !$this->userManager->userExists($value)) {
			$output->writeln('<comment>Note: no user with this id is known yet. The rule applies once there is one.</comment>');
		}
		if ($list === ExclusionService::LIST_GROUPS && !$this->groupManager->groupExists($value)) {
			$output->writeln('<comment>Note: no group with this id is known yet. The rule applies once there is one.</comment>');
		}
	}

	/**
	 * The lists in force, one entry per line. A list that cannot be read is
	 * said so, with the key to repair, and is a failure.
	 */
	private function show(OutputInterface $output): int {
		$code = Command::SUCCESS;
		foreach (self::LABELS as $list => $label) {
			$entries = $this->exclusionService->entries($list);
			if ($entries === null) {
				$output->writeln(sprintf('<error>%s: %s</error>', ucfirst($label), self::unreadable($list)));
				$code = Command::FAILURE;
				continue;
			}
			$output->writeln(sprintf('%s (%d):', ucfirst($label), count($entries)));
			foreach ($entries as $entry) {
				$output->writeln('  ' . OutputFormatter::escape($entry));
			}
		}

		return $code;
	}

	/**
	 * The sentence and the exit code for one result of the service.
	 *
	 * @return array{0: string, 1: int}
	 */
	private static function answer(string $option, string $list, string $result): array {
		$label = self::LABELS[$list];

		return match ($result) {
			ExclusionService::RESULT_ADDED => [sprintf('Added to the %s.', $label), Command::SUCCESS],
			ExclusionService::RESULT_REMOVED => [sprintf('Removed from the %s.', $label), Command::SUCCESS],
			ExclusionService::ERROR_DUPLICATE => [sprintf('Already in the %s, nothing changed.', $label), Command::SUCCESS],
			ExclusionService::RESULT_ABSENT => [sprintf('Not in the %s, nothing changed.', $label), Command::SUCCESS],
			ExclusionService::ERROR_EMPTY => [sprintf('<error>--%s needs a value.</error>', $option), Command::INVALID],
			ExclusionService::ERROR_TOO_LONG => [
				sprintf('<error>--%s takes at most %d bytes.</error>', $option, ExclusionService::MAX_ENTRY_LENGTH),
				Command::INVALID,
			],
			ExclusionService::ERROR_TRAVERSAL => ['<error>A folder may not hold "." or ".." as a part of its path.</error>', Command::INVALID],
			ExclusionService::ERROR_TOO_MANY => [
				sprintf('<error>The %s are full (%d entries).</error>', $label, ExclusionService::MAX_ENTRIES),
				Command::FAILURE,
			],
			ExclusionService::ERROR_UNKNOWN_MOUNT => ['<error>No external storage configuration has this mount id.</error>', Command::FAILURE],
			ExclusionService::ERROR_MOUNTS_UNREADABLE => [
				'<error>The external storage configurations cannot be read, so the mount id could not be checked and nothing changed. Is the app files_external enabled?</error>',
				Command::FAILURE,
			],
			ExclusionService::ERROR_UNREADABLE => [sprintf('<error>%s</error>', self::unreadable($list)), Command::FAILURE],
			default => [
				$list === ExclusionService::LIST_MOUNTS
					? '<error>--storage takes the mount id of an external storage configuration, a positive whole number.</error>'
					: sprintf('<error>--%s holds characters that cannot be used.</error>', $option),
				Command::INVALID,
			],
		};
	}

	private static function unreadable(string $list): string {
		return sprintf(
			'The stored list cannot be read, so everything is excluded until it is repaired. Correct or delete the app config key %s.',
			$list,
		);
	}
}
