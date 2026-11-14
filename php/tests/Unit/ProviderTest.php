<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Search\Provider;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ExclusionService;
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
use OCP\IUserManager;
use OCP\IUserSession;
use OCP\Search\IFilter;
use OCP\Search\ISearchQuery;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The unified search entry: recheck, time mark, play link, the marks of state
 * and the paging (plan 03-12).
 *
 * The container is a double of ExAppService, the file system a double of the
 * user folder. Every hit the container proposes has to survive
 * FileAccess::readableFile in the folder of the searching user, and title and
 * path of an entry come out of that node, never out of the answer.
 *
 * The double of the container holds one fixed order of proposals ($hits) and
 * cuts it like the container does (plan 03-08): [offset, offset + limit),
 * nextOffset = offset + count, hasMore while proposals are left.
 */
#[CoversClass(Provider::class)]
final class ProviderTest extends TestCase {
	/** @var list<array{fileId:int,startMs:int,excerpt:string,sample:bool,stage:string}>|null the fixed order of the container */
	private ?array $hits = [];

	/** @var list<array{limit:int,offset:int}> every call to the container */
	private array $pages = [];

	/** The call (1 based) from which the container gives no usable answer. */
	private ?int $failFromCall = null;

	/** How often a file was looked up in the folder of alice. */
	private int $lookups = 0;

	private bool $debug = false;
	private bool $sampleVisible = false;
	private bool $allowed = true;
	private int $searchCalls = 0;
	private int $allowedCalls = 0;

	/** @var list<string> the users a rule of the admin excludes */
	private array $excludedUsers = [];

	/** @var list<string> every user the exclusions were asked about */
	private array $askedUsers = [];

	/** @var list<int> the files a rule of the admin excludes, set after the first crawl */
	private array $excludedFiles = [];

	/** @var list<int> every file the exclusions were asked about */
	private array $askedFiles = [];

	/**
	 * The double keeps the rules it read like the real service (read once per
	 * instance, again only after reload), for the tests about the rules of now.
	 */
	private bool $cachedRules = false;

	/** @var array{users: list<string>, files: list<int>}|null the rules the double read last */
	private ?array $ruleSnapshot = null;

	/** @var list<string> the questions to the exclusions in their order */
	private array $exclusionCalls = [];

	/** @var list<string> every log line with its context, as one text */
	private array $logged = [];

	/** @var array<int, File> the files alice may read, by id */
	private array $readable = [];

	/** @var list<array{string, array<string, mixed>}> */
	private array $links = [];

	protected function setUp(): void {
		parent::setUp();

		$this->hits = [];
		$this->pages = [];
		$this->failFromCall = null;
		$this->lookups = 0;
		$this->debug = false;
		$this->sampleVisible = false;
		$this->allowed = true;
		$this->searchCalls = 0;
		$this->allowedCalls = 0;
		$this->excludedUsers = [];
		$this->askedUsers = [];
		$this->excludedFiles = [];
		$this->askedFiles = [];
		$this->cachedRules = false;
		$this->ruleSnapshot = null;
		$this->exclusionCalls = [];
		$this->logged = [];
		$this->readable = [];
		$this->links = [];
	}

	private function provider(): Provider {
		$l10n = $this->createMock(IL10N::class);
		$l10n->method('t')->willReturnArgument(0);

		$urls = $this->createMock(IURLGenerator::class);
		$urls->method('linkToRouteAbsolute')->willReturnCallback(
			function (string $route, array $parameters = []): string {
				$this->links[] = [$route, $parameters];

				return 'https://cloud.example/apps/audio_video_search/play/' . $parameters['fileId'] . '?t=' . $parameters['t'];
			},
		);

		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('searchAllowed')->willReturnCallback(function (): bool {
			$this->allowedCalls++;

			return $this->allowed;
		});
		$exApp->method('search')->willReturnCallback(function (string $uid, string $term, int $limit, int $offset = 0): ?array {
			$this->searchCalls++;
			self::assertSame('alice', $uid);
			self::assertLessThanOrEqual(200, mb_strlen($term));
			$this->pages[] = ['limit' => $limit, 'offset' => $offset];
			if ($this->hits === null || ($this->failFromCall !== null && $this->searchCalls >= $this->failFromCall)) {
				return null;
			}

			// The container caps a page at 50 (ExAppService::MAX_LIMIT).
			$cut = array_slice($this->hits, $offset, min(50, $limit));

			return [
				'hits' => $cut,
				'nextOffset' => $offset + count($cut),
				'hasMore' => $offset + count($cut) < count($this->hits),
			];
		});

		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturnCallback(function (int $id): ?File {
			$this->lookups++;

			return $this->readable[$id] ?? null;
		});
		$userFolder->method('getRelativePath')->willReturnCallback(
			static fn (string $path): string => substr($path, strlen('/alice/files')),
		);
		$root = $this->createMock(IRootFolder::class);
		$root->method('getUserFolder')->with('alice')->willReturn($userFolder);

		$config = $this->createMock(IConfig::class);
		$config->method('getSystemValueBool')->willReturnCallback(
			fn (string $key, bool $default = false): bool => $key === 'debug' ? $this->debug : $default,
		);
		$appConfig = $this->createMock(IAppConfig::class);
		$appConfig->method('getValueBool')->willReturnCallback(
			fn (string $app, string $key, bool $default = false): bool => $app === Application::APP_ID && $key === 'sample_visible'
				? $this->sampleVisible
				: $default,
		);

		$mime = $this->createMock(IMimeTypeDetector::class);
		$mime->method('mimeTypeIcon')->willReturn('https://cloud.example/core/img/filetypes/video.svg');

		$session = $this->createMock(IUserSession::class);
		$alice = $this->user();
		$session->method('getUser')->willReturn($alice);

		$exclusions = $this->createMock(ExclusionService::class);
		$exclusions->method('reload')->willReturnCallback(function (): void {
			$this->exclusionCalls[] = 'reload';
			$this->ruleSnapshot = null;
		});
		$exclusions->method('isExcludedUser')->willReturnCallback(function (string $uid): bool {
			$this->exclusionCalls[] = 'user';
			$this->askedUsers[] = $uid;

			return in_array($uid, $this->rulesInForce()['users'], true);
		});
		$exclusions->method('isExcludedFile')->willReturnCallback(function (int $fileId): bool {
			$this->exclusionCalls[] = 'file';
			$this->askedFiles[] = $fileId;

			return in_array($fileId, $this->rulesInForce()['files'], true);
		});

		$logger = $this->createMock(LoggerInterface::class);
		$logger->method('debug')->willReturnCallback(function (string|\Stringable $message, array $context = []): void {
			$this->logged[] = $message . ' ' . json_encode($context);
		});

		return new Provider(
			$l10n,
			$urls,
			$exApp,
			$root,
			new ReaderContext($session, $this->createMock(IUserManager::class)),
			$config,
			$appConfig,
			$mime,
			$logger,
			$exclusions,
		);
	}

	/**
	 * What the double of the exclusions answers with: the rules of the test
	 * now, or with cachedRules the ones it read first since the last reload.
	 *
	 * @return array{users: list<string>, files: list<int>}
	 */
	private function rulesInForce(): array {
		$now = ['users' => $this->excludedUsers, 'files' => $this->excludedFiles];
		if (!$this->cachedRules) {
			return $now;
		}

		return $this->ruleSnapshot ??= $now;
	}

	private function user(): IUser&MockObject {
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn('alice');

		return $user;
	}

	private function query(string $term, int $limit = 5, int|string|null $cursor = null): ISearchQuery&MockObject {
		$query = $this->createMock(ISearchQuery::class);
		$query->method('getTerm')->willReturn($term);
		$query->method('getLimit')->willReturn($limit);
		$query->method('getCursor')->willReturn($cursor);
		$query->method('getRoute')->willReturn('files.view.index');

		return $query;
	}

	private function file(int $id, string $name, bool $readable = true): File&MockObject {
		$file = $this->createMock(File::class);
		$file->method('getId')->willReturn($id);
		$file->method('getName')->willReturn($name);
		$file->method('getPath')->willReturn('/alice/files/Sitzungen/' . $name);
		$file->method('getMimetype')->willReturn('video/mp4');
		$file->method('isReadable')->willReturn($readable);
		$this->readable[$id] = $file;

		return $file;
	}

	/**
	 * The entries of one search as plain arrays.
	 *
	 * @return list<array<string, mixed>>
	 */
	private function entries(string $term = 'Haushalt'): array {
		return $this->page($term)['entries'];
	}

	/**
	 * One whole answer: the entries as plain arrays, isPaginated and the cursor.
	 *
	 * @return array{entries: list<array<string, mixed>>, isPaginated: bool, cursor: mixed}
	 */
	private function page(string $term = 'Haushalt', int $limit = 5, int|string|null $cursor = null): array {
		$result = $this->provider()->search($this->user(), $this->query($term, $limit, $cursor))->jsonSerialize();
		$entries = [];
		foreach ($result['entries'] as $entry) {
			$entries[] = is_array($entry) ? $entry : $entry->jsonSerialize();
		}

		return ['entries' => $entries, 'isPaginated' => (bool)$result['isPaginated'], 'cursor' => $result['cursor']];
	}

	/**
	 * A proposal as ExAppService::search hands it on. 'final' by default so
	 * the older cases keep their subline; a sample is always the stage sample.
	 *
	 * @return array{fileId:int,startMs:int,excerpt:string,sample:bool,stage:string}
	 */
	private static function hit(int $fileId, int $startMs, string $excerpt = 'der Haushalt wird beraten', bool $sample = false, string $stage = 'final'): array {
		return ['fileId' => $fileId, 'startMs' => $startMs, 'excerpt' => $excerpt, 'sample' => $sample, 'stage' => $sample ? 'sample' : $stage];
	}

	/**
	 * $count marks, one second apart, spread over files 11, 12, ... with three
	 * marks per file, as the tiers of the container bring them.
	 *
	 * @return list<array{fileId:int,startMs:int,excerpt:string,sample:bool,stage:string}>
	 */
	private function marks(int $count, string $stage = 'final'): array {
		$hits = [];
		for ($index = 0; $index < $count; $index++) {
			$fileId = 11 + intdiv($index, 3);
			if (!isset($this->readable[$fileId])) {
				$this->file($fileId, 'Sitzung ' . $fileId . '.mp4');
			}
			$hits[] = self::hit($fileId, ($index + 1) * 1000, 'Stelle ' . $index, false, $stage);
		}

		return $hits;
	}

	/**
	 * The time marks of a page, which name the proposal they came from.
	 *
	 * @param list<array<string, mixed>> $entries
	 * @return list<string>
	 */
	private static function urls(array $entries): array {
		return array_map(static fn (array $entry): string => (string)$entry['resourceUrl'], $entries);
	}

	public function testItsIdNameAndOrder(): void {
		$provider = $this->provider();

		self::assertSame('audio_video_search', $provider->getId());
		self::assertSame('Audio and video', $provider->getName());
		self::assertSame(-5, $provider->getOrder('files.view.index', []));
		self::assertSame(25, $provider->getOrder('dashboard.dashboard.index', []));
	}

	public function testOnlyTheTermFilterIsSupported(): void {
		$provider = $this->provider();

		self::assertSame([IFilter::BUILTIN_TERM], $provider->getSupportedFilters());
		self::assertSame([], $provider->getAlternateIds());
		self::assertSame([], $provider->getCustomFilters());
	}

	public function testAnEmptyTermAsksNobody(): void {
		self::assertSame([], $this->entries('   '));
		self::assertSame(0, $this->searchCalls);
	}

	public function testADriftOnRecordAsksNobody(): void {
		$this->allowed = false;
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 754200)];

		self::assertSame([], $this->entries());
		self::assertSame(0, $this->searchCalls);
	}

	public function testAnExcludedUserGetsNoHitAndTheContainerIsNeverAsked(): void {
		$this->excludedUsers = ['alice'];
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 754200)];

		self::assertSame([], $this->entries());
		self::assertSame(['alice'], $this->askedUsers);
		self::assertSame(0, $this->allowedCalls);
		self::assertSame(0, $this->searchCalls);
		self::assertSame([], $this->links);
	}

	public function testTheAnswerForAnExcludedUserIsTheOneOfASearchThatFoundNothing(): void {
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [];
		$nothingFound = $this->provider()->search($this->user(), $this->query('Haushalt'))->jsonSerialize();

		$this->excludedUsers = ['alice'];
		$this->hits = [self::hit(11, 754200)];
		$excluded = $this->provider()->search($this->user(), $this->query('Haushalt'))->jsonSerialize();

		self::assertSame($nothingFound, $excluded);
		self::assertSame(1, $this->searchCalls);
	}

	public function testTheLogLineOfAnExclusionNamesNeitherTheUserNorTheTerm(): void {
		$this->excludedUsers = ['alice'];

		self::assertSame([], $this->entries('Haushaltsgeheimnis'));
		self::assertCount(1, $this->logged);
		self::assertStringNotContainsString('alice', $this->logged[0]);
		self::assertStringNotContainsString('Haushaltsgeheimnis', $this->logged[0]);
	}

	public function testAUserWhoIsNotExcludedIsAskedAboutOnceAndGetsTheHits(): void {
		$this->excludedUsers = ['bob'];
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 754200)];

		self::assertCount(1, $this->entries());
		self::assertSame(['alice'], $this->askedUsers);
		self::assertSame(1, $this->searchCalls);
	}

	public function testABackendWithoutAnswerIsAnEmptyGroup(): void {
		$this->hits = null;

		self::assertSame([], $this->entries());
	}

	public function testAHitCarriesTimeExcerptAndThePlayLink(): void {
		$this->file(11, 'Sitzung 2026-11-03.mp4');
		$this->hits = [self::hit(11, 754200)];

		$entries = $this->entries();

		self::assertCount(1, $entries);
		self::assertSame('Sitzung 2026-11-03.mp4', $entries[0]['title']);
		self::assertSame('12:34 · der Haushalt wird beraten', $entries[0]['subline']);
		self::assertSame([['audio_video_search.page.play', ['fileId' => 11, 't' => '754.2']]], $this->links);
		self::assertSame('https://cloud.example/apps/audio_video_search/play/11?t=754.2', $entries[0]['resourceUrl']);
		self::assertSame('https://cloud.example/core/img/filetypes/video.svg', $entries[0]['thumbnailUrl']);
	}

	public function testTheClockFormat(): void {
		self::assertSame('0:05', Provider::clock(5000));
		self::assertSame('0:05', Provider::clock(5999));
		self::assertSame('12:34', Provider::clock(754200));
		self::assertSame('59:59', Provider::clock(3599999));
		self::assertSame('1:02:03', Provider::clock(3723000));
		self::assertSame('0:00', Provider::clock(0));
	}

	public function testAnHourLongMarkInTheSubline(): void {
		$this->file(11, 'Lange Sitzung.mp4');
		$this->hits = [self::hit(11, 3723000)];

		self::assertStringStartsWith('1:02:03 · ', (string)$this->entries()[0]['subline']);
	}

	public function testALongExcerptIsCutAtAWordBoundaryWithAnEllipsis(): void {
		$long = trim(str_repeat('Haushaltsberatung im Rat ', 12));
		self::assertGreaterThan(250, mb_strlen($long));
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 5000, mb_substr($long . ' ' . $long, 0, 300))];

		$subline = (string)$this->entries()[0]['subline'];
		$excerpt = mb_substr($subline, mb_strlen('0:05 · '));

		self::assertLessThanOrEqual(120, mb_strlen($excerpt));
		self::assertStringEndsWith('…', $excerpt);
		$body = mb_substr($excerpt, 0, -1);
		self::assertStringStartsWith($body, $long . ' ' . $long);
		// The cut lands on a word boundary: the next character of the source is a space.
		self::assertSame(' ', mb_substr($long . ' ' . $long, mb_strlen($body), 1));
	}

	public function testAShortExcerptStaysWhole(): void {
		self::assertSame('kurz', Provider::shorten('kurz'));
		self::assertSame(str_repeat('a', 120), Provider::shorten(str_repeat('a', 120)));
		self::assertSame(120, mb_strlen(Provider::shorten(str_repeat('a', 300))));
	}

	public function testASampleHitIsDroppedWithoutDebugMode(): void {
		$this->sampleVisible = true;
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 42000, 'Testtext', true)];

		self::assertSame([], $this->entries());
	}

	public function testASampleHitIsDroppedWithoutTheSwitch(): void {
		$this->debug = true;
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 42000, 'Testtext', true)];

		self::assertSame([], $this->entries());
	}

	public function testASampleHitIsMarkedWithDebugModeAndTheSwitch(): void {
		$this->debug = true;
		$this->sampleVisible = true;
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 42000, 'Testtext', true)];

		self::assertSame('0:42 · Test result · Testtext', $this->entries()[0]['subline']);
	}

	public function testAFileTheUserCannotReadNeverAppears(): void {
		$this->file(11, 'Fremd.mp4', false);
		$this->file(12, 'Eigen.mp4');
		$this->hits = [self::hit(11, 1000), self::hit(99, 1000), self::hit(12, 2000)];

		$entries = $this->entries();

		self::assertCount(1, $entries);
		self::assertSame('Eigen.mp4', $entries[0]['title']);
	}

	public function testAHitOfAFileExcludedAfterTheCrawlNeverAppears(): void {
		$this->file(11, 'Archiv.mp4');
		$this->file(12, 'Eigen.mp4');
		$this->hits = [self::hit(11, 1000), self::hit(12, 2000)];
		$this->excludedFiles = [11];

		$entries = $this->entries();

		self::assertCount(1, $entries);
		self::assertSame('Eigen.mp4', $entries[0]['title']);
		self::assertSame([11, 12], $this->askedFiles);
		self::assertSame([['audio_video_search.page.play', ['fileId' => 12, 't' => '2.0']]], $this->links);
	}

	public function testAnExclusionSetBetweenTwoSearchesHoldsForTheSecondOne(): void {
		$this->cachedRules = true;
		$this->file(11, 'Archiv.mp4');
		$this->hits = [self::hit(11, 1000)];
		$provider = $this->provider();

		$before = $provider->search($this->user(), $this->query('Haushalt'))->jsonSerialize();
		$this->excludedFiles = [11];
		$after = $provider->search($this->user(), $this->query('Haushalt'))->jsonSerialize();

		self::assertCount(1, $before['entries']);
		self::assertSame([], $after['entries']);
	}

	public function testEverySearchReadsTheRulesBeforeItAsksAnything(): void {
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 1000)];

		$this->entries();

		self::assertSame(['reload', 'user', 'file'], $this->exclusionCalls);
	}

	public function testAUserExcludedBetweenTwoSearchesGetsNothingFromTheSecondOne(): void {
		$this->cachedRules = true;
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 1000)];
		$provider = $this->provider();

		$provider->search($this->user(), $this->query('Haushalt'));
		$this->excludedUsers = ['alice'];
		$after = $provider->search($this->user(), $this->query('Haushalt'))->jsonSerialize();

		self::assertSame([], $after['entries']);
		self::assertSame(1, $this->searchCalls);
	}

	public function testTheAttributesCarryFileIdAndARelativePath(): void {
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 754200)];

		self::assertSame(
			['fileId' => '11', 'path' => 'Sitzungen/Sitzung.mp4'],
			$this->entries()[0]['attributes'],
		);
	}

	public function testTheTitleComesFromTheNodeAndNeverFromTheAnswer(): void {
		$this->file(11, 'Echter Name.mp4');
		$hit = self::hit(11, 1000);
		$hit['title'] = 'Gefälschter Name.mp4';
		$this->hits = [$hit];

		$entries = $this->entries();

		self::assertSame('Echter Name.mp4', $entries[0]['title']);
		self::assertStringNotContainsString('Gefälschter', (string)json_encode($entries));
	}

	public function testTheSublineNeverCarriesADash(): void {
		$this->debug = true;
		$this->sampleVisible = true;
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 3723000, 'Text', true), self::hit(11, 5000)];

		foreach ($this->entries() as $entry) {
			self::assertStringNotContainsString("\u{2013}", (string)$entry['subline']);
			self::assertStringNotContainsString("\u{2014}", (string)$entry['subline']);
		}
	}

	public function testTwoMarksInOneFileAreTwoEntriesWithTheirOwnLink(): void {
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 1000), self::hit(11, 61500)];

		$entries = $this->entries();

		self::assertCount(2, $entries);
		self::assertNotSame($entries[0]['resourceUrl'], $entries[1]['resourceUrl']);
		self::assertSame('61.5', $this->links[1][1]['t']);
	}

	// -- paging, recheck cache and the marks of state (plan 03-12) ---------------

	public function testALimitOfFiveGivesExactlyFiveAndACursorBehindThem(): void {
		$this->hits = $this->marks(12);

		$page = $this->page('Haushalt', 5);

		self::assertCount(5, $page['entries']);
		self::assertTrue($page['isPaginated']);
		self::assertSame(5, $page['cursor']);
		self::assertSame([['limit' => 20, 'offset' => 0]], $this->pages);
	}

	public function testALargerLimitStartsWithTheSameMarks(): void {
		$this->hits = $this->marks(12);
		$five = self::urls($this->page('Haushalt', 5)['entries']);
		$this->links = [];

		$ten = self::urls($this->page('Haushalt', 10)['entries']);

		self::assertCount(10, $ten);
		self::assertSame($five, array_slice($ten, 0, 5));
	}

	public function testUnreadableProposalsAreFilledUpToTheLimitAndTheCursorFollowsTheLastDelivered(): void {
		// Positions 0..6: files 21 and 23 are closed, so five entries need
		// seven proposals, and the fifth delivered one is position 6.
		$this->file(20, 'A.mp4');
		$this->file(21, 'Fremd.mp4', false);
		$this->file(22, 'B.mp4');
		$this->file(23, 'Fremd2.mp4', false);
		$this->file(24, 'C.mp4');
		$this->file(25, 'D.mp4');
		$this->file(26, 'E.mp4');
		$this->file(27, 'F.mp4');
		$this->hits = [
			self::hit(20, 1000), self::hit(21, 1000), self::hit(22, 1000), self::hit(23, 1000),
			self::hit(24, 1000), self::hit(25, 1000), self::hit(26, 1000), self::hit(27, 1000),
		];

		$page = $this->page('Haushalt', 5);

		self::assertSame(['A.mp4', 'B.mp4', 'C.mp4', 'D.mp4', 'E.mp4'], array_column($page['entries'], 'title'));
		self::assertTrue($page['isPaginated']);
		self::assertSame(7, $page['cursor']);

		// The next page with that cursor begins with the first mark not shown.
		$this->links = [];
		$next = $this->page('Haushalt', 5, $page['cursor']);
		self::assertSame(['F.mp4'], array_column($next['entries'], 'title'));
		self::assertFalse($next['isPaginated']);
	}

	public function testAFileWithThreeMarksIsCheckedOnce(): void {
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 1000), self::hit(11, 2000), self::hit(11, 3000)];

		self::assertCount(3, $this->entries());
		self::assertSame(1, $this->lookups);
		self::assertSame([11], $this->askedFiles);
	}

	public function testAClosedFileWithThreeMarksIsCheckedOnceAndNeverShown(): void {
		$this->file(11, 'Fremd.mp4', false);
		$this->file(12, 'Eigen.mp4');
		$this->hits = [self::hit(11, 1000), self::hit(11, 2000), self::hit(11, 3000), self::hit(12, 4000)];

		self::assertSame(['Eigen.mp4'], array_column($this->entries(), 'title'));
		self::assertSame(2, $this->lookups);
		self::assertSame([11, 12], $this->askedFiles);
	}

	public function testTheLastPageIsComplete(): void {
		$this->hits = $this->marks(3);

		$page = $this->page('Haushalt', 5);

		self::assertCount(3, $page['entries']);
		self::assertFalse($page['isPaginated']);
		self::assertCount(1, $this->pages);
	}

	public function testAFullPageWithTheVeryLastProposalIsComplete(): void {
		$this->hits = $this->marks(5);

		$page = $this->page('Haushalt', 5);

		self::assertCount(5, $page['entries']);
		self::assertFalse($page['isPaginated']);
	}

	public function testATestResultIsMarkedAsSuchAndNeverAsPreliminary(): void {
		$this->debug = true;
		$this->sampleVisible = true;
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 42000, 'Testtext', true)];

		$subline = (string)$this->entries()[0]['subline'];

		self::assertSame('0:42 · Test result · Testtext', $subline);
		self::assertStringNotContainsString('Preliminary', $subline);
	}

	public function testAPreviewIsPreliminaryBeforeTheExcerptAndAFinalMarkHasNoMark(): void {
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [
			self::hit(11, 83000, 'der Haushalt', false, 'preview'),
			self::hit(11, 84000, 'der Haushalt', false, 'final'),
		];

		$entries = $this->entries();

		self::assertSame('1:23 · Preliminary · der Haushalt', $entries[0]['subline']);
		self::assertSame('1:24 · der Haushalt', $entries[1]['subline']);
	}

	public function testAPreviewWithoutExcerptEndsWithoutASeparator(): void {
		$this->file(11, 'Sitzung.mp4');
		$this->hits = [self::hit(11, 83000, '', false, 'preview')];

		self::assertSame('1:23 · Preliminary', $this->entries()[0]['subline']);
	}

	public function testACursorIsReadAsTheOffsetAndCappedAtTheCeiling(): void {
		$this->hits = $this->marks(30);

		$this->page('Haushalt', 5, '17');
		$this->page('Haushalt', 5, 17);
		$this->page('Haushalt', 5, '9999');
		$this->page('Haushalt', 5, '99999999999999999999');
		$this->page('Haushalt', 5, 'abc');
		$this->page('Haushalt', 5, '-3');

		self::assertSame([17, 17, 1200, 1200, 0, 0], array_column($this->pages, 'offset'));
	}

	public function testTheLimitIsCappedAtTwentyFiveAndAtLeastOne(): void {
		$this->hits = $this->marks(60);

		self::assertCount(25, $this->page('Haushalt', 40)['entries']);
		self::assertCount(1, $this->page('Haushalt', 0)['entries']);
		self::assertSame([100, 4], array_column($this->pages, 'limit'));
	}

	public function testABackendThatFailsInTheSecondRoundKeepsTheFirstRound(): void {
		// Round 1 brings 20 proposals of which only file 11 is readable.
		$this->hits = $this->marks(40);
		foreach (array_keys($this->readable) as $id) {
			if ($id !== 11) {
				$this->file($id, 'Fremd ' . $id . '.mp4', false);
			}
		}
		$this->failFromCall = 2;

		$page = $this->page('Haushalt', 5);

		self::assertCount(3, $page['entries']);
		self::assertFalse($page['isPaginated']);
		self::assertSame([0, 20], array_column($this->pages, 'offset'));
	}

	public function testAtMostThreeRoundsAreAsked(): void {
		$this->hits = $this->marks(200);
		foreach (array_keys($this->readable) as $id) {
			$this->file($id, 'Fremd ' . $id . '.mp4', false);
		}

		$page = $this->page('Haushalt', 5);

		self::assertSame([], $page['entries']);
		self::assertFalse($page['isPaginated']);
		self::assertSame([0, 20, 40], array_column($this->pages, 'offset'));
	}
}
