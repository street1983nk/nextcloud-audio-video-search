<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Search;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\FileAccess;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IMimeTypeDetector;
use OCP\Files\IRootFolder;
use OCP\IAppConfig;
use OCP\IConfig;
use OCP\IL10N;
use OCP\IURLGenerator;
use OCP\IUser;
use OCP\Search\IFilter;
use OCP\Search\IFilteringProvider;
use OCP\Search\ISearchQuery;
use OCP\Search\SearchResult;
use OCP\Search\SearchResultEntry;
use Psr\Log\LoggerInterface;

/**
 * The result group "Audio and video" of the unified search.
 *
 * Two steps, and the order is the security of it. The container proposes
 * hits (file id, time, excerpt); every proposal is then rechecked with
 * FileAccess::readableFile in the folder of the searching user, at the time
 * of the search. A hit for a file the user cannot read never appears, and
 * title and path of an entry come out of the confirmed node, never out of the
 * answer of the container.
 *
 * Each hit links to the playback page at its time mark. Two marks in one file
 * are two entries with two links, so the web client does not fold them.
 *
 * A test result (occ seed) is only shown with 'debug' => true in config.php
 * AND the switch sample_visible on, decided here on the server, and it carries
 * the word "Test result" in its subline so it never looks like a real hit.
 *
 * An excluded user gets no hits at all (D-02-08, T-02-58): the group is empty
 * before the container is asked anything, and the answer is the one of a
 * search that found nothing. Every proposal is also asked about with
 * ExclusionService::isExcludedFile under the rules read at the start of this
 * search, so a storage or a folder excluded after the first crawl gives no
 * hit from the moment the rule is written (owner 14.11.2026).
 *
 * Nothing a user typed or owns is logged: the reasons for an empty group are
 * debug lines without term, without path and without the user.
 */
final class Provider implements IFilteringProvider {
	/** The wall clock of the whole result group, as in Findling. */
	private const BUDGET_SECONDS = 2.5;

	/** How many proposals the container is asked for. */
	private const SEARCH_LIMIT = 25;

	/** The term ceiling of the contract, in characters. */
	private const MAX_TERM_LENGTH = 200;

	/** The excerpt ceiling of the subline (UI-SPEC), ellipsis included. */
	public const MAX_EXCERPT_LENGTH = 120;

	/** The switch of the admin page that lets a test result into the search. */
	public const KEY_SAMPLE_VISIBLE = 'sample_visible';

	private const SEPARATOR = ' · ';
	private const ELLIPSIS = '…';

	public function __construct(
		private IL10N $l10n,
		private IURLGenerator $urlGenerator,
		private ExAppService $exAppService,
		private IRootFolder $rootFolder,
		private ReaderContext $readerContext,
		private IConfig $config,
		private IAppConfig $appConfig,
		private IMimeTypeDetector $mimeTypeDetector,
		private LoggerInterface $logger,
		private ExclusionService $exclusions,
	) {
	}

	#[\Override]
	public function getId(): string {
		return 'audio_video_search';
	}

	#[\Override]
	public function getName(): string {
		return $this->l10n->t('Audio and video');
	}

	/**
	 * Ahead of most groups in the Files app, behind the core groups elsewhere.
	 */
	#[\Override]
	public function getOrder(string $route, array $routeParameters): ?int {
		return str_starts_with($route, 'files.') ? -5 : 25;
	}

	/**
	 * Only the term in phase 1. A provider that claimed date or title filters
	 * it does not apply would show wrong hits; one that names only the term is
	 * hidden by the web client while such a filter is active, which is honest.
	 */
	#[\Override]
	public function getSupportedFilters(): array {
		return [IFilter::BUILTIN_TERM];
	}

	#[\Override]
	public function getAlternateIds(): array {
		return [];
	}

	#[\Override]
	public function getCustomFilters(): array {
		return [];
	}

	#[\Override]
	public function search(IUser $user, ISearchQuery $query): SearchResult {
		// The rules of now for every search, also in a process that lives
		// longer than one request: a rule written a moment ago holds here
		// before SchedulerJob turns it into work (owner 14.11.2026).
		$this->exclusions->reload();
		$term = mb_substr(trim($query->getTerm()), 0, self::MAX_TERM_LENGTH);
		if ($term === '') {
			return SearchResult::complete($this->getName(), []);
		}

		// Before the first call that could reach the container: an excluded
		// user, by name or through a group, never gets a hit.
		$uid = $user->getUID();
		if ($this->exclusions->isExcludedUser($uid)) {
			$this->logger->debug('Audio & Video Search: no search, the user is excluded');
			return SearchResult::complete($this->getName(), []);
		}

		if (!$this->exAppService->searchAllowed()) {
			$this->logger->debug('Audio & Video Search: no search, the two halves drifted apart');
			return SearchResult::complete($this->getName(), []);
		}

		$startedAt = hrtime(true);
		$hits = $this->exAppService->search($uid, $term, self::SEARCH_LIMIT);
		if ($hits === null) {
			$this->logger->debug('Audio & Video Search: the backend gave no usable answer');
			return SearchResult::complete($this->getName(), []);
		}

		return SearchResult::complete($this->getName(), $this->entries($uid, $hits, $startedAt));
	}

	/**
	 * The confirmed hits as entries, in the order the container ranked them.
	 *
	 * @param list<array{fileId:int,startMs:int,excerpt:string,sample:bool}> $hits
	 * @return list<SearchResultEntry>
	 */
	private function entries(string $uid, array $hits, int $startedAt): array {
		$showSamples = $this->config->getSystemValueBool('debug', false)
			&& $this->appConfig->getValueBool(Application::APP_ID, self::KEY_SAMPLE_VISIBLE, false);

		try {
			$userFolder = $this->readerContext->actAs($uid, fn (): Folder => $this->rootFolder->getUserFolder($uid));
		} catch (\Throwable $e) {
			$this->logger->debug('Audio & Video Search: no user folder for the search', ['exception' => $e]);
			return [];
		}

		$entries = [];
		$checked = 0;
		foreach ($hits as $hit) {
			if ($hit['sample'] && !$showSamples) {
				continue;
			}

			if ((hrtime(true) - $startedAt) / 1e9 > self::BUDGET_SECONDS) {
				$this->logger->debug('Audio & Video Search: time budget spent during the recheck', [
					'checked' => $checked,
					'proposed' => count($hits),
				]);
				break;
			}

			$fileId = $hit['fileId'];
			$checked++;
			// A storage, a folder or an owner excluded after the first crawl
			// may still have references in the container until SchedulerJob
			// removes them; such a hit never appears. A question that fails
			// is a yes (ExclusionService).
			if ($this->exclusions->isExcludedFile($fileId)) {
				continue;
			}
			try {
				$file = $this->readerContext->actAs($uid, static fn (): ?File => FileAccess::readableFile($userFolder, $fileId));
			} catch (\Throwable $e) {
				$this->logger->debug('Audio & Video Search: a recheck failed', ['fileId' => $fileId, 'exception' => $e]);
				continue;
			}
			if ($file === null) {
				continue;
			}

			$entries[] = $this->entry($userFolder, $file, $fileId, $hit);
		}

		return $entries;
	}

	/**
	 * @param array{fileId:int,startMs:int,excerpt:string,sample:bool} $hit
	 */
	private function entry(Folder $userFolder, File $file, int $fileId, array $hit): SearchResultEntry {
		$parts = [self::clock($hit['startMs'])];
		if ($hit['sample']) {
			$parts[] = $this->l10n->t('Test result');
		}
		$excerpt = self::shorten($hit['excerpt']);
		if ($excerpt !== '') {
			$parts[] = $excerpt;
		}

		$entry = new SearchResultEntry(
			$this->mimeTypeDetector->mimeTypeIcon($file->getMimetype()),
			$file->getName(),
			implode(self::SEPARATOR, $parts),
			$this->urlGenerator->linkToRouteAbsolute('audio_video_search.page.play', [
				'fileId' => $fileId,
				't' => sprintf('%.1f', intdiv($hit['startMs'], 100) / 10),
			]),
		);
		// Both or neither (owner 06.11.): clients that open the file by id
		// also need the path to show where it lives.
		$entry->addAttribute('fileId', (string)$fileId);
		$entry->addAttribute('path', FileAccess::relativePath($userFolder, $file));

		return $entry;
	}

	/**
	 * A time mark as m:ss below one hour and h:mm:ss above, not localised.
	 * Milliseconds are cut, never rounded up, so the mark never lies ahead
	 * of the spoken word.
	 */
	public static function clock(int $milliseconds): string {
		$seconds = intdiv(max(0, $milliseconds), 1000);
		$hours = intdiv($seconds, 3600);
		$minutes = intdiv($seconds % 3600, 60);
		$rest = $seconds % 60;

		return $hours > 0
			? sprintf('%d:%02d:%02d', $hours, $minutes, $rest)
			: sprintf('%d:%02d', $minutes, $rest);
	}

	/**
	 * An excerpt of at most MAX_EXCERPT_LENGTH characters, cut at the last word
	 * boundary and closed with an ellipsis when it had to be cut. Plain text:
	 * the web client escapes it, and no markup is built here.
	 */
	public static function shorten(string $text): string {
		$clean = preg_replace('/\s+/u', ' ', $text);
		$clean = trim(is_string($clean) ? $clean : $text);
		if (mb_strlen($clean) <= self::MAX_EXCERPT_LENGTH) {
			return $clean;
		}

		$room = self::MAX_EXCERPT_LENGTH - 1;
		$cut = mb_substr($clean, 0, $room);
		if (mb_substr($clean, $room, 1) !== ' ') {
			$space = mb_strrpos($cut, ' ');
			if ($space !== false && $space > 0) {
				$cut = mb_substr($cut, 0, $space);
			}
		}

		return rtrim($cut, ' ,;:') . self::ELLIPSIS;
	}
}
