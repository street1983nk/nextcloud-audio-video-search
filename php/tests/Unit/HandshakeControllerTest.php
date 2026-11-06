<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Controller\HandshakeController;
use OCP\App\IAppManager;
use OCP\AppFramework\Http;
use OCP\IRequest;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The handshake the container asks to find out whether the PHP half is there.
 *
 * Only the backend of this app gets the version; every other caller gets a
 * 403 with a static sentence, and the log names the caller app id only.
 */
#[CoversClass(HandshakeController::class)]
final class HandshakeControllerTest extends TestCase {
	private const FORBIDDEN = ['error' => 'This route is reserved for the Audio & Video Search backend.'];

	private IAppManager&MockObject $appManager;
	private LoggerInterface&MockObject $logger;

	protected function setUp(): void {
		parent::setUp();

		$this->appManager = $this->createMock(IAppManager::class);
		$this->logger = $this->createMock(LoggerInterface::class);
	}

	/** The app id of the container, read out of the class instead of copied. */
	private function backendAppId(): string {
		$value = (new \ReflectionClass(Application::class))->getConstant('BACKEND_APP_ID');

		self::assertIsString($value, 'BACKEND_APP_ID is gone or is no longer a string');

		return $value;
	}

	private function controller(string $callerAppId): HandshakeController {
		$request = $this->createMock(IRequest::class);
		$request->method('getHeader')->willReturnCallback(
			static fn (string $name): string => $name === 'EX-APP-ID' ? $callerAppId : '',
		);

		return new HandshakeController($request, $this->appManager, $this->logger);
	}

	public function testTheBackendGetsTheVersionOfThePhpApp(): void {
		$this->appManager->expects(self::once())
			->method('getAppVersion')
			->with('audio_video_search')
			->willReturn('0.1.0');
		$this->logger->expects(self::never())->method('warning');

		$response = $this->controller($this->backendAppId())->handshake();

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame(['companionVersion' => '0.1.0'], $response->getData());
	}

	public function testAForeignExAppIsRefusedWithAStaticSentence(): void {
		$this->appManager->expects(self::never())->method('getAppVersion');

		$response = $this->controller('some_other_backend')->handshake();

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame(self::FORBIDDEN, $response->getData());
	}

	public function testTheFindlingBackendIsAForeignCallerToo(): void {
		$this->appManager->expects(self::never())->method('getAppVersion');

		$response = $this->controller('findling_backend')->handshake();

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
	}

	public function testACallWithoutTheHeaderIsRefused(): void {
		$response = $this->controller('')->handshake();

		self::assertSame(Http::STATUS_FORBIDDEN, $response->getStatus());
		self::assertSame(self::FORBIDDEN, $response->getData());
	}

	public function testTheRefusalIsLoggedWithTheCallerAppIdAndWithNothingElse(): void {
		$this->logger->expects(self::once())
			->method('warning')
			->with('Audio & Video Search: handshake called by a foreign ExApp', ['app' => 'some_other_backend']);

		$this->controller('some_other_backend')->handshake();
	}
}
