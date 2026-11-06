<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Search\Provider;
use OCA\AudioVideoSearch\Service\ExAppService;
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
 * The unified search entry: recheck, time mark, play link and the test result.
 *
 * The container is a double of ExAppService, the file system a double of the
 * user folder. Every hit the container proposes has to survive
 * FileAccess::readableFile in the folder of the searching user, and title and
 * path of an entry come out of that node, never out of the answer.
 */
#[CoversClass(Provider::class)]
final class ProviderTest extends TestCase {
	/** @var list<array{fileId:int,startMs:int,excerpt:string,sample:bool}>|null */
	private ?array $hits = [];

	private bool $debug = false;
	private bool $sampleVisible = false;
	private bool $allowed = true;
	private int $searchCalls = 0;

	/** @var array<int, File> the files alice may read, by id */
	private array $readable = [];

	/** @var list<array{string, array<string, mixed>}> */
	private array $links = [];

	protected function setUp(): void {
		parent::setUp();

		$this->hits = [];
		$this->debug = false;
		$this->sampleVisible = false;
		$this->allowed = true;
		$this->searchCalls = 0;
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
		$exApp->method('searchAllowed')->willReturnCallback(fn (): bool => $this->allowed);
		$exApp->method('search')->willReturnCallback(function (string $uid, string $term, int $limit): ?array {
			$this->searchCalls++;
			self::assertSame('alice', $uid);
			self::assertLessThanOrEqual(200, mb_strlen($term));
			self::assertSame(25, $limit);

			return $this->hits;
		});

		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturnCallback(fn (int $id): ?File => $this->readable[$id] ?? null);
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

		return new Provider(
			$l10n,
			$urls,
			$exApp,
			$root,
			new ReaderContext($session, $this->createMock(IUserManager::class)),
			$config,
			$appConfig,
			$mime,
			$this->createMock(LoggerInterface::class),
		);
	}

	private function user(): IUser&MockObject {
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn('alice');

		return $user;
	}

	private function query(string $term): ISearchQuery&MockObject {
		$query = $this->createMock(ISearchQuery::class);
		$query->method('getTerm')->willReturn($term);
		$query->method('getLimit')->willReturn(5);
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
		$result = $this->provider()->search($this->user(), $this->query($term))->jsonSerialize();
		$entries = [];
		foreach ($result['entries'] as $entry) {
			$entries[] = is_array($entry) ? $entry : $entry->jsonSerialize();
		}

		return $entries;
	}

	/** @return array{fileId:int,startMs:int,excerpt:string,sample:bool} */
	private static function hit(int $fileId, int $startMs, string $excerpt = 'der Haushalt wird beraten', bool $sample = false): array {
		return ['fileId' => $fileId, 'startMs' => $startMs, 'excerpt' => $excerpt, 'sample' => $sample];
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
}
