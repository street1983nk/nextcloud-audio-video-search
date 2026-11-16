<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Search\Provider;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\DB\IResult;
use OCP\DB\QueryBuilder\ICompositeExpression;
use OCP\DB\QueryBuilder\IExpressionBuilder;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IMimeTypeDetector;
use OCP\Files\IRootFolder;
use OCP\Files\Storage\ISharedStorage;
use OCP\IAppConfig;
use OCP\IConfig;
use OCP\IDBConnection;
use OCP\IL10N;
use OCP\IURLGenerator;
use OCP\IUser;
use OCP\IUserManager;
use OCP\IUserSession;
use OCP\Search\IFilter;
use OCP\Search\ISearchQuery;
use OCP\Share\IAttributes;
use OCP\Share\IShare;
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

	/** @var list<int> the files a share row ties to the person of the filter */
	private array $sharedFileIds = [];

	/** @var list<list<int>> the ids of every executed share query, one band per query */
	private array $shareBands = [];

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
		$this->sharedFileIds = [];
		$this->shareBands = [];
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

		$db = $this->createMock(IDBConnection::class);
		$db->method('getQueryBuilder')->willReturnCallback(fn (): IQueryBuilder => $this->shareQueryBuilder());

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
			$db,
		);
	}

	/**
	 * The database of the person filter: it records the band of every executed
	 * query and answers with the share rows of $sharedFileIds. Whether the
	 * conditions mean what Files means is judged in SearchFiltersTest; here
	 * the questions are who was asked, how often, and what came of it.
	 */
	private function shareQueryBuilder(): IQueryBuilder {
		$band = null;

		$qb = $this->createMock(IQueryBuilder::class);
		$expr = $this->createMock(IExpressionBuilder::class);
		$expr->method('eq')->willReturn('eq');
		$expr->method('in')->willReturn('in');
		$expr->method('orX')->willReturnCallback(fn (): ICompositeExpression => $this->createMock(ICompositeExpression::class));
		$expr->method('andX')->willReturnCallback(fn (): ICompositeExpression => $this->createMock(ICompositeExpression::class));
		$qb->method('expr')->willReturn($expr);
		$qb->method('select')->willReturnSelf();
		$qb->method('from')->willReturnSelf();
		$qb->method('where')->willReturnSelf();
		$qb->method('andWhere')->willReturnSelf();
		$qb->method('createNamedParameter')->willReturnCallback(static function (mixed $value, mixed $type = null) use (&$band): string {
			if ($type === IQueryBuilder::PARAM_INT_ARRAY && is_array($value)) {
				$band = array_values($value);
			}

			return ':p';
		});
		$qb->method('executeQuery')->willReturnCallback(function () use (&$band): IResult {
			self::assertIsArray($band, 'every share query carries its ids as one bound int array');
			$this->shareBands[] = $band;
			$rows = [];
			foreach ($band as $fileId) {
				if (in_array($fileId, $this->sharedFileIds, true)) {
					$rows[] = ['file_source' => (string)$fileId];
				}
			}

			$result = $this->createMock(IResult::class);
			$result->method('fetch')->willReturnCallback(static function () use (&$rows): mixed {
				return array_shift($rows) ?? false;
			});
			$result->method('closeCursor')->willReturn(true);

			return $result;
		});

		return $qb;
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

	/** @param array<string, mixed> $filters filter name to the value its get() returns */
	private function query(string $term, int $limit = 5, int|string|null $cursor = null, array $filters = []): ISearchQuery&MockObject {
		$query = $this->createMock(ISearchQuery::class);
		$query->method('getTerm')->willReturn($term);
		$query->method('getLimit')->willReturn($limit);
		$query->method('getCursor')->willReturn($cursor);
		$query->method('getRoute')->willReturn('files.view.index');
		$query->method('getFilter')->willReturnCallback(function (string $name) use ($filters): ?IFilter {
			if (!array_key_exists($name, $filters)) {
				return null;
			}
			$filter = $this->createMock(IFilter::class);
			$filter->method('get')->willReturn($filters[$name]);

			return $filter;
		});

		return $query;
	}

	/** The person of the filter, an account that is not the searching alice. */
	private function person(string $uid): IUser&MockObject {
		$person = $this->createMock(IUser::class);
		$person->method('getUID')->willReturn($uid);

		return $person;
	}

	private function file(int $id, string $name, bool $readable = true, int $mtime = 1_700_000_000): File&MockObject {
		$file = $this->createMock(File::class);
		$file->method('getId')->willReturn($id);
		$file->method('getName')->willReturn($name);
		$file->method('getPath')->willReturn('/alice/files/Sitzungen/' . $name);
		$file->method('getMimetype')->willReturn('video/mp4');
		$file->method('isReadable')->willReturn($readable);
		$file->method('getMTime')->willReturn($mtime);
		$this->readable[$id] = $file;

		return $file;
	}

	/**
	 * The entries of one search as plain arrays.
	 *
	 * @param array<string, mixed> $filters
	 * @return list<array<string, mixed>>
	 */
	private function entries(string $term = 'Haushalt', array $filters = []): array {
		return $this->page($term, 5, null, $filters)['entries'];
	}

	/**
	 * One whole answer: the entries as plain arrays, isPaginated and the cursor.
	 *
	 * @param array<string, mixed> $filters
	 * @return array{entries: list<array<string, mixed>>, isPaginated: bool, cursor: mixed}
	 */
	private function page(string $term = 'Haushalt', int $limit = 5, int|string|null $cursor = null, array $filters = []): array {
		$result = $this->provider()->search($this->user(), $this->query($term, $limit, $cursor, $filters))->jsonSerialize();
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

	public function testExactlyTheFourCoreFiltersAreSupported(): void {
		$provider = $this->provider();

		self::assertSame(
			[IFilter::BUILTIN_TERM, IFilter::BUILTIN_SINCE, IFilter::BUILTIN_UNTIL, IFilter::BUILTIN_PERSON],
			$provider->getSupportedFilters(),
		);
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

	// -- the filters of the dialog (plan 04-02, SRCH-06, SRCH-04) ----------------

	public function testWithoutAFilterTheShareTableIsNeverAsked(): void {
		$this->file(11, 'Sitzung.mp4');
		$this->sharedFileIds = [11];
		$this->hits = [self::hit(11, 1000)];

		self::assertCount(1, $this->entries());
		self::assertSame([], $this->shareBands);
	}

	public function testSinceSkipsAnOlderFileAndThePageFillsFromLaterProposals(): void {
		$this->file(11, 'Alt.mp4', true, 999);
		$this->file(12, 'Genau.mp4', true, 1000);
		$this->file(13, 'Neuer.mp4', true, 2000);
		$this->hits = [self::hit(11, 1000), self::hit(12, 2000), self::hit(13, 3000)];

		$page = $this->page('Haushalt', 2, null, [IFilter::BUILTIN_SINCE => new \DateTimeImmutable('@1000')]);

		self::assertSame(['Genau.mp4', 'Neuer.mp4'], array_column($page['entries'], 'title'));
		self::assertFalse($page['isPaginated']);
	}

	public function testUntilIsInclusiveAtTheBoundarySecond(): void {
		$this->file(11, 'Genau.mp4', true, 2000);
		$this->file(12, 'Danach.mp4', true, 2001);
		$this->hits = [self::hit(11, 1000), self::hit(12, 2000)];

		$entries = $this->entries('Haushalt', [IFilter::BUILTIN_UNTIL => new \DateTimeImmutable('@2000')]);

		self::assertSame(['Genau.mp4'], array_column($entries, 'title'));
	}

	public function testThePersonFilterDropsANeverSharedFile(): void {
		$this->file(11, 'Geteilt.mp4');
		$this->file(12, 'Privat.mp4');
		$this->sharedFileIds = [11];
		$this->hits = [self::hit(11, 1000), self::hit(12, 2000)];

		$entries = $this->entries('Haushalt', [IFilter::BUILTIN_PERSON => $this->person('bob')]);

		self::assertSame(['Geteilt.mp4'], array_column($entries, 'title'));
	}

	public function testOneShareQueryAnswersAllConfirmedCandidatesOfARound(): void {
		$this->sharedFileIds = [11, 12];
		$this->hits = $this->marks(6);

		$entries = $this->entries('Haushalt', [IFilter::BUILTIN_PERSON => $this->person('bob')]);

		self::assertCount(5, $entries);
		self::assertSame([[11, 12]], $this->shareBands);
	}

	public function testASecondRoundAsksOnlyAboutFilesNotAnsweredYet(): void {
		// Round 1 carries the files 11 to 17, round 2 the files 17 to 24; only
		// file 17 is shared, so its three marks are the whole yield and the
		// second query names only the seven files the first one did not.
		$this->sharedFileIds = [17];
		$this->hits = $this->marks(40);

		$entries = $this->entries('Haushalt', [IFilter::BUILTIN_PERSON => $this->person('bob')]);

		self::assertSame(array_fill(0, 3, 'Sitzung 17.mp4'), array_column($entries, 'title'));
		self::assertSame([[11, 12, 13, 14, 15, 16, 17], [18, 19, 20, 21, 22, 23, 24]], $this->shareBands);
	}

	public function testAnExcludedOrUnreadableFileNeverReachesTheShareQuestion(): void {
		$this->file(11, 'Archiv.mp4');
		$this->file(12, 'Fremd.mp4', false);
		$this->file(13, 'Eigen.mp4');
		$this->excludedFiles = [11];
		$this->sharedFileIds = [11, 12, 13];
		$this->hits = [self::hit(11, 1000), self::hit(12, 2000), self::hit(13, 3000)];

		$entries = $this->entries('Haushalt', [IFilter::BUILTIN_PERSON => $this->person('bob')]);

		self::assertSame(['Eigen.mp4'], array_column($entries, 'title'));
		self::assertSame([[13]], $this->shareBands);
	}

	public function testAFileInAShareWithoutDownloadStillGivesAHit(): void {
		// SRCH-04: search yes. The download lock of a share blocks export and
		// sidecar, never the hit; this provider never asks the storage for it.
		$file = $this->file(11, 'Geteilt.mp4');
		$attributes = $this->createMock(IAttributes::class);
		$attributes->method('getAttribute')->willReturn(false);
		$share = $this->createMock(IShare::class);
		$share->method('getAttributes')->willReturn($attributes);
		$storage = $this->createMock(ISharedStorage::class);
		$storage->method('instanceOfStorage')->willReturnCallback(
			static fn (string $class): bool => $class === ISharedStorage::class,
		);
		$storage->method('getShare')->willReturn($share);
		$file->method('getStorage')->willReturn($storage);
		$this->sharedFileIds = [11];
		$this->hits = [self::hit(11, 754200)];

		$entries = $this->entries('Haushalt', [IFilter::BUILTIN_PERSON => $this->person('bob')]);

		self::assertSame(['Geteilt.mp4'], array_column($entries, 'title'));
	}

	public function testWithAFilterAtMostSixRoundsAreAsked(): void {
		$this->hits = $this->marks(200);
		foreach (array_keys($this->readable) as $id) {
			$this->file($id, 'Fremd ' . $id . '.mp4', false);
		}

		$page = $this->page('Haushalt', 5, null, [IFilter::BUILTIN_SINCE => new \DateTimeImmutable('@0')]);

		self::assertSame([], $page['entries']);
		self::assertFalse($page['isPaginated']);
		self::assertSame([0, 20, 40, 60, 80, 100], array_column($this->pages, 'offset'));
	}
}
