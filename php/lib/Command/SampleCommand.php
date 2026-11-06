<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Command;

use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\FileAccess;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\Files\File;
use OCP\Files\IRootFolder;
use OCP\IConfig;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputArgument;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * Seed or remove a test result for one real file, for the integration proof.
 *
 * The container reads the file through the content gateway like any real
 * job, checks its sha256 and publishes a short dummy transcript at the given
 * second at the lowest provenance level, so every real stage displaces it.
 * --remove takes the test result, its media entry and its index entries out
 * again; the file in Nextcloud stays untouched, and a real transcript is
 * refused with not_sample.
 *
 * Only with 'debug' => true in config.php: a production instance cannot be
 * given a test result by accident. The search shows one only while the admin
 * switch is on as well.
 *
 * Texts are English, as every occ text of Nextcloud. No line carries a path
 * or a file name; the file id is what the admin typed.
 */
class SampleCommand extends Command {
	public const DEFAULT_AT_SECONDS = 42;
	public const MAX_AT_SECONDS = 86400;

	private const NOT_FOUND = '<error>File not found or not readable.</error>';
	private const NO_ANSWER = '<error>The backend gave no usable answer.</error>';

	public function __construct(
		private ExAppService $exAppService,
		private IRootFolder $rootFolder,
		private ReaderContext $readerContext,
		private IConfig $config,
	) {
		parent::__construct();
	}

	protected function configure(): void {
		$this
			->setName('audio_video_search:sample')
			->setDescription('Create (or with --remove delete) a test result for one audio or video file. Debug mode only.')
			->addArgument('fileId', InputArgument::REQUIRED, 'The numeric id of the file')
			->addOption('at', null, InputOption::VALUE_REQUIRED, 'Second of the test hit, 0 to ' . self::MAX_AT_SECONDS . ', at most three decimals (default ' . self::DEFAULT_AT_SECONDS . ')')
			->addOption('user', null, InputOption::VALUE_REQUIRED, 'Ask as this user instead of the owner of the file')
			->addOption('remove', null, InputOption::VALUE_NONE, 'Remove the test result of this file with its index entries; the file itself stays');
	}

	protected function execute(InputInterface $input, OutputInterface $output): int {
		$fileId = self::fileIdOf($input->getArgument('fileId'));
		if ($fileId === null) {
			$output->writeln('<error>fileId takes a positive whole number.</error>');
			return Command::INVALID;
		}

		$remove = (bool)$input->getOption('remove');
		$at = $input->getOption('at');
		if ($remove && $at !== null) {
			$output->writeln('<error>--remove takes no --at.</error>');
			return Command::INVALID;
		}

		$atMs = $at === null ? self::DEFAULT_AT_SECONDS * 1000 : self::millisecondsOf($at);
		if ($atMs === null) {
			$output->writeln('<error>--at takes seconds from 0 to ' . self::MAX_AT_SECONDS . ' with at most three decimals.</error>');
			return Command::INVALID;
		}

		if (!$this->config->getSystemValueBool('debug', false)) {
			$output->writeln("<error>Debug mode is off. Set 'debug' => true in config.php to create a test result.</error>");
			return Command::FAILURE;
		}

		$uid = $this->readerOf($input->getOption('user'), $fileId);
		if ($uid === null) {
			$output->writeln(self::NOT_FOUND);
			return Command::FAILURE;
		}

		return $remove
			? $this->remove($output, $uid, $fileId)
			: $this->create($output, $uid, $fileId, $atMs);
	}

	private function create(OutputInterface $output, string $uid, int $fileId, int $atMs): int {
		$answer = $this->exAppService->sample($uid, $fileId, $atMs);
		if ($answer === null) {
			$output->writeln(self::NO_ANSWER);
			return Command::FAILURE;
		}

		if (isset($answer['error'])) {
			$output->writeln('<error>' . $answer['error'] . '</error>');
			return Command::FAILURE;
		}

		if ($answer['result'] === 'stale_rejected') {
			$output->writeln('stale_rejected: this file already has a better transcript, no test result was created.');
			return Command::SUCCESS;
		}

		$output->writeln(sprintf(
			'published media %d rev %s',
			$answer['mediaId'],
			$answer['indexRev'] === null ? 'none' : (string)$answer['indexRev'],
		));

		return Command::SUCCESS;
	}

	private function remove(OutputInterface $output, string $uid, int $fileId): int {
		$answer = $this->exAppService->removeSample($uid, $fileId);
		if ($answer === null) {
			$output->writeln(self::NO_ANSWER);
			return Command::FAILURE;
		}

		return match ($answer['result']) {
			'removed' => $this->said($output, sprintf('removed media %d', (int)$answer['mediaId']), Command::SUCCESS),
			'not_found' => $this->said($output, 'not_found: this file has no test result, nothing to remove.', Command::SUCCESS),
			default => $this->said($output, '<error>not a test result: a real transcript is never removed here.</error>', Command::FAILURE),
		};
	}

	private function said(OutputInterface $output, string $line, int $code): int {
		$output->writeln($line);

		return $code;
	}

	/**
	 * The user to ask as: the one named, or the owner of the file. Null when
	 * the file is unknown or not readable for that user; both read the same.
	 */
	private function readerOf(mixed $named, int $fileId): ?string {
		$uid = is_string($named) && $named !== '' ? $named : FileAccess::ownerOf($this->rootFolder, $fileId);
		if ($uid === null) {
			return null;
		}

		try {
			$file = $this->readerContext->actAs(
				$uid,
				fn (): ?File => FileAccess::readableFile($this->rootFolder->getUserFolder($uid), $fileId),
			);
		} catch (\Throwable) {
			return null;
		}

		return $file === null ? null : $uid;
	}

	private static function fileIdOf(mixed $raw): ?int {
		if (!is_string($raw) || preg_match('/^\d{1,18}$/D', $raw) !== 1) {
			return null;
		}

		$fileId = (int)$raw;

		return $fileId > 0 ? $fileId : null;
	}

	/** Seconds with at most three decimals as milliseconds, exactly. */
	private static function millisecondsOf(mixed $raw): ?int {
		if (!is_string($raw) || preg_match('/^(\d{1,5})(?:\.(\d{1,3}))?$/D', $raw, $match) !== 1) {
			return null;
		}

		$milliseconds = (int)$match[1] * 1000 + (int)str_pad($match[2] ?? '', 3, '0');

		return $milliseconds <= self::MAX_AT_SECONDS * 1000 ? $milliseconds : null;
	}
}
