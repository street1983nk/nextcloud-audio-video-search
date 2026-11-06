<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Controller\PageController;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IRootFolder;
use OCP\Files\Storage\ISharedStorage;
use OCP\Files\Storage\IStorage;
use OCP\IAppConfig;
use OCP\IL10N;
use OCP\IRequest;
use OCP\IURLGenerator;
use OCP\IUser;
use OCP\IUserManager;
use OCP\IUserSession;
use OCP\Share\IAttributes;
use OCP\Share\IShare;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The playback page: recheck, start time, WebDAV address and the states.
 *
 * The file system is a double of the user folder, the container a double of
 * ExAppService. Whatever the address says, the page only plays a file that
 * FileAccess::readableFile confirms in the folder of the signed in user, and a
 * file it cannot confirm leaves no name and no path in the page parameters.
 */
#[CoversClass(PageController::class)]
final class PlayControllerTest extends TestCase {
	private const UID = 'alice';

	private string $uid = self::UID;
	private mixed $t = '';

	/** @var array<int, File> the files the user may read, by id */
	private array $readable = [];

	/** @var array{known:bool,excerpt:?string}|null */
	private ?array $excerpt = ['known' => true, 'excerpt' => 'der Haushalt wird beraten'];

	private bool $searchAllowed = true;
	private bool $viewWithoutDownload = true;

	/** @var list<array{string,int,int}> */
	private array $excerptCalls = [];

	protected function setUp(): void {
		parent::setUp();

		$this->uid = self::UID;
		$this->t = '';
		$this->readable = [];
		$this->excerpt = ['known' => true, 'excerpt' => 'der Haushalt wird beraten'];
		$this->searchAllowed = true;
		$this->viewWithoutDownload = true;
		$this->excerptCalls = [];
	}

	private function controller(): PageController {
		$request = $this->createMock(IRequest::class);
		$request->method('getParam')->willReturnCallback(
			fn (string $key, mixed $default = null): mixed => $key === 't' ? $this->t : $default,
		);

		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn($this->uid);
		$session = $this->createMock(IUserSession::class);
		$session->method('getUser')->willReturn($user);

		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturnCallback(fn (int $id): ?File => $this->readable[$id] ?? null);
		$prefix = '/' . $this->uid . '/files';
		$userFolder->method('getRelativePath')->willReturnCallback(
			static fn (string $path): string => substr($path, strlen($prefix)),
		);
		$root = $this->createMock(IRootFolder::class);
		$root->method('getUserFolder')->willReturnCallback(function (string $uid) use ($userFolder): Folder {
			self::assertSame($this->uid, $uid);

			return $userFolder;
		});

		$urls = $this->createMock(IURLGenerator::class);
		$urls->method('getWebroot')->willReturn('/nc');
		$urls->method('linkToRoute')->willReturnCallback(
			static fn (string $route, array $parameters = []): string => '/nc/route/' . $route . ($parameters === [] ? '' : '?' . http_build_query($parameters)),
		);

		$appConfig = $this->createMock(IAppConfig::class);
		$appConfig->method('getValueBool')->willReturnCallback(
			fn (string $app, string $key, bool $default = false): bool => $app === 'core' && $key === 'shareapi_allow_view_without_download'
				? $this->viewWithoutDownload
				: $default,
		);

		$l10n = $this->createMock(IL10N::class);
		$l10n->method('t')->willReturnCallback(
			static fn (string $text, array|string $parameters = []): string => vsprintf($text, (array)$parameters),
		);

		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('searchAllowed')->willReturnCallback(fn (): bool => $this->searchAllowed);
		$exApp->method('excerpt')->willReturnCallback(function (string $uid, int $fileId, int $startMs): ?array {
			$this->excerptCalls[] = [$uid, $fileId, $startMs];

			return $this->excerpt;
		});

		return new PageController(
			$request,
			$root,
			$session,
			$urls,
			$appConfig,
			$l10n,
			$exApp,
			new ReaderContext($session, $this->createMock(IUserManager::class)),
			$this->createMock(LoggerInterface::class),
		);
	}

	private function file(int $id, string $relativePath, string $mime = 'video/webm', ?IStorage $storage = null, bool $readable = true): File&MockObject {
		$file = $this->createMock(File::class);
		$file->method('getId')->willReturn($id);
		$file->method('getName')->willReturn(basename($relativePath));
		$file->method('getPath')->willReturn('/' . $this->uid . '/files/' . $relativePath);
		$file->method('getMimetype')->willReturn($mime);
		$file->method('isReadable')->willReturn($readable);
		if ($storage === null) {
			$storage = $this->createMock(IStorage::class);
			$storage->method('instanceOfStorage')->willReturn(false);
		}
		$file->method('getStorage')->willReturn($storage);
		$this->readable[$id] = $file;

		return $file;
	}

	/** A received share whose download switch is set to $download (null: not set). */
	private function sharedStorage(?bool $download): ISharedStorage&MockObject {
		$attributes = $this->createMock(IAttributes::class);
		$attributes->method('getAttribute')->willReturnCallback(
			static fn (string $scope, string $key): ?bool => $scope === 'permissions' && $key === 'download' ? $download : null,
		);
		$share = $this->createMock(IShare::class);
		$share->method('getAttributes')->willReturn($attributes);

		$storage = $this->createMock(ISharedStorage::class);
		$storage->method('instanceOfStorage')->willReturnCallback(
			static fn (string $class): bool => $class === ISharedStorage::class,
		);
		$storage->method('getShare')->willReturn($share);

		return $storage;
	}

	/** @return array<string, mixed> */
	private function play(int $fileId): array {
		return $this->response($fileId)->getParams();
	}

	private function response(int $fileId): TemplateResponse {
		return $this->controller()->play($fileId);
	}

	// -- the start time -----------------------------------------------------------

	public function testAStartTimeInSecondsBecomesMillisecondsAndAClock(): void {
		$this->file(7, 'Sitzung.webm');
		$this->t = '42.0';

		$params = $this->play(7);

		self::assertSame('ready', $params['state']);
		self::assertSame('42.0', $params['startSeconds']);
		self::assertSame('0:42', $params['startClock']);
		self::assertSame('PT42S', $params['startIso']);
		self::assertSame([[self::UID, 7, 42000]], $this->excerptCalls);
	}

	public function testFractionsAreKeptToMillisecondsAndShownCutToOneDecimal(): void {
		$this->file(7, 'Sitzung.webm');
		$this->t = '754.25';

		$params = $this->play(7);

		self::assertSame([[self::UID, 7, 754250]], $this->excerptCalls);
		self::assertSame('754.2', $params['startSeconds']);
		self::assertSame('12:34', $params['startClock']);
		self::assertSame('PT12M34S', $params['startIso']);
	}

	/** @return array<string, array{mixed}> */
	public static function invalidStarts(): array {
		return [
			'letters' => ['abc'],
			'negative' => ['-1'],
			'beyond a day' => ['86401'],
			'exponent' => ['1e3'],
			'empty' => [''],
			'too many decimals' => ['1.2345'],
			'not a string' => [['42']],
		];
	}

	#[DataProvider('invalidStarts')]
	public function testAnInvalidStartIsZeroWithoutAnError(mixed $raw): void {
		$this->file(7, 'Sitzung.webm');
		$this->t = $raw;

		$response = $this->response(7);
		$params = $response->getParams();

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame('ready', $params['state']);
		self::assertSame('0.0', $params['startSeconds']);
		self::assertSame('0:00', $params['startClock']);
		self::assertSame('PT0S', $params['startIso']);
		self::assertSame([[self::UID, 7, 0]], $this->excerptCalls);
	}

	public function testStartMsReadsTheBoundariesExactly(): void {
		self::assertSame(86400000, PageController::startMs('86400'));
		self::assertSame(0, PageController::startMs('86400.001'));
		self::assertSame(5, PageController::startMs('0.005'));
		self::assertSame(1500, PageController::startMs('1.5'));
		self::assertSame(0, PageController::startMs(' 1'));
		self::assertSame(0, PageController::startMs("1\n"));
	}

	// -- the address of the medium -------------------------------------------------

	public function testTheSourceIsTheEncodedWebDavAddressWithTheFragmentOnlyAfterZero(): void {
		$this->uid = 'max mustermann@example.org';
		$this->file(9, 'Team A/Sitzung #1.webm');
		$this->t = '42.0';

		$params = $this->play(9);

		$expected = '/nc/remote.php/dav/files/max%20mustermann%40example.org/Team%20A/Sitzung%20%231.webm';
		self::assertSame($expected, $params['src']);
		self::assertSame($expected . '#t=42.0', $params['mediaSrc']);

		$this->excerptCalls = [];
		$this->t = '';
		$params = $this->play(9);
		self::assertSame($expected, $params['mediaSrc']);
	}

	public function testVideoAndAudioPickTheirElement(): void {
		$this->file(1, 'Film.webm', 'video/webm');
		$this->file(2, 'Interview.ogg', 'audio/ogg');

		self::assertSame('video', $this->play(1)['mediaTag']);
		self::assertSame('audio', $this->play(2)['mediaTag']);
	}

	public function testTheNameIsTheHeadingAndTheDocumentTitle(): void {
		$this->file(7, 'Sitzung.webm');

		$params = $this->play(7);

		self::assertSame('Sitzung.webm', $params['fileName']);
		self::assertSame('Sitzung.webm', $params['pageTitle']);
		self::assertSame('/nc/route/files.view.showFile?fileid=7', $params['filesUrl']);
		self::assertTrue($params['downloadAllowed']);
	}

	public function testTheResponseIsTheUserLayoutOfThisApp(): void {
		$this->file(7, 'Sitzung.webm');

		$response = $this->response(7);

		self::assertSame(Application::APP_ID, $response->getApp());
		self::assertSame('play', $response->getTemplateName());
		self::assertSame(TemplateResponse::RENDER_AS_USER, $response->getRenderAs());
	}

	// -- what may not be shown ------------------------------------------------------

	/** @return array<string, array{string}> */
	public static function unreadableCases(): array {
		return [
			'missing or foreign' => ['missing'],
			'not readable' => ['closed'],
		];
	}

	#[DataProvider('unreadableCases')]
	public function testAFileTheUserCannotReadIsA404WithoutNameOrPath(string $case): void {
		if ($case === 'closed') {
			$this->file(5, 'Geheim/Personalsitzung.webm', readable: false);
		}
		$this->t = '42.0';

		$response = $this->response(5);
		$params = $response->getParams();

		self::assertSame(Http::STATUS_NOT_FOUND, $response->getStatus());
		self::assertSame('unavailable', $params['state']);
		self::assertSame('', $params['fileName']);
		self::assertSame('', $params['src']);
		self::assertSame('', $params['mediaSrc']);
		self::assertSame('Playback', $params['pageTitle']);
		self::assertSame('/nc/route/files.view.index', $params['filesUrl']);
		$flat = json_encode($params, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
		self::assertStringNotContainsString('Personalsitzung', $flat);
		self::assertStringNotContainsString('Geheim', $flat);
		self::assertSame([], $this->excerptCalls);
	}

	public function testAReadableFileThatIsNoMediumIsNamedButNotPlayed(): void {
		$this->file(3, 'Protokoll.txt', 'text/plain');

		$response = $this->response(3);
		$params = $response->getParams();

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame('not_media', $params['state']);
		self::assertSame('Protokoll.txt', $params['fileName']);
		self::assertSame('', $params['src']);
		self::assertSame([], $this->excerptCalls);
	}

	// -- shares without download ----------------------------------------------------

	public function testAShareWithoutDownloadIsBlockedWhenViewingIsNotAllowedEither(): void {
		$this->file(4, 'Geteilt/Sitzung.webm', storage: $this->sharedStorage(false));
		$this->viewWithoutDownload = false;

		$response = $this->response(4);
		$params = $response->getParams();

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame('download_blocked', $params['state']);
		self::assertSame('Sitzung.webm', $params['fileName']);
		self::assertSame('', $params['src']);
		self::assertSame('', $params['mediaSrc']);
		self::assertFalse($params['downloadAllowed']);
		self::assertSame([], $this->excerptCalls);
	}

	public function testAShareWithoutDownloadPlaysWhenViewingIsAllowedButOffersNoDownload(): void {
		$this->file(4, 'Geteilt/Sitzung.webm', storage: $this->sharedStorage(false));
		$this->viewWithoutDownload = true;

		$params = $this->play(4);

		self::assertSame('ready', $params['state']);
		self::assertNotSame('', $params['src']);
		self::assertFalse($params['downloadAllowed']);
	}

	public function testAShareWithDownloadPlaysNormally(): void {
		$this->file(4, 'Geteilt/Sitzung.webm', storage: $this->sharedStorage(null));
		$this->viewWithoutDownload = false;

		$params = $this->play(4);

		self::assertSame('ready', $params['state']);
		self::assertTrue($params['downloadAllowed']);
	}

	// -- the excerpt ------------------------------------------------------------------

	public function testTheExcerptStates(): void {
		$this->file(7, 'Sitzung.webm');

		$params = $this->play(7);
		self::assertSame('ok', $params['excerptState']);
		self::assertSame('der Haushalt wird beraten', $params['excerpt']);

		$this->excerpt = ['known' => false, 'excerpt' => null];
		$params = $this->play(7);
		self::assertSame('none', $params['excerptState']);
		self::assertSame('', $params['excerpt']);

		$this->excerpt = null;
		$params = $this->play(7);
		self::assertSame('unavailable', $params['excerptState']);
		self::assertSame('', $params['excerpt']);
	}

	public function testADriftOnRecordDoesNotAskTheContainer(): void {
		$this->file(7, 'Sitzung.webm');
		$this->searchAllowed = false;

		$params = $this->play(7);

		self::assertSame('unavailable', $params['excerptState']);
		self::assertSame([], $this->excerptCalls);
		self::assertSame('ready', $params['state']);
	}

	// -- the route ----------------------------------------------------------------------

	public function testTheRouteNeedsASessionButNoAdminAndNoToken(): void {
		$method = new \ReflectionMethod(PageController::class, 'play');
		$names = array_map(static fn (\ReflectionAttribute $attribute): string => $attribute->getName(), $method->getAttributes());

		self::assertContains(\OCP\AppFramework\Http\Attribute\NoAdminRequired::class, $names);
		self::assertContains(\OCP\AppFramework\Http\Attribute\NoCSRFRequired::class, $names);
		self::assertContains(\OCP\AppFramework\Http\Attribute\FrontpageRoute::class, $names);
		self::assertNotContains(\OCP\AppFramework\Http\Attribute\PublicPage::class, $names);
		self::assertNotContains(\OCP\AppFramework\Http\Attribute\ExAppRequired::class, $names);

		foreach ($method->getAttributes(\OCP\AppFramework\Http\Attribute\FrontpageRoute::class) as $route) {
			$arguments = $route->getArguments();
			self::assertSame('GET', $arguments['verb']);
			self::assertSame('/play/{fileId}', $arguments['url']);
			self::assertSame(['fileId' => '\d+'], $arguments['requirements']);
		}
	}
}
