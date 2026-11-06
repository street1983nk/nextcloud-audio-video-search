<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Controller\GatewayController;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\StreamResponse;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IRootFolder;
use OCP\Files\StorageNotAvailableException;
use OCP\IRequest;
use OCP\IUser;
use OCP\IUserManager;
use OCP\IUserSession;
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
	private ?IUser $active = null;

	protected function setUp(): void {
		parent::setUp();

		$this->active = null;
		$this->rootFolder = $this->createMock(IRootFolder::class);
		$this->logger = $this->createMock(LoggerInterface::class);

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

	private static function assertNoPathIn(DataResponse|StreamResponse $response): void {
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
}
