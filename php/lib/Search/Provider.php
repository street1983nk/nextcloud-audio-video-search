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
 * Paging (D-03-02, D-03-15): the web dialog of NC 33 and 34 sends no cursor,
 * it asks the same search again with limit + 5 and shows "load more" only
 * when exactly limit entries came back. So this provider fills a page up to
 * exactly limit confirmed entries while the container has more, in at most
 * MAX_ROUNDS rounds of limit * OVERFETCH proposals each (Findling
 * SearchService::run). API clients that send a cursor get it read as the
 * offset into the same fixed order of the container; the next cursor points
 * right behind the last DELIVERED proposal, never behind the last fetched
 * one, so no mark falls into a gap between two pages.
 *
 * The recheck of a file (exclusion and read right) is done once per file and
 * search: a file brings up to three marks per tier, and the answer for the
 * second mark is the one for the first. The cache lives in this one call.
 *
 * A mark of a preview, or of a stage the container did not name, carries the
 * word "Preliminary" in its subline (D-03-03, UI-SPEC T1); a test result
 * carries "Test result" instead, never both; a final mark carries neither.
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

	/** The server side ceiling of a page, as the one of the web dialog. */
	private const MAX_LIMIT = 25;

	/** The deepest cursor that is passed on (container MAX_OFFSET, plan 03-08). */
	private const MAX_CONTAINER_OFFSET = 1200;

	/**
	 * At most three rounds of asking, each with four times the page size, as in
	 * Findling. The recheck can drop proposals, so asking again is necessary;
	 * asking without a bound is what makes a permission check at query time
	 * unusable.
	 */
	private const MAX_ROUNDS = 3;
	private const OVERFETCH = 4;

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

		$page = $this->entries($uid, $term, max(1, min(self::MAX_LIMIT, $query->getLimit())), $this->startOffset($query));

		return $page['cursor'] !== null
			? SearchResult::paginated($this->getName(), $page['entries'], $page['cursor'])
			: SearchResult::complete($this->getName(), $page['entries']);
	}

	/**
	 * Where the page starts. The web dialog sends no cursor; an API client
	 * hands back the cursor of the previous answer, which is an offset into the
	 * order of the container. Anything that is not a plain number starts at the
	 * top, and a cursor deeper than the container accepts ends at its ceiling.
	 */
	private function startOffset(ISearchQuery $query): int {
		$cursor = $query->getCursor();
		$offset = 0;
		if (is_int($cursor) && $cursor > 0) {
			$offset = $cursor;
		} elseif (is_string($cursor) && $cursor !== '' && ctype_digit($cursor)) {
			$offset = strlen($cursor) > 9 ? self::MAX_CONTAINER_OFFSET : (int)$cursor;
		}

		return min(self::MAX_CONTAINER_OFFSET, $offset);
	}

	/**
	 * Exactly $limit confirmed entries while the container has more, in the
	 * order it ranked them, and the cursor of the next page; the cursor is null
	 * when nothing is behind this page.
	 *
	 * Every proposal is rechecked at the time of the search: the rules of
	 * exclusion read at the start of this search, then the read right in the
	 * folder of the searching user. Both answers are kept per file id for this
	 * one call only. A storage, a folder or an owner excluded after the first
	 * crawl may still have references in the container until SchedulerJob
	 * removes them; such a hit never appears. A question that fails is a yes
	 * (ExclusionService).
	 *
	 * @return array{entries: list<SearchResultEntry>, cursor: ?int}
	 */
	private function entries(string $uid, string $term, int $limit, int $offset): array {
		$startedAt = hrtime(true);
		$showSamples = $this->config->getSystemValueBool('debug', false)
			&& $this->appConfig->getValueBool(Application::APP_ID, self::KEY_SAMPLE_VISIBLE, false);

		$userFolder = null;
		/** @var array<int, ?File> $checked the recheck of each file, once per search */
		$checked = [];
		$entries = [];

		for ($round = 0; $round < self::MAX_ROUNDS; $round++) {
			if ($offset > self::MAX_CONTAINER_OFFSET || self::secondsSince($startedAt) > self::BUDGET_SECONDS) {
				break;
			}

			$page = $this->exAppService->search($uid, $term, $limit * self::OVERFETCH, $offset);
			if ($page === null) {
				// Silent, as before: the entries of earlier rounds are confirmed
				// and are shown, and nothing promises a next page.
				$this->logger->debug('Audio & Video Search: the backend gave no usable answer', ['round' => $round]);
				break;
			}

			if ($userFolder === null && $page['hits'] !== []) {
				try {
					$userFolder = $this->readerContext->actAs($uid, fn (): Folder => $this->rootFolder->getUserFolder($uid));
				} catch (\Throwable $e) {
					$this->logger->debug('Audio & Video Search: no user folder for the search', ['exception' => $e]);
					break;
				}
			}

			$last = count($page['hits']) - 1;
			foreach ($page['hits'] as $position => $hit) {
				if (self::secondsSince($startedAt) > self::BUDGET_SECONDS) {
					$this->logger->debug('Audio & Video Search: time budget spent during the recheck', [
						'checked' => count($checked),
						'delivered' => count($entries),
					]);
					break 2;
				}
				if ($userFolder === null || ($hit['sample'] && !$showSamples)) {
					continue;
				}

				$fileId = $hit['fileId'];
				if (!array_key_exists($fileId, $checked)) {
					$checked[$fileId] = null;
					if (!$this->exclusions->isExcludedFile($fileId)) {
						try {
							$checked[$fileId] = $this->readerContext->actAs($uid, static fn (): ?File => FileAccess::readableFile($userFolder, $fileId));
						} catch (\Throwable $e) {
							$this->logger->debug('Audio & Video Search: a recheck failed', ['fileId' => $fileId, 'exception' => $e]);
						}
					}
				}
				$file = $checked[$fileId];
				if ($file === null) {
					continue;
				}

				$entries[] = $this->entry($userFolder, $file, $fileId, $hit);
				if (count($entries) === $limit) {
					// Behind the last DELIVERED proposal, not the last fetched
					// one, so the next page leaves no gap. A full page offers a
					// next one unless this was the last proposal there is.
					$more = $position < $last || $page['hasMore'];

					return ['entries' => $entries, 'cursor' => $more ? $offset + $position + 1 : null];
				}
			}

			if (!$page['hasMore'] || $page['nextOffset'] <= $offset) {
				break;
			}
			$offset = $page['nextOffset'];
		}

		// Fewer than $limit: there is nothing behind this page that a client
		// could ask for, so no "load more" (budget, rounds or the end).
		return ['entries' => $entries, 'cursor' => null];
	}

	private static function secondsSince(int $startedAt): float {
		return (hrtime(true) - $startedAt) / 1e9;
	}

	/**
	 * One mark as one entry. The subline is "time · Preliminary · excerpt" for
	 * a preview (and any stage that is not final), "time · Test result ·
	 * excerpt" for a test result and "time · excerpt" for a final mark; never
	 * two marks of state, never a separator at the end.
	 *
	 * @param array{fileId:int,startMs:int,excerpt:string,sample:bool,stage:string} $hit
	 */
	private function entry(Folder $userFolder, File $file, int $fileId, array $hit): SearchResultEntry {
		$parts = [self::clock($hit['startMs'])];
		if ($hit['sample'] || $hit['stage'] === 'sample') {
			$parts[] = $this->l10n->t('Test result');
		} elseif ($hit['stage'] !== 'final') {
			$parts[] = $this->l10n->t('Preliminary');
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
