<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Controller\ExportController;
use OCA\AudioVideoSearch\Service\DownloadPolicy;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCA\AudioVideoSearch\Service\SidecarWriter;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataDisplayResponse;
use OCP\AppFramework\Http\DataDownloadResponse;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\Files\Cache\ICache;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IRootFolder;
use OCP\Files\NotPermittedException;
use OCP\Files\Storage\ISharedStorage;
use OCP\Files\Storage\IStorage;
use OCP\IL10N;
use OCP\IRequest;
use OCP\IURLGenerator;
use OCP\IUser;
use OCP\IUserManager;
use OCP\IUserSession;
use OCP\Lock\ILockingProvider;
use OCP\Lock\LockedException;
use OCP\Share\IAttributes;
use OCP\Share\IShare;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The export routes: the block before the exclusions and before the
 * container, the error pages that cannot be told apart, and the three file
 * bodies. The container is a double of ExAppService, the download policy is
 * the real service over doubled storages.
 */
#[CoversClass(ExportController::class)]
final class ExportControllerTest extends TestCase {
	private const UID = 'alice';

	private mixed $t = '';

	/** @var array<int, File> the files the user may read, by id */
	private array $readable = [];

	/** @var array{known:bool,partial?:bool,untilMs?:int,language?:string,body?:string}|null */
	private ?array $export = null;

	/** Set where the container must not be asked at all: export() then expects never(). */
	private bool $containerNeverAsked = false;

	/** Set where the exclusions must not be asked at all (combined block cases). */
	private bool $exclusionsNeverAsked = false;

	private bool $searchAllowed = true;

	/** @var list<array{string,int,string}> */
	private array $exportCalls = [];

	/** @var list<string> the users a rule of the admin excludes */
	private array $excludedUsers = [];

	/** @var list<int> the files a rule of the admin excludes */
	private array $excludedFiles = [];

	private bool $exclusionsFail = false;

	/** @var list<string> every log line with its context, as one text */
	private array $logged = [];

	/** @var array<string, string> the sidecar files of the parent folder, name to content */
	private array $sidecars = [];

	private bool $creatable = true;

	private bool $lockTaken = false;

	private bool $storageRefuses = false;

	private int $newFileCalls = 0;

	protected function setUp(): void {
		parent::setUp();

		$this->t = '';
		$this->readable = [];
		$this->export = self::known();
		$this->containerNeverAsked = false;
		$this->exclusionsNeverAsked = false;
		$this->searchAllowed = true;
		$this->exportCalls = [];
		$this->excludedUsers = [];
		$this->excludedFiles = [];
		$this->exclusionsFail = false;
		$this->logged = [];
		$this->sidecars = [];
		$this->creatable = true;
		$this->lockTaken = false;
		$this->storageRefuses = false;
		$this->newFileCalls = 0;
	}

	private function controller(): ExportController {
		$request = $this->createMock(IRequest::class);
		$request->method('getParam')->willReturnCallback(
			fn (string $key, mixed $default = null): mixed => $key === 't' ? $this->t : $default,
		);

		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn(self::UID);
		$session = $this->createMock(IUserSession::class);
		$session->method('getUser')->willReturn($user);

		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturnCallback(fn (int $id): ?File => $this->readable[$id] ?? null);
		$root = $this->createMock(IRootFolder::class);
		$root->method('getUserFolder')->willReturn($userFolder);

		$urls = $this->createMock(IURLGenerator::class);
		$urls->method('linkToRoute')->willReturnCallback(
			static fn (string $route, array $parameters = []): string => '/nc/route/' . $route . ($parameters === [] ? '' : '?' . http_build_query($parameters)),
		);

		$l10n = $this->createMock(IL10N::class);
		$l10n->method('t')->willReturnCallback(
			static fn (string $text, array|string $parameters = []): string => vsprintf($text, (array)$parameters),
		);

		$exApp = $this->createMock(ExAppService::class);
		$exApp->method('searchAllowed')->willReturnCallback(fn (): bool => $this->searchAllowed);
		$exApp->expects($this->containerNeverAsked ? self::never() : self::any())
			->method('export')
			->willReturnCallback(function (string $uid, int $fileId, string $format): ?array {
				$this->exportCalls[] = [$uid, $fileId, $format];

				return $this->export;
			});

		$exclusions = $this->createMock(ExclusionService::class);
		$silence = $this->exclusionsNeverAsked;
		$exclusions->expects($silence ? self::never() : self::any())->method('reload');
		$exclusions->expects($silence ? self::never() : self::any())
			->method('isExcludedUser')
			->willReturnCallback(function (string $uid): bool {
				if ($this->exclusionsFail) {
					throw new \RuntimeException('the rules are gone for alice and Sitzung.webm');
				}

				return in_array($uid, $this->excludedUsers, true);
			});
		$exclusions->expects($silence ? self::never() : self::any())
			->method('isExcludedFile')
			->willReturnCallback(fn (int $fileId): bool => in_array($fileId, $this->excludedFiles, true));

		$logger = $this->logger();

		$locking = $this->createMock(ILockingProvider::class);
		$locking->method('acquireLock')->willReturnCallback(function (string $path, int $type): void {
			if ($this->lockTaken) {
				throw new LockedException($path);
			}
		});

		return new ExportController(
			$request,
			$root,
			$session,
			$urls,
			$l10n,
			$exApp,
			new ReaderContext($session, $this->createMock(IUserManager::class)),
			$logger,
			$exclusions,
			new DownloadPolicy($logger),
			new SidecarWriter($locking, $logger),
		);
	}

	/** A logger that keeps every line with its context as one text. */
	private function logger(): LoggerInterface&MockObject {
		$logger = $this->createMock(LoggerInterface::class);
		foreach (['debug', 'info', 'notice', 'warning', 'error'] as $level) {
			$logger->method($level)->willReturnCallback(function (string|\Stringable $message, array $context = []): void {
				$this->logged[] = $message . ' ' . json_encode($context);
			});
		}

		return $logger;
	}

	/**
	 * An answer of the container about a file it may speak about, in the
	 * shape ExAppService::export hands on.
	 *
	 * @param array<string, mixed> $fields
	 * @return array{known:bool,partial:bool,untilMs:int,language:string,body:string}
	 */
	private static function known(array $fields = []): array {
		return $fields + [
			'known' => true,
			'partial' => false,
			'untilMs' => 0,
			'language' => 'de',
			'body' => "WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\nder Haushalt wird beraten\n",
		];
	}

	private function file(int $id, string $name, ?IStorage $storage = null): File&MockObject {
		$file = $this->createMock(File::class);
		$file->method('getId')->willReturn($id);
		$file->method('getName')->willReturn($name);
		$file->method('isReadable')->willReturn(true);
		if ($storage === null) {
			$storage = $this->createMock(IStorage::class);
			$storage->method('instanceOfStorage')->willReturn(false);
		}
		$file->method('getStorage')->willReturn($storage);
		$file->method('getParent')->willReturn($this->parentFolder());
		$this->readable[$id] = $file;

		return $file;
	}

	/**
	 * The folder of the medium, a double whose files live in $this->sidecars,
	 * so they survive across controller instances within one test.
	 */
	private function parentFolder(): Folder&MockObject {
		$cache = $this->createMock(ICache::class);
		$cache->method('getNumericStorageId')->willReturn(42);
		$parentStorage = $this->createMock(IStorage::class);
		$parentStorage->method('getCache')->willReturn($cache);

		$parent = $this->createMock(Folder::class);
		$parent->method('getStorage')->willReturn($parentStorage);
		$parent->method('getInternalPath')->willReturn('files/Aufnahmen');
		$parent->method('isCreatable')->willReturnCallback(fn (): bool => $this->creatable);
		$parent->method('nodeExists')->willReturnCallback(
			fn (string $name): bool => array_key_exists($name, $this->sidecars),
		);
		$parent->method('newFile')->willReturnCallback(function (string $name, mixed $content = null): File {
			$this->newFileCalls++;
			if ($this->storageRefuses) {
				throw new NotPermittedException('no create permission');
			}
			$this->sidecars[$name] = (string)$content;

			return $this->createMock(File::class);
		});

		return $parent;
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

	/** A share whose attributes cannot be read: the policy answers UNKNOWN. */
	private function brokenStorage(): ISharedStorage&MockObject {
		$storage = $this->createMock(ISharedStorage::class);
		$storage->method('instanceOfStorage')->willReturnCallback(
			static fn (string $class): bool => $class === ISharedStorage::class,
		);
		$storage->method('getShare')->willThrowException(new \RuntimeException('share table away'));

		return $storage;
	}

	/**
	 * What could tell two pages apart: the status and every parameter.
	 *
	 * @return array{status: int, app: string, template: string, renderAs: string, params: array<string, mixed>}
	 */
	private static function answer(TemplateResponse $response): array {
		return [
			'status' => $response->getStatus(),
			'app' => $response->getApp(),
			'template' => $response->getTemplateName(),
			'renderAs' => $response->getRenderAs(),
			'params' => $response->getParams(),
		];
	}

	/** The page as the server renders it, with its status: the byte for byte view. */
	private static function page(TemplateResponse $response): string {
		$blank = new TemplateResponse($response->getApp(), $response->getTemplateName(), $response->getParams(), TemplateResponse::RENDER_AS_BLANK);

		return $response->getStatus() . "\n" . $blank->render();
	}

	/** What could tell two track answers apart: status, headers and body. */
	private static function trackAnswer(DataDisplayResponse $response): string {
		return $response->getStatus() . "\n" . json_encode($response->getHeaders()) . "\n" . $response->render();
	}

	private function download(int $fileId, string $format = 'vtt'): TemplateResponse|DataDownloadResponse {
		return $this->controller()->download($fileId, $format);
	}

	private function errorPageOf(int $fileId, string $format = 'vtt'): TemplateResponse {
		$response = $this->download($fileId, $format);
		self::assertInstanceOf(TemplateResponse::class, $response);

		return $response;
	}

	// -- the block comes first (SRCH-04, T-04-29, T-04-29a) --------------------------

	public function testABlockedShareGetsA403PageAndTheContainerIsNeverAsked(): void {
		$this->file(7, 'Sitzung.webm', $this->sharedStorage(false));
		$this->containerNeverAsked = true;

		$response = $this->errorPageOf(7);

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame('export_error', $response->getTemplateName());
		self::assertSame(ExportController::CASE_BLOCKED, $response->getParams()['case']);
		self::assertSame([], $this->exportCalls);
	}

	public function testAnAttributeNobodyCanReadBlocksTheExportWithTheSame403(): void {
		$this->file(7, 'Sitzung.webm', $this->brokenStorage());
		$this->containerNeverAsked = true;

		$response = $this->errorPageOf(7);

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame(ExportController::CASE_BLOCKED, $response->getParams()['case']);
		self::assertSame([], $this->exportCalls);
	}

	public function testABlockedAndExcludedFileAnswersByteForByteLikeABlockedOneAndTheExclusionsAreNeverAsked(): void {
		$this->t = '42.0';
		$this->file(7, 'Sitzung.webm', $this->sharedStorage(false));
		$this->containerNeverAsked = true;

		// The reference: blocked without any exclusion.
		$blockedOnly = $this->errorPageOf(7);

		$this->excludedFiles = [7];
		$this->exclusionsNeverAsked = true;
		$blockedAndExcluded = $this->errorPageOf(7);

		self::assertSame(self::answer($blockedOnly), self::answer($blockedAndExcluded));
		self::assertSame(self::page($blockedOnly), self::page($blockedAndExcluded));
		self::assertSame(Http::STATUS_FORBIDDEN, $blockedAndExcluded->getStatus());

		// The excluded user case, same verdict.
		$this->excludedFiles = [];
		$this->excludedUsers = [self::UID];
		self::assertSame(self::answer($blockedOnly), self::answer($this->errorPageOf(7)));
	}

	public function testAnUnknownAttributeOnAnExcludedFileIsStillThe403(): void {
		$this->file(7, 'Sitzung.webm', $this->brokenStorage());
		$this->excludedFiles = [7];
		$this->containerNeverAsked = true;
		$this->exclusionsNeverAsked = true;

		$response = $this->errorPageOf(7);

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame(ExportController::CASE_BLOCKED, $response->getParams()['case']);
	}

	public function testTheTrackOfABlockedAndExcludedFileAnswersLikeABlockedOneWithoutAskingAnybody(): void {
		$this->file(7, 'Sitzung.webm', $this->sharedStorage(false));
		$this->containerNeverAsked = true;

		$response = $this->controller()->track(7);
		self::assertInstanceOf(DataDisplayResponse::class, $response);
		$blockedOnly = self::trackAnswer($response);

		$this->excludedFiles = [7];
		$this->exclusionsNeverAsked = true;
		$both = $this->controller()->track(7);

		self::assertSame($blockedOnly, self::trackAnswer($both));
		self::assertSame(Http::STATUS_FORBIDDEN, $both->getStatus());
		self::assertSame('', $both->render());
		self::assertSame([], $this->exportCalls);
	}

	// -- the 404 family (X4 leak rule) ------------------------------------------------

	public function testAnExcludedFileAndAFileTheContainerDoesNotKnowGetByteForByteTheSamePage(): void {
		$this->t = '42.0';
		$this->file(7, 'Sitzung.webm');

		// The reference: the container answers known false.
		$this->export = ['known' => false];
		$unknown = $this->errorPageOf(7);
		self::assertSame(Http::STATUS_NOT_FOUND, $unknown->getStatus());

		// Positive control: a readable transcript renders another page.
		$this->export = self::known();
		self::assertInstanceOf(DataDownloadResponse::class, $this->download(7));

		// The probe: an excluded file, the container is never asked.
		$this->excludedFiles = [7];
		$this->containerNeverAsked = true;
		$excluded = $this->errorPageOf(7);

		self::assertSame(self::answer($unknown), self::answer($excluded));
		self::assertSame(self::page($unknown), self::page($excluded));
		self::assertSame(ExportController::CASE_NONE, $excluded->getParams()['case']);
	}

	/** @return array<string, array{string}> */
	public static function exclusionKinds(): array {
		return [
			'excluded user' => ['user'],
			'excluded file' => ['file'],
			'question fails' => ['fails'],
		];
	}

	#[DataProvider('exclusionKinds')]
	public function testEveryKindOfExclusionEndsInThe404AndTheContainerIsNeverAsked(string $kind): void {
		$this->file(7, 'Sitzung.webm');
		match ($kind) {
			'user' => $this->excludedUsers = [self::UID],
			'file' => $this->excludedFiles = [7],
			'fails' => $this->exclusionsFail = true,
		};
		$this->containerNeverAsked = true;

		$response = $this->errorPageOf(7);

		self::assertSame(Http::STATUS_NOT_FOUND, $response->getStatus());
		self::assertSame(ExportController::CASE_NONE, $response->getParams()['case']);
		self::assertSame([], $this->exportCalls);
	}

	public function testAFileTheUserCannotReadIsA404WithoutNameOrPath(): void {
		$this->containerNeverAsked = true;
		$this->exclusionsNeverAsked = true;

		$response = $this->errorPageOf(5);

		self::assertSame(Http::STATUS_NOT_FOUND, $response->getStatus());
		self::assertSame(ExportController::CASE_UNAVAILABLE, $response->getParams()['case']);
		$flat = json_encode($response->getParams(), JSON_THROW_ON_ERROR);
		self::assertStringNotContainsString('Sitzung', $flat);
	}

	public function testADriftAndASilentContainerAreThe503(): void {
		$this->file(7, 'Sitzung.webm');
		$this->searchAllowed = false;
		$this->containerNeverAsked = true;
		$drift = $this->errorPageOf(7);
		self::assertSame(Http::STATUS_SERVICE_UNAVAILABLE, $drift->getStatus());
		self::assertSame(ExportController::CASE_UNREACHABLE, $drift->getParams()['case']);
		self::assertSame([], $this->exportCalls);

		$this->searchAllowed = true;
		$this->containerNeverAsked = false;
		$this->export = null;
		$silent = $this->errorPageOf(7);
		self::assertSame(Http::STATUS_SERVICE_UNAVAILABLE, $silent->getStatus());
		self::assertSame(self::answer($drift), self::answer($silent));
	}

	public function testTheWayBackCarriesTheFileIdAndAValidTimeMark(): void {
		$this->t = '42.0';
		$this->file(7, 'Sitzung.webm', $this->sharedStorage(false));
		self::assertSame(
			'/nc/route/audio_video_search.page.play?fileId=7&t=42.0',
			$this->errorPageOf(7)->getParams()['backUrl'],
		);

		$this->t = 'abc';
		self::assertSame(
			'/nc/route/audio_video_search.page.play?fileId=7',
			$this->errorPageOf(7)->getParams()['backUrl'],
		);
	}

	// -- the download itself (EXP-01, D-04-03, D-04-04) --------------------------------

	/** @return array<string, array{string, string}> */
	public static function mimeTypes(): array {
		return [
			'srt' => ['srt', 'application/x-subrip; charset=utf-8'],
			'vtt' => ['vtt', 'text/vtt; charset=utf-8'],
			'txt' => ['txt', 'text/plain; charset=utf-8'],
		];
	}

	#[DataProvider('mimeTypes')]
	public function testEveryFormatCarriesItsMediaTypeAndTheName(string $format, string $mime): void {
		$this->file(7, 'sitzung.mp4');
		$this->export = self::known(['language' => 'en']);

		$response = $this->download(7, $format);

		self::assertInstanceOf(DataDownloadResponse::class, $response);
		self::assertSame($mime, $response->getHeaders()['Content-Type']);
		self::assertStringContainsString('attachment', (string)$response->getHeaders()['Content-Disposition']);
		self::assertStringContainsString('sitzung.en.' . $format, (string)$response->getHeaders()['Content-Disposition']);
		self::assertSame([[self::UID, 7, $format]], $this->exportCalls);
	}

	/** @return array<string, array{string, string, string, string}> */
	public static function downloadNames(): array {
		return [
			'one extension' => ['sitzung.mp4', 'de', 'srt', 'sitzung.de.srt'],
			'several dots' => ['Übung.final.webm', 'fr', 'vtt', 'Uebung.final.fr.vtt'],
			'no dot' => ['mitschnitt', 'en', 'txt', 'mitschnitt.en.txt'],
			'leading dot only' => ['.versteckt', 'de', 'txt', '.versteckt.de.txt'],
			'control character stays' => ["Sitz\tung.webm", 'de', 'vtt', "Sitz\tung.de.vtt"],
			'decomposed umlaut' => ["U\u{0308}bung.mp4", 'de', 'srt', 'Uebung.de.srt'],
			'decomposed lowercase' => ["Ma\u{0308}rz.ogg", 'de', 'srt', 'Maerz.de.srt'],
			'all umlauts' => [
				'Äpfel Öl Über ärger öfter übel Straße.mp4',
				'de',
				'vtt',
				'Aepfel Oel Ueber aerger oefter uebel Strasse.de.vtt',
			],
			'capital sharp s' => ["GRO\u{1E9E}E.wav", 'de', 'txt', 'GROSSE.de.txt'],
			// Only umlauts and the sharp s are spelled out: every other letter,
			// Cyrillic and the microphone U+1F3A4 (an escape, never the
			// character in a tracked file) stay as they are.
			'other letters stay' => [
				"Caf\u{00E9} ni\u{00F1}o \u{041F}\u{0440}\u{0438}\u{0432}\u{0435}\u{0442} \u{1F3A4}.mp4",
				'fr',
				'srt',
				"Caf\u{00E9} ni\u{00F1}o \u{041F}\u{0440}\u{0438}\u{0432}\u{0435}\u{0442} \u{1F3A4}.fr.srt",
			],
		];
	}

	#[DataProvider('downloadNames')]
	public function testTheDownloadNameFollowsTheSidecarPattern(string $fileName, string $language, string $format, string $expected): void {
		self::assertSame($expected, ExportController::downloadName($fileName, $language, $format));
	}

	public function testTheSrtLeavesTheContainerBodyUntouched(): void {
		$srt = "1\n00:00:00,000 --> 00:00:02,000\nder Haushalt wird beraten\n";
		$this->file(7, 'Sitzung.webm');
		$this->export = self::known(['body' => $srt]);

		$response = $this->download(7, 'srt');

		self::assertInstanceOf(DataDownloadResponse::class, $response);
		self::assertSame($srt, $response->render());
	}

	public function testTheTxtCarriesTheNameTheNoticeAndForAPartialTranscriptTheTime(): void {
		$this->file(7, 'Sitzung.webm');
		$this->export = self::known(['body' => 'der Haushalt wird beraten']);
		$whole = $this->download(7, 'txt');
		self::assertInstanceOf(DataDownloadResponse::class, $whole);
		self::assertSame(
			"Sitzung.webm\n"
			. "Subtitle draft, created automatically and not reviewed.\n"
			. "\n"
			. 'der Haushalt wird beraten',
			$whole->render(),
		);

		$this->export = self::known(['body' => 'der Haushalt wird beraten', 'partial' => true, 'untilMs' => 754250]);
		$partial = $this->download(7, 'txt');
		self::assertInstanceOf(DataDownloadResponse::class, $partial);
		self::assertSame(
			"Sitzung.webm\n"
			. "Subtitle draft, created automatically and not reviewed.\n"
			. "Transcript up to 12:34, the file is still being processed.\n"
			. "\n"
			. 'der Haushalt wird beraten',
			$partial->render(),
		);
	}

	public function testControlCharactersInTheNameBecomeSpacesInTheTxtHead(): void {
		$this->file(7, "Sitz\tung.webm");
		$this->export = self::known(['body' => 'Text']);

		$response = $this->download(7, 'txt');

		self::assertInstanceOf(DataDownloadResponse::class, $response);
		self::assertStringStartsWith("Sitz ung.webm\n", $response->render());
		// The header carries the name too: the tab became a space there, so
		// the download is a download and not a server error.
		self::assertStringContainsString('Sitz ung.de.txt', (string)$response->getHeaders()['Content-Disposition']);
	}

	public function testTheDownloadNameSpellsOutTheUmlautAndTheTxtHeadKeepsTheRealName(): void {
		$this->file(7, 'S7-Übung.webm');
		$this->export = self::known(['body' => 'der Haushalt wird beraten']);

		foreach (['srt', 'vtt', 'txt'] as $format) {
			$response = $this->download(7, $format);
			self::assertInstanceOf(DataDownloadResponse::class, $response);
			$disposition = (string)$response->getHeaders()['Content-Disposition'];
			self::assertStringContainsString('S7-Uebung.de.' . $format, $disposition);
			self::assertStringNotContainsString('Übung', $disposition);
			self::assertStringNotContainsString(rawurlencode('Ü'), $disposition);
		}

		// The head of the TXT is content, not a file name: the real name of the recording.
		$txt = $this->download(7, 'txt');
		self::assertInstanceOf(DataDownloadResponse::class, $txt);
		self::assertStringStartsWith("S7-Übung.webm\n", $txt->render());
	}

	public function testTheAttachmentNameTurnsControlCharactersIntoSpacesAndKeepsTheRest(): void {
		self::assertSame('a b c d.de.vtt', ExportController::attachmentName("a\tb\x00c\x7Fd.de.vtt"));
		self::assertSame('Übung.final.fr.vtt', ExportController::attachmentName('Übung.final.fr.vtt'));
		// The sidecar name is not touched: it keeps the pattern of its medium.
		self::assertSame("Sitz\tung.de.vtt", ExportController::downloadName("Sitz\tung.webm", 'de', 'vtt'));
	}

	public function testTheVttCarriesTheNoticeAsANoteAndForAPartialTranscriptTheTime(): void {
		$cues = "1\n00:00:00.000 --> 00:00:02.000\nder Haushalt wird beraten\n";
		$this->file(7, 'Sitzung.webm');
		$this->export = self::known(['body' => "WEBVTT\n\n" . $cues]);
		$whole = $this->download(7, 'vtt');
		self::assertInstanceOf(DataDownloadResponse::class, $whole);
		self::assertSame(
			"WEBVTT\n\nNOTE\nSubtitle draft, created automatically and not reviewed.\n\n" . $cues,
			$whole->render(),
		);

		$this->export = self::known(['body' => "WEBVTT\n\n" . $cues, 'partial' => true, 'untilMs' => 60000]);
		$partial = $this->download(7, 'vtt');
		self::assertInstanceOf(DataDownloadResponse::class, $partial);
		self::assertSame(
			"WEBVTT\n\nNOTE\nSubtitle draft, created automatically and not reviewed.\n"
			. "Transcript up to 1:00, the file is still being processed.\n\n" . $cues,
			$partial->render(),
		);
	}

	public function testANoteLineThatWouldBreakTheBlockIsLeftOutAndLoggedWithTheFileIdOnly(): void {
		$lines = ['safe line', "broken --> line", "broken\nline"];

		self::assertSame("WEBVTT\n\nNOTE\nsafe line\n\ncue", ExportController::withNote("WEBVTT\n\ncue", ['safe line']));
		self::assertSame("WEBVTT\n\ncue", ExportController::withNote("WEBVTT\n\ncue", []));

		// Through the instance path: only the safe line survives.
		$this->file(7, 'Sitzung.webm');
		$method = new \ReflectionMethod(ExportController::class, 'noteSafe');
		$safe = $method->invoke($this->controller(), $lines, 7);
		self::assertSame(['safe line'], $safe);
		self::assertCount(2, $this->logged);
		self::assertStringContainsString('"fileId":7', $this->logged[0]);
		self::assertStringNotContainsString('broken', $this->logged[0]);
	}

	// -- the track (D-04-18) ------------------------------------------------------------

	public function testTheTrackIsTheVttWithTheNoteWithoutADisposition(): void {
		$cues = "1\n00:00:00.000 --> 00:00:02.000\nder Haushalt wird beraten\n";
		$this->file(7, 'Sitzung.webm');
		$this->export = self::known(['body' => "WEBVTT\n\n" . $cues]);

		$response = $this->controller()->track(7);

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame('text/vtt; charset=utf-8', $response->getHeaders()['Content-Type']);
		self::assertArrayNotHasKey('Content-Disposition', $response->getHeaders());
		self::assertSame(
			"WEBVTT\n\nNOTE\nSubtitle draft, created automatically and not reviewed.\n\n" . $cues,
			$response->render(),
		);
		self::assertSame([[self::UID, 7, 'vtt']], $this->exportCalls);
	}

	public function testTheTrackErrorsAreEmptyAnswersWithTheStatus(): void {
		// Not readable: 404 and nothing else.
		$this->containerNeverAsked = true;
		$this->exclusionsNeverAsked = true;
		$missing = $this->controller()->track(5);
		self::assertSame(Http::STATUS_NOT_FOUND, $missing->getStatus());
		self::assertSame('', $missing->render());

		// Blocked: 403 before anybody is asked.
		$this->file(7, 'Sitzung.webm', $this->sharedStorage(false));
		$blocked = $this->controller()->track(7);
		self::assertSame(Http::STATUS_FORBIDDEN, $blocked->getStatus());
		self::assertSame('', $blocked->render());

		// Excluded and unknown: the same 404; drift: 503.
		$this->readable = [];
		$this->file(8, 'Rat.webm');
		$this->containerNeverAsked = false;
		$this->exclusionsNeverAsked = false;
		$this->export = ['known' => false];
		$unknown = $this->controller()->track(8);
		self::assertSame(Http::STATUS_NOT_FOUND, $unknown->getStatus());
		self::assertSame('', $unknown->render());

		$this->excludedFiles = [8];
		$this->containerNeverAsked = true;
		self::assertSame(self::trackAnswer($unknown), self::trackAnswer($this->controller()->track(8)));

		$this->excludedFiles = [];
		$this->containerNeverAsked = true;
		$this->searchAllowed = false;
		self::assertSame(Http::STATUS_SERVICE_UNAVAILABLE, $this->controller()->track(8)->getStatus());
	}

	// -- the sidecar (EXP-03, D-04-05 bis D-04-08) ----------------------------------------

	private function sidecar(int $fileId): DataResponse {
		return $this->controller()->sidecar($fileId);
	}

	/** What could tell two JSON answers apart: the status and the encoded data. */
	private static function dataAnswer(DataResponse $response): string {
		return $response->getStatus() . "\n" . json_encode($response->getData());
	}

	public function testTheSidecarIsCreatedNextToTheMediumAndCarriesTheNote(): void {
		$cues = "1\n00:00:00.000 --> 00:00:02.000\nder Haushalt wird beraten\n";
		$this->file(7, 'sitzung.mp4');
		$this->export = self::known(['body' => "WEBVTT\n\n" . $cues, 'partial' => true, 'untilMs' => 60000]);

		$response = $this->sidecar(7);

		self::assertSame(Http::STATUS_CREATED, $response->getStatus());
		self::assertSame(['name' => 'sitzung.de.vtt'], $response->getData());
		self::assertSame([[self::UID, 7, 'vtt']], $this->exportCalls);
		self::assertArrayHasKey('sitzung.de.vtt', $this->sidecars);
		self::assertStringStartsWith("WEBVTT\n\nNOTE\n", $this->sidecars['sitzung.de.vtt']);
		self::assertSame(
			"WEBVTT\n\nNOTE\nSubtitle draft, created automatically and not reviewed.\n"
			. "Transcript up to 1:00, the file is still being processed.\n\n" . $cues,
			$this->sidecars['sitzung.de.vtt'],
		);
	}

	public function testASecondCallAfterSuccessIsThe409WithTheSameNameAndTheFileStaysByteForByte(): void {
		$this->file(7, 'sitzung.mp4');

		$first = $this->sidecar(7);
		self::assertSame(Http::STATUS_CREATED, $first->getStatus());
		$before = hash('sha256', $this->sidecars['sitzung.de.vtt']);

		$second = $this->sidecar(7);

		self::assertSame(Http::STATUS_CONFLICT, $second->getStatus());
		self::assertSame(['name' => 'sitzung.de.vtt'], $second->getData());
		self::assertSame($before, hash('sha256', $this->sidecars['sitzung.de.vtt']));
		self::assertSame(1, $this->newFileCalls);
	}

	public function testAForeignFileOfTheSameNameIsReportedAndNeverTouched(): void {
		$this->file(7, 'sitzung.mp4');
		$this->sidecars['sitzung.de.vtt'] = "WEBVTT\n\nder alte, korrigierte Untertitel\n";
		$before = hash('sha256', $this->sidecars['sitzung.de.vtt']);

		$response = $this->sidecar(7);

		self::assertSame(Http::STATUS_CONFLICT, $response->getStatus());
		self::assertSame(['name' => 'sitzung.de.vtt'], $response->getData());
		self::assertSame($before, hash('sha256', $this->sidecars['sitzung.de.vtt']));
		self::assertSame(0, $this->newFileCalls);
	}

	public function testABusyLockIsThe409WithTheNameAndNothingIsWritten(): void {
		$this->file(7, 'sitzung.mp4');
		$this->lockTaken = true;

		$response = $this->sidecar(7);

		self::assertSame(Http::STATUS_CONFLICT, $response->getStatus());
		self::assertSame(['name' => 'sitzung.de.vtt'], $response->getData());
		self::assertSame([], $this->sidecars);
		self::assertSame(0, $this->newFileCalls);
	}

	public function testABlockedShareIsTheReasonBlockedAndNobodyIsAskedWhateverElseHolds(): void {
		$this->file(7, 'sitzung.mp4', $this->sharedStorage(false));
		$this->containerNeverAsked = true;

		// The reference: blocked without any exclusion.
		$blockedOnly = $this->sidecar(7);
		self::assertSame(Http::STATUS_FORBIDDEN, $blockedOnly->getStatus());
		self::assertSame(['reason' => 'blocked'], $blockedOnly->getData());

		// Blocked and excluded: byte for byte the same, the exclusions are never asked.
		$this->excludedFiles = [7];
		$this->exclusionsNeverAsked = true;
		self::assertSame(self::dataAnswer($blockedOnly), self::dataAnswer($this->sidecar(7)));

		// An attribute nobody can read blocks the write the same way (fail closed).
		$this->readable = [];
		$this->file(7, 'sitzung.mp4', $this->brokenStorage());
		self::assertSame(self::dataAnswer($blockedOnly), self::dataAnswer($this->sidecar(7)));

		self::assertSame([], $this->sidecars);
	}

	public function testAFolderThatTakesNoNewFileIsTheReasonNotWritableAndTheContainerIsNeverAsked(): void {
		$this->file(7, 'sitzung.mp4');
		$this->creatable = false;
		$this->containerNeverAsked = true;

		$response = $this->sidecar(7);

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame(['reason' => 'not_writable'], $response->getData());
		self::assertSame([], $this->exportCalls);
		self::assertSame(0, $this->newFileCalls);
	}

	public function testARefusalDeepInTheStorageIsTheReasonNotWritable(): void {
		$this->file(7, 'sitzung.mp4');
		$this->storageRefuses = true;

		$response = $this->sidecar(7);

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame(['reason' => 'not_writable'], $response->getData());
		self::assertSame([], $this->sidecars);
	}

	public function testAnOverlongNameIsThe400AndNothingIsWrittenAndTheLimitSitsAt255Bytes(): void {
		// 252 + ".de.vtt" = 259 bytes: over the limit.
		$this->file(7, str_repeat('a', 252) . '.mp4');
		$over = $this->sidecar(7);
		self::assertSame(Http::STATUS_BAD_REQUEST, $over->getStatus());
		self::assertSame(['reason' => 'name_too_long'], $over->getData());
		self::assertSame(0, $this->newFileCalls);

		// The positive control: 248 + ".de.vtt" = 255 bytes still works.
		$this->readable = [];
		$this->file(8, str_repeat('a', 248) . '.mp4');
		$fits = $this->sidecar(8);
		self::assertSame(Http::STATUS_CREATED, $fits->getStatus());
		self::assertSame(['name' => str_repeat('a', 248) . '.de.vtt'], $fits->getData());
	}

	public function testTheSidecarSpellsOutTheUmlautAndASecondCallIsThe409OnTheSameName(): void {
		$this->file(7, 'Übung.webm');

		$first = $this->sidecar(7);
		self::assertSame(Http::STATUS_CREATED, $first->getStatus());
		self::assertSame(['name' => 'Uebung.de.vtt'], $first->getData());
		self::assertSame(['Uebung.de.vtt'], array_keys($this->sidecars));
		$before = hash('sha256', $this->sidecars['Uebung.de.vtt']);

		$second = $this->sidecar(7);
		self::assertSame(Http::STATUS_CONFLICT, $second->getStatus());
		self::assertSame(['name' => 'Uebung.de.vtt'], $second->getData());
		self::assertSame($before, hash('sha256', $this->sidecars['Uebung.de.vtt']));
		self::assertSame(1, $this->newFileCalls);
	}

	public function testTheLimitOf255BytesIsCheckedOnTheSpelledOutName(): void {
		// 124 x "ß" (248 bytes) + ".mp4" is a valid file name; spelled out
		// 124 x "ss" (248 bytes) + ".de.vtt" makes exactly 255 bytes. "ß" to
		// "ss" keeps the byte count, so this pair pins the edge 255/256.
		$this->file(7, str_repeat('ß', 124) . '.mp4');
		$fits = $this->sidecar(7);
		self::assertSame(Http::STATUS_CREATED, $fits->getStatus());
		$name = str_repeat('ss', 124) . '.de.vtt';
		self::assertSame(255, strlen($name));
		self::assertSame(['name' => $name], $fits->getData());

		// One byte more: 256 bytes, the 400 and nothing written.
		$this->readable = [];
		$this->sidecars = [];
		$this->newFileCalls = 0;
		$this->file(8, str_repeat('ß', 124) . 'x.mp4');
		$over = $this->sidecar(8);
		self::assertSame(Http::STATUS_BAD_REQUEST, $over->getStatus());
		self::assertSame(['reason' => 'name_too_long'], $over->getData());
		self::assertSame([], $this->sidecars);
		self::assertSame(0, $this->newFileCalls);
	}

	public function testACapitalSharpSNameFitsOnlyBecauseItIsSpelledOut(): void {
		// 83 x U+1E9E is 249 bytes: kept, the name would be 256 bytes. Spelled
		// out as "SS" it is 173 bytes, so the check sits on the replaced name.
		$this->file(7, str_repeat("\u{1E9E}", 83) . '.webm');

		$response = $this->sidecar(7);

		$name = str_repeat('SS', 83) . '.de.vtt';
		self::assertSame(173, strlen($name));
		self::assertSame(Http::STATUS_CREATED, $response->getStatus());
		self::assertSame(['name' => $name], $response->getData());
		self::assertArrayHasKey($name, $this->sidecars);
	}

	public function testAnExcludedAnUnknownAndAnUnreadableFileAreTheSameEmpty404(): void {
		$this->file(7, 'sitzung.mp4');

		// The reference: the container answers known false.
		$this->export = ['known' => false];
		$unknown = $this->sidecar(7);
		self::assertSame(Http::STATUS_NOT_FOUND, $unknown->getStatus());
		self::assertSame([], $unknown->getData());

		// An excluded file: the container is never asked, the bytes are the same.
		$this->export = self::known();
		$this->excludedFiles = [7];
		$this->containerNeverAsked = true;
		self::assertSame(self::dataAnswer($unknown), self::dataAnswer($this->sidecar(7)));

		// A file the user cannot read: same bytes again.
		$this->excludedFiles = [];
		$this->exclusionsNeverAsked = true;
		self::assertSame(self::dataAnswer($unknown), self::dataAnswer($this->sidecar(5)));

		self::assertSame([], $this->sidecars);
	}

	public function testADriftAndASilentContainerAreTheSameEmpty503ForTheSidecar(): void {
		$this->file(7, 'sitzung.mp4');
		$this->searchAllowed = false;
		$this->containerNeverAsked = true;
		$drift = $this->sidecar(7);
		self::assertSame(Http::STATUS_SERVICE_UNAVAILABLE, $drift->getStatus());
		self::assertSame([], $drift->getData());

		$this->searchAllowed = true;
		$this->containerNeverAsked = false;
		$this->export = null;
		self::assertSame(self::dataAnswer($drift), self::dataAnswer($this->sidecar(7)));
		self::assertSame([], $this->sidecars);
	}

	public function testTheSidecarRouteIsAPostWithTheCsrfCheckAndItsOwnRateLimit(): void {
		$reflection = new \ReflectionMethod(ExportController::class, 'sidecar');
		$names = array_map(static fn (\ReflectionAttribute $attribute): string => $attribute->getName(), $reflection->getAttributes());

		self::assertContains(\OCP\AppFramework\Http\Attribute\NoAdminRequired::class, $names);
		self::assertContains(\OCP\AppFramework\Http\Attribute\UserRateLimit::class, $names);
		// The route writes: the request token stays required (gate rule 20).
		self::assertNotContains(\OCP\AppFramework\Http\Attribute\NoCSRFRequired::class, $names);
		self::assertNotContains(\OCP\AppFramework\Http\Attribute\PublicPage::class, $names);
		self::assertNotContains(\OCP\AppFramework\Http\Attribute\ExAppRequired::class, $names);

		foreach ($reflection->getAttributes(\OCP\AppFramework\Http\Attribute\FrontpageRoute::class) as $route) {
			$arguments = $route->getArguments();
			self::assertSame('POST', $arguments['verb']);
			self::assertSame('/sidecar/{fileId}', $arguments['url']);
			self::assertSame(['fileId' => '\d+'], $arguments['requirements']);
		}
		foreach ($reflection->getAttributes(\OCP\AppFramework\Http\Attribute\UserRateLimit::class) as $limit) {
			self::assertSame(['limit' => 10, 'period' => 60], $limit->getArguments());
		}
	}

	// -- the routes -----------------------------------------------------------------------

	/** @return array<string, array{string, string, array<string, string>}> */
	public static function routes(): array {
		return [
			'download' => ['download', '/export/{fileId}/{format}', ['fileId' => '\d+', 'format' => 'srt|vtt|txt']],
			'track' => ['track', '/track/{fileId}', ['fileId' => '\d+']],
		];
	}

	/** @param array<string, string> $requirements */
	#[DataProvider('routes')]
	public function testTheRoutesNeedASessionButNoAdminAndAreRateLimited(string $method, string $url, array $requirements): void {
		$reflection = new \ReflectionMethod(ExportController::class, $method);
		$names = array_map(static fn (\ReflectionAttribute $attribute): string => $attribute->getName(), $reflection->getAttributes());

		self::assertContains(\OCP\AppFramework\Http\Attribute\NoAdminRequired::class, $names);
		self::assertContains(\OCP\AppFramework\Http\Attribute\NoCSRFRequired::class, $names);
		self::assertContains(\OCP\AppFramework\Http\Attribute\UserRateLimit::class, $names);
		self::assertNotContains(\OCP\AppFramework\Http\Attribute\PublicPage::class, $names);
		self::assertNotContains(\OCP\AppFramework\Http\Attribute\ExAppRequired::class, $names);

		foreach ($reflection->getAttributes(\OCP\AppFramework\Http\Attribute\FrontpageRoute::class) as $route) {
			$arguments = $route->getArguments();
			self::assertSame('GET', $arguments['verb']);
			self::assertSame($url, $arguments['url']);
			self::assertSame($requirements, $arguments['requirements']);
		}
		foreach ($reflection->getAttributes(\OCP\AppFramework\Http\Attribute\UserRateLimit::class) as $limit) {
			self::assertSame(['limit' => 30, 'period' => 60], $limit->getArguments());
		}
	}

	public function testTheErrorPageIsTheUserLayoutOfThisApp(): void {
		$this->containerNeverAsked = true;
		$this->exclusionsNeverAsked = true;

		$response = $this->errorPageOf(5);

		self::assertSame(Application::APP_ID, $response->getApp());
		self::assertSame('export_error', $response->getTemplateName());
		self::assertSame(TemplateResponse::RENDER_AS_USER, $response->getRenderAs());
	}
}
