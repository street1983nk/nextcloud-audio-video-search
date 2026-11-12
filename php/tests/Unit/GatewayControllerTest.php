<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Controller\GatewayController;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataDisplayResponse;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\StreamResponse;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\ForbiddenException;
use OCP\Files\IRootFolder;
use OCP\Files\StorageNotAvailableException;
use OCP\IRequest;
use OCP\IUser;
use OCP\IUserManager;
use OCP\IUserSession;
use OCP\Lock\LockedException;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The content gateway, taken over from Findling together with its cases.
 *
 * The route attribute answers "is this a registered external app", not "is
 * this our external app". The comparison of the EX-APP-ID header against the
 * one backend app id is what stands between any other container on the
 * instance and the file content of every user. backend/tests/test_php_gates.py
 * holds the attribute and the first statement by reading the sources; this
 * file holds what the method does once it runs.
 *
 * Everything is a double. No file system is touched, and the one stream below
 * is in memory.
 */
#[CoversClass(GatewayController::class)]
final class GatewayControllerTest extends TestCase {
	private const NOT_FOUND = ['error' => 'Node is not a file or could not be found.'];

	private IRootFolder&MockObject $rootFolder;
	private LoggerInterface&MockObject $logger;
	private IUserSession&MockObject $session;
	private IUserManager&MockObject $userManager;
	private ExclusionService&MockObject $exclusions;
	private ?IUser $active = null;
	/** @var list<int> the file ids a rule of the admin leaves out */
	private array $excludedFiles = [];
	/** @var list<int> every file id the exclusions were asked about */
	private array $askedExclusions = [];

	protected function setUp(): void {
		parent::setUp();

		$this->active = null;
		$this->excludedFiles = [];
		$this->askedExclusions = [];
		$this->rootFolder = $this->createMock(IRootFolder::class);
		$this->logger = $this->createMock(LoggerInterface::class);
		$this->exclusions = $this->createMock(ExclusionService::class);
		$this->exclusions->method('isExcludedFile')->willReturnCallback(function (int $fileId): bool {
			$this->askedExclusions[] = $fileId;

			return in_array($fileId, $this->excludedFiles, true);
		});

		// Stateful, so the cases can observe who is active at each step.
		$this->session = $this->createMock(IUserSession::class);
		$this->session->method('getUser')->willReturnCallback(fn (): ?IUser => $this->active);
		$this->session->method('setVolatileActiveUser')->willReturnCallback(function (?IUser $user): void {
			$this->active = $user;
		});
		$this->userManager = $this->createMock(IUserManager::class);
		$this->userManager->method('get')->willReturnCallback(function (string $uid): ?IUser {
			if ($uid === 'ghost') {
				return null;
			}
			$user = $this->createMock(IUser::class);
			$user->method('getUID')->willReturn($uid);

			return $user;
		});
	}

	/** The app id of the container, read out of the class instead of copied. */
	private function backendAppId(): string {
		$value = (new \ReflectionClass(Application::class))->getConstant('BACKEND_APP_ID');

		self::assertIsString($value, 'BACKEND_APP_ID is gone or is no longer a string');

		return $value;
	}

	private function controller(string $callerAppId): GatewayController {
		$request = $this->createMock(IRequest::class);
		$request->method('getHeader')->willReturnCallback(
			static fn (string $name): string => $name === 'EX-APP-ID' ? $callerAppId : '',
		);

		return new GatewayController(
			$request,
			$this->rootFolder,
			$this->logger,
			new ReaderContext($this->session, $this->userManager),
			$this->exclusions,
		);
	}

	/** A readable file of alice whose open behaves as the closure says. */
	private function fileOpeningAs(\Closure $open): void {
		$file = $this->createMock(File::class);
		$file->method('isReadable')->willReturn(true);
		$file->method('getPath')->willReturn('/alice/files/Sitzung 2026-11-03.mp4');
		$file->method('getName')->willReturn('Sitzung 2026-11-03.mp4');
		$file->method('fopen')->with('r')->willReturnCallback($open);
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->with(11)->willReturn($file);
		$this->rootFolder->method('getUserFolder')->with('alice')->willReturn($userFolder);
	}

	private static function assertNoPathIn(DataResponse|StreamResponse|DataDisplayResponse $response): void {
		if (!$response instanceof DataResponse) {
			return;
		}
		$encoded = (string)json_encode($response->getData());
		self::assertStringNotContainsString('Sitzung', $encoded);
		self::assertStringNotContainsString('/alice', $encoded);
		self::assertStringNotContainsString('.mp4', $encoded);
	}

	public function testACallFromTheBackendUnderItsOwnAppIdDeliversTheFileContents(): void {
		$stream = fopen('php://memory', 'rb+');
		self::assertIsResource($stream);

		$file = $this->createMock(File::class);
		// The 'r' is the entire read only guarantee of this route.
		$file->expects(self::once())->method('fopen')->with('r')->willReturn($stream);
		$file->method('isReadable')->willReturn(true);

		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->with(11)->willReturn($file);
		$this->rootFolder->method('getUserFolder')->with('alice')->willReturn($userFolder);

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(StreamResponse::class, $response);

		fclose($stream);
	}

	public function testACallFromAForeignExAppIsRefusedBeforeAnyLookup(): void {
		$this->rootFolder->expects(self::never())->method('getUserFolder');

		$response = $this->controller('some_other_backend')->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertNoPathIn($response);
	}

	public function testTheFindlingBackendIsAForeignCallerToo(): void {
		// A sibling product on the same instance is a registered ExApp as well,
		// and it is not ours.
		$this->rootFolder->expects(self::never())->method('getUserFolder');

		$response = $this->controller('findling_backend')->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
	}

	public function testACallWithoutTheHeaderIsRefusedAndDoesNotFail(): void {
		$response = $this->controller('')->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
	}

	public function testTheRefusalIsLoggedWithTheCallerAppIdAndWithNothingElse(): void {
		$this->logger->expects(self::once())
			->method('warning')
			->with(
				'Audio & Video Search: content gateway called by a foreign ExApp',
				['app' => 'some_other_backend'],
			);

		$this->controller('some_other_backend')->getFileContents(11, 'alice');
	}

	public function testUnreadableMissingFolderAndUnknownUserAreTheSame404(): void {
		$closed = $this->createMock(File::class);
		$closed->method('isReadable')->willReturn(false);
		$closed->expects(self::never())->method('fopen');
		$folderNode = $this->createMock(Folder::class);

		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturnCallback(
			static fn (int $fileId): mixed => match ($fileId) {
				11 => $closed,
				12 => $folderNode,
				default => null,
			},
		);
		$this->rootFolder->method('getUserFolder')->willReturnCallback(
			static function (string $uid) use ($userFolder): Folder {
				if ($uid === 'ghost') {
					throw new \OC\User\NoUserException('ghost');
				}

				return $userFolder;
			},
		);

		$controller = $this->controller($this->backendAppId());
		$answers = [
			$controller->getFileContents(11, 'alice'),
			$controller->getFileContents(12, 'alice'),
			$controller->getFileContents(999999, 'alice'),
			$controller->getFileContents(11, 'ghost'),
		];

		foreach ($answers as $answer) {
			self::assertInstanceOf(DataResponse::class, $answer);
			self::assertSame(Http::STATUS_NOT_FOUND, $answer->getStatus());
			self::assertSame(self::NOT_FOUND, $answer->getData());
		}
	}

	public function testAnUnknownUserIsNotSwitchedTo(): void {
		$this->session->expects(self::never())->method('setVolatileActiveUser');
		$this->rootFolder->method('getUserFolder')->willThrowException(new \OC\User\NoUserException('ghost'));

		$unknown = $this->controller($this->backendAppId())->getFileContents(11, 'ghost');

		self::assertInstanceOf(DataResponse::class, $unknown);
		self::assertSame(self::NOT_FOUND, $unknown->getData());
	}

	public function testTheFolderAndTheLookupRunAsTheUserAndTheOpenAfterTheRestore(): void {
		$stream = fopen('php://memory', 'rb+');
		self::assertIsResource($stream);
		$steps = [];

		$file = $this->createMock(File::class);
		$file->method('isReadable')->willReturn(true);
		$file->method('fopen')->willReturnCallback(function () use ($stream, &$steps) {
			$steps[] = ['fopen', $this->active?->getUID()];

			return $stream;
		});
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturnCallback(function () use ($file, &$steps): File {
			$steps[] = ['lookup', $this->active?->getUID()];

			return $file;
		});
		$this->rootFolder->method('getUserFolder')->willReturnCallback(function () use ($userFolder, &$steps): Folder {
			$steps[] = ['folder', $this->active?->getUID()];

			return $userFolder;
		});

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(StreamResponse::class, $response);
		self::assertSame([['folder', 'alice'], ['lookup', 'alice'], ['fopen', null]], $steps);
		self::assertNull($this->active);

		fclose($stream);
	}

	public function testAFileThatCannotBeOpenedAnswers422AndLogsTheFileIdOnly(): void {
		$this->fileOpeningAs(static fn () => false);
		$this->logger->expects(self::once())
			->method('warning')
			->with('Audio & Video Search: a file could not be opened for reading, answered 422', ['fileId' => 11]);
		$this->logger->expects(self::never())->method('error');

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_UNPROCESSABLE_ENTITY, $response->getStatus());
		self::assertSame(['error' => 'File could not be opened for reading.'], $response->getData());
		self::assertNoPathIn($response);
	}

	public function testAStorageThatIsNotAvailableAtTheOpenIsA500WithoutAPath(): void {
		$this->fileOpeningAs(static function (): never {
			throw new StorageNotAvailableException('/alice/files/Sitzung 2026-11-03.mp4');
		});
		$this->logger->expects(self::once())
			->method('error')
			->with('Audio & Video Search: unknown error reading a file', self::callback(
				static fn (array $context): bool => array_keys($context) === ['exception'],
			));

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_INTERNAL_SERVER_ERROR, $response->getStatus());
		self::assertSame(['error' => 'Unknown error occurred.'], $response->getData());
		self::assertNoPathIn($response);
	}

	/** A memory stream holding $bytes, positioned at the start. */
	private static function memoryStream(string $bytes) {
		$stream = fopen('php://memory', 'rb+');
		self::assertIsResource($stream);
		fwrite($stream, $bytes);
		rewind($stream);

		return $stream;
	}

	/** The logger must never see the path or the user of the file in any call. */
	private function loggerSeesNoPathOrUser(): void {
		$check = static function (string $message, array $context = []): void {
			$encoded = $message . json_encode($context);
			self::assertStringNotContainsString('Sitzung', $encoded);
			self::assertStringNotContainsString('alice', $encoded);
		};
		foreach (['debug', 'info', 'warning'] as $level) {
			$this->logger->method($level)->willReturnCallback($check);
		}
	}

	public function testAccessControlAtTheOpenIsA403WithItsReasonAndWithoutAPath(): void {
		$this->fileOpeningAs(static function (): never {
			throw new ForbiddenException('Access denied by access control', false);
		});
		$this->loggerSeesNoPathOrUser();
		$this->logger->expects(self::never())->method('error');

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame('access_control', $response->getHeaders()['X-AVS-Reason'] ?? null);
		self::assertSame('access_control', $response->getData()['code'] ?? null);
		self::assertNoPathIn($response);
	}

	public function testAccessControlAtTheLookupIsA403Too(): void {
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willThrowException(new ForbiddenException('Access denied by access control', false));
		$this->rootFolder->method('getUserFolder')->willReturn($userFolder);

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame('access_control', $response->getHeaders()['X-AVS-Reason'] ?? null);
		self::assertNull($this->active);
	}

	public function testALockedFileIsA423WithItsReasonAndWithoutAPath(): void {
		$this->fileOpeningAs(static function (): never {
			throw new LockedException('/alice/files/Sitzung 2026-11-03.mp4');
		});
		$this->loggerSeesNoPathOrUser();
		$this->logger->expects(self::never())->method('error');

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_LOCKED, $response->getStatus());
		self::assertSame('locked', $response->getHeaders()['X-AVS-Reason'] ?? null);
		self::assertNoPathIn($response);
	}

	public function testAPlainRefusalCarriesNoReasonHeader(): void {
		$response = $this->controller('some_other_backend')->getFileContents(11, 'alice');

		self::assertArrayNotHasKey('X-AVS-Reason', $response->getHeaders());
	}

	public function testTheHeadRouteRefusesAForeignCallerBeforeAnyLookup(): void {
		$this->rootFolder->expects(self::never())->method('getUserFolder');

		$response = $this->controller('findling_backend')->getFileHead(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
	}

	/** @return array<string, array{int, int}> */
	public static function headSizes(): array {
		return [
			'200 KiB' => [204800, 65536],
			'exactly 64 KiB' => [65536, 65536],
			'10 KiB' => [10240, 10240],
			'empty' => [0, 0],
		];
	}

	#[\PHPUnit\Framework\Attributes\DataProvider('headSizes')]
	public function testTheHeadIsExactlyTheStartOfTheFileUpTo64KiB(int $size, int $expected): void {
		$bytes = '';
		for ($i = 0; strlen($bytes) < $size; $i++) {
			$bytes .= hash('sha256', (string)$i, true);
		}
		$bytes = substr($bytes, 0, $size);
		$stream = self::memoryStream($bytes);
		$this->fileOpeningAs(static fn () => $stream);

		$response = $this->controller($this->backendAppId())->getFileHead(11, 'alice');

		self::assertInstanceOf(DataDisplayResponse::class, $response);
		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame('application/octet-stream', $response->getHeaders()['Content-Type'] ?? null);
		self::assertSame($expected, strlen($response->render()));
		self::assertSame(substr($bytes, 0, $expected), $response->render());
		// The stream is closed again: the head holds no lock beyond the read.
		self::assertFalse(is_resource($stream));
	}

	public function testTheHeadRouteRunsTheLookupAsTheUser(): void {
		$stream = self::memoryStream('abc');
		$steps = [];
		$file = $this->createMock(File::class);
		$file->method('isReadable')->willReturn(true);
		$file->method('fopen')->with('r')->willReturnCallback(function () use ($stream, &$steps) {
			$steps[] = ['fopen', $this->active?->getUID()];

			return $stream;
		});
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturnCallback(function () use ($file, &$steps): File {
			$steps[] = ['lookup', $this->active?->getUID()];

			return $file;
		});
		$this->rootFolder->method('getUserFolder')->willReturn($userFolder);

		$this->controller($this->backendAppId())->getFileHead(11, 'alice');

		self::assertSame([['lookup', 'alice'], ['fopen', null]], $steps);
	}

	public function testTheHeadRouteGivesTheSame404AsTheGateway(): void {
		$closed = $this->createMock(File::class);
		$closed->method('isReadable')->willReturn(false);
		$closed->expects(self::never())->method('fopen');
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturnCallback(
			static fn (int $fileId): mixed => $fileId === 11 ? $closed : null,
		);
		$this->rootFolder->method('getUserFolder')->willReturnCallback(
			static function (string $uid) use ($userFolder): Folder {
				if ($uid === 'ghost') {
					throw new \OC\User\NoUserException('ghost');
				}

				return $userFolder;
			},
		);
		$controller = $this->controller($this->backendAppId());

		foreach ([[11, 'alice'], [999, 'alice'], [11, 'ghost']] as [$fileId, $uid]) {
			$head = $controller->getFileHead($fileId, $uid);
			$full = $controller->getFileContents($fileId, $uid);
			self::assertInstanceOf(DataResponse::class, $head);
			self::assertInstanceOf(DataResponse::class, $full);
			self::assertSame(Http::STATUS_NOT_FOUND, $head->getStatus());
			self::assertSame($full->getData(), $head->getData());
		}
	}

	public function testAHeadThatCannotBeOpenedIs422LikeTheGateway(): void {
		$this->fileOpeningAs(static fn () => false);

		$response = $this->controller($this->backendAppId())->getFileHead(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_UNPROCESSABLE_ENTITY, $response->getStatus());
		self::assertSame(['error' => 'File could not be opened for reading.'], $response->getData());
	}

	public function testTheHeadRouteKnowsAccessControl(): void {
		$this->fileOpeningAs(static function (): never {
			throw new ForbiddenException('Access denied by access control', false);
		});

		$forbidden = $this->controller($this->backendAppId())->getFileHead(11, 'alice');

		self::assertSame(Http::STATUS_FORBIDDEN, $forbidden->getStatus());
		self::assertSame('access_control', $forbidden->getHeaders()['X-AVS-Reason'] ?? null);
	}

	public function testALockedHeadIs423(): void {
		$this->fileOpeningAs(static function (): never {
			throw new LockedException('/alice/files/Sitzung 2026-11-03.mp4');
		});

		$locked = $this->controller($this->backendAppId())->getFileHead(11, 'alice');

		self::assertSame(Http::STATUS_LOCKED, $locked->getStatus());
		self::assertSame('locked', $locked->getHeaders()['X-AVS-Reason'] ?? null);
		self::assertNoPathIn($locked);
	}

	public function testAnotherErrorOfTheHeadIsA500WithoutAPath(): void {
		$this->fileOpeningAs(static function (): never {
			throw new StorageNotAvailableException('/alice/files/Sitzung 2026-11-03.mp4');
		});

		$response = $this->controller($this->backendAppId())->getFileHead(11, 'alice');

		self::assertSame(Http::STATUS_INTERNAL_SERVER_ERROR, $response->getStatus());
		self::assertNoPathIn($response);
	}

	/**
	 * reason_77 (plan 02-13): on stable33 a rule of files_accesscontrol does
	 * not hide the file and does not throw at the lookup. Its cache wrapper
	 * takes the read permission out of the cache entry, so the node is found
	 * and isReadable() is false. The cases below hold the difference between
	 * that and every other file the user cannot read.
	 */
	private const ACCESS_CONTROL_STORAGE = 'OCA\FilesAccessControl\StorageWrapper';
	private const INTERNAL_PATH = 'Aufnahmen/Sitzung 2026-11-03.mp4';

	/**
	 * A storage layer as Nextcloud stacks them: it says whether the wrapper of
	 * files_accesscontrol is at or below it, whether the path is readable at
	 * this layer, and hands out the layer below.
	 */
	private function storageLayer(bool $holdsAccessControl, bool $readable, ?object $below): \OC\Files\Storage\Wrapper\Wrapper&MockObject {
		$layer = $this->createMock(\OC\Files\Storage\Wrapper\Wrapper::class);
		$layer->method('instanceOfStorage')->willReturnCallback(
			static fn (string $class): bool => $holdsAccessControl && $class === self::ACCESS_CONTROL_STORAGE,
		);
		$layer->method('isReadable')->with(self::INTERNAL_PATH)->willReturn($readable);
		if ($below !== null) {
			$layer->method('getWrapperStorage')->willReturn($below);
		}

		return $layer;
	}

	/** The storage below every wrapper: no access control in it, readable or not. */
	private function plainStorage(bool $readable): \OC\Files\Storage\Storage&MockObject {
		$storage = $this->createMock(\OC\Files\Storage\Storage::class);
		$storage->method('instanceOfStorage')->willReturn(false);
		$storage->method('isReadable')->with(self::INTERNAL_PATH)->willReturn($readable);

		return $storage;
	}

	/** File 11 of alice: listed, not readable for her, never opened, on the given storage. */
	private function listedButClosedFileOn(?object $storage): void {
		$file = $this->createMock(File::class);
		$file->method('isReadable')->willReturn(false);
		$file->method('getPath')->willReturn('/alice/files/Aufnahmen/Sitzung 2026-11-03.mp4');
		$file->method('getName')->willReturn('Sitzung 2026-11-03.mp4');
		$file->method('getInternalPath')->willReturn(self::INTERNAL_PATH);
		$file->method('getStorage')->willReturn($storage);
		$file->expects(self::never())->method('fopen');
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->with(11)->willReturn($file);
		$this->rootFolder->method('getUserFolder')->with('alice')->willReturn($userFolder);
	}

	private static function assertPlain404(DataResponse|StreamResponse|DataDisplayResponse $response): void {
		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_NOT_FOUND, $response->getStatus());
		self::assertSame(self::NOT_FOUND, $response->getData());
		self::assertArrayNotHasKey('X-AVS-Reason', $response->getHeaders());
	}

	public function testAFileOnlyAccessControlKeepsFromTheUserIsA403AccessControl(): void {
		$this->listedButClosedFileOn($this->storageLayer(true, false, $this->plainStorage(true)));
		$this->loggerSeesNoPathOrUser();
		$this->logger->expects(self::never())->method('error');

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame('access_control', $response->getHeaders()['X-AVS-Reason'] ?? null);
		self::assertSame('access_control', $response->getData()['code'] ?? null);
		self::assertNoPathIn($response);
		// The switch to the reader is undone on this way out as well.
		self::assertNull($this->active);
	}

	public function testTheHeadRouteGivesTheSame403ForAccessControl(): void {
		$this->listedButClosedFileOn($this->storageLayer(true, false, $this->plainStorage(true)));
		$this->loggerSeesNoPathOrUser();

		$response = $this->controller($this->backendAppId())->getFileHead(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame('access_control', $response->getHeaders()['X-AVS-Reason'] ?? null);
		self::assertNoPathIn($response);
	}

	public function testAccessControlIsLoggedWithTheFileIdAndTheReasonOnly(): void {
		$this->listedButClosedFileOn($this->storageLayer(true, false, $this->plainStorage(true)));
		$this->logger->expects(self::once())
			->method('info')
			->with(
				'Audio & Video Search: access control refused a read, answered 403',
				['fileId' => 11, 'reason' => 'access_control'],
			);

		$this->controller($this->backendAppId())->getFileContents(11, 'alice');
	}

	public function testAccessControlBelowAnotherWrapperIsFoundToo(): void {
		$accessControl = $this->storageLayer(true, false, $this->plainStorage(true));
		$this->listedButClosedFileOn($this->storageLayer(true, false, $accessControl));

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame('access_control', $response->getHeaders()['X-AVS-Reason'] ?? null);
	}

	public function testAnUnreadableFileWithoutAccessControlStaysThePlain404(): void {
		$this->listedButClosedFileOn($this->storageLayer(false, false, $this->plainStorage(false)));
		$controller = $this->controller($this->backendAppId());

		self::assertPlain404($controller->getFileContents(11, 'alice'));
		self::assertPlain404($controller->getFileHead(11, 'alice'));
	}

	public function testAFileTheStorageBelowAccessControlRefusesAsWellStaysThePlain404(): void {
		// The wrapper is there, but the file is closed for another reason:
		// the storage below it says no on its own.
		$this->listedButClosedFileOn($this->storageLayer(true, false, $this->plainStorage(false)));
		$controller = $this->controller($this->backendAppId());

		self::assertPlain404($controller->getFileContents(11, 'alice'));
		self::assertPlain404($controller->getFileHead(11, 'alice'));
	}

	public function testAFileAccessControlWouldLetThroughStaysThePlain404(): void {
		// The wrapper is there and has no objection; the node is closed anyway.
		$this->listedButClosedFileOn($this->storageLayer(true, true, $this->plainStorage(true)));

		self::assertPlain404($this->controller($this->backendAppId())->getFileContents(11, 'alice'));
	}

	public function testWithAccessControlInPlaceAFileTheUserDoesNotSeeStaysThePlain404(): void {
		// Not visible at all for this user: nothing to ask a storage about.
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturn(null);
		$this->rootFolder->method('getUserFolder')->with('alice')->willReturn($userFolder);
		$controller = $this->controller($this->backendAppId());

		self::assertPlain404($controller->getFileContents(11, 'alice'));
		self::assertPlain404($controller->getFileHead(11, 'alice'));
	}

	public function testAFolderUnderAccessControlStaysThePlain404(): void {
		$folderNode = $this->createMock(Folder::class);
		$folderNode->method('isReadable')->willReturn(false);
		$folderNode->expects(self::never())->method('getStorage');
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturn($folderNode);
		$this->rootFolder->method('getUserFolder')->with('alice')->willReturn($userFolder);

		self::assertPlain404($this->controller($this->backendAppId())->getFileContents(11, 'alice'));
	}

	public function testAStorageThatFailsWhileAskedStaysThePlain404(): void {
		$layer = $this->createMock(\OC\Files\Storage\Wrapper\Wrapper::class);
		$layer->method('instanceOfStorage')->willThrowException(new StorageNotAvailableException('/alice/files/Aufnahmen'));
		$this->listedButClosedFileOn($layer);
		$this->logger->expects(self::never())->method('error');

		self::assertPlain404($this->controller($this->backendAppId())->getFileContents(11, 'alice'));
	}

	public function testAFileWithoutAStorageStaysThePlain404(): void {
		$this->listedButClosedFileOn(null);

		self::assertPlain404($this->controller($this->backendAppId())->getFileContents(11, 'alice'));
	}

	public function testAReadableFileIsServedWithoutAskingItsStorage(): void {
		$stream = self::memoryStream('abc');
		$file = $this->createMock(File::class);
		$file->method('isReadable')->willReturn(true);
		$file->expects(self::never())->method('getStorage');
		$file->method('fopen')->with('r')->willReturn($stream);
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->with(11)->willReturn($file);
		$this->rootFolder->method('getUserFolder')->with('alice')->willReturn($userFolder);

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(StreamResponse::class, $response);
		fclose($stream);
	}

	public function testTheHeadLimitAndTheHeaderAreTheOnesOfTheContainer(): void {
		// backend/src/audio_video_search_backend/nc.py HEAD_BYTES and REASON_HEADER.
		self::assertSame(65536, GatewayController::HEAD_BYTES);
		self::assertSame('X-AVS-Reason', GatewayController::REASON_HEADER);
	}

	// -- exclusions (plan 02-16): the third check, before anything is opened -----

	/** A readable file of alice that must never be opened. */
	private function fileThatMustStayClosed(): void {
		$file = $this->createMock(File::class);
		$file->method('isReadable')->willReturn(true);
		$file->expects(self::never())->method('fopen');
		$userFolder = $this->createMock(Folder::class);
		$userFolder->method('getFirstNodeById')->willReturn($file);
		$this->rootFolder->method('getUserFolder')->willReturn($userFolder);
	}

	public function testAnExcludedFileIsA403ExcludedAndIsNeitherResolvedNorOpened(): void {
		$this->excludedFiles = [11];
		$this->fileThatMustStayClosed();
		$this->rootFolder->expects(self::never())->method('getUserFolder');
		$this->userManager->expects(self::never())->method('get');
		$this->session->expects(self::never())->method('setVolatileActiveUser');

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $response);
		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame(['error' => 'File is excluded.', 'code' => 'excluded'], $response->getData());
		self::assertSame('excluded', $response->getHeaders()['X-AVS-Reason'] ?? null);
		self::assertSame([11], $this->askedExclusions);
	}

	public function testTheHeadRouteGivesTheSame403ForAnExcludedFile(): void {
		$this->excludedFiles = [11];
		$this->fileThatMustStayClosed();
		$this->rootFolder->expects(self::never())->method('getUserFolder');
		$this->session->expects(self::never())->method('setVolatileActiveUser');

		$head = $this->controller($this->backendAppId())->getFileHead(11, 'alice');
		$full = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(DataResponse::class, $head);
		self::assertInstanceOf(DataResponse::class, $full);
		self::assertSame(Http::STATUS_FORBIDDEN, $head->getStatus());
		self::assertSame($full->getData(), $head->getData());
		self::assertSame('excluded', $head->getHeaders()['X-AVS-Reason'] ?? null);
		self::assertSame([11, 11], $this->askedExclusions);
	}

	public function testAnExcludedFileIsRefusedForAUserNobodyKnowsAsWell(): void {
		// The rule is about the file: no user is looked up before the refusal.
		$this->excludedFiles = [11];
		$this->userManager->expects(self::never())->method('get');

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'ghost');

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame('excluded', $response->getHeaders()['X-AVS-Reason'] ?? null);
	}

	public function testAnExclusionIsLoggedWithTheFileIdAndTheReasonOnly(): void {
		$this->excludedFiles = [11];
		$this->logger->expects(self::once())
			->method('info')
			->with(
				'Audio & Video Search: an excluded file was asked for, answered 403',
				['fileId' => 11, 'reason' => 'excluded'],
			);
		$this->logger->expects(self::never())->method('warning');
		$this->logger->expects(self::never())->method('error');

		$this->controller($this->backendAppId())->getFileContents(11, 'alice');
	}

	public function testAForeignCallerGetsTheSameRefusalForAnExcludedFileAsForAnyOther(): void {
		// The guard comes first: a foreign container learns nothing about a
		// rule, the exclusions are not even asked.
		$this->excludedFiles = [11];

		$excluded = $this->controller('some_other_backend')->getFileContents(11, 'alice');
		$other = $this->controller('some_other_backend')->getFileContents(12, 'alice');
		$excludedHead = $this->controller('some_other_backend')->getFileHead(11, 'alice');
		$otherHead = $this->controller('some_other_backend')->getFileHead(12, 'alice');

		self::assertInstanceOf(DataResponse::class, $excluded);
		self::assertInstanceOf(DataResponse::class, $other);
		self::assertInstanceOf(DataResponse::class, $excludedHead);
		self::assertInstanceOf(DataResponse::class, $otherHead);
		foreach ([[$excluded, $other], [$excludedHead, $otherHead]] as [$one, $two]) {
			self::assertSame($two->getStatus(), $one->getStatus());
			self::assertSame($two->getData(), $one->getData());
			self::assertArrayNotHasKey('X-AVS-Reason', $one->getHeaders());
			self::assertArrayNotHasKey('X-AVS-Reason', $two->getHeaders());
		}
		self::assertSame([], $this->askedExclusions);
	}

	public function testAFileNoRuleCoversIsAskedAboutOnceAndThenServed(): void {
		$stream = fopen('php://memory', 'rb+');
		self::assertIsResource($stream);
		$this->excludedFiles = [12];
		$this->fileOpeningAs(static fn () => $stream);

		$response = $this->controller($this->backendAppId())->getFileContents(11, 'alice');

		self::assertInstanceOf(StreamResponse::class, $response);
		self::assertSame([11], $this->askedExclusions);

		fclose($stream);
	}

	public function testTheReasonOfAnExclusionIsTheOneTheContainerReads(): void {
		// backend/src/audio_video_search_backend/nc.py EXCLUDED.
		self::assertSame('excluded', GatewayController::REASON_EXCLUDED);
	}
}
