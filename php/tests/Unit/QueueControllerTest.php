<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Tests\Unit;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Controller\QueueController;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\QueueService;
use OCP\AppFramework\Http;
use OCP\IRequest;
use OCP\Security\ISecureRandom;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;
use Psr\Log\LoggerInterface;

/**
 * The queue routes as the container sees them.
 *
 * backend/tests/test_php_gates.py holds the attributes and the guard as the
 * first statement; this suite holds the answers: a foreign ExApp is refused
 * before anything is read, every bound is a 400, and a claim hands out what
 * QueueService::describe() said, under a fresh 32 hex token.
 */
#[CoversClass(QueueController::class)]
final class QueueControllerTest extends TestCase {
	private const TOKEN = '0123456789abcdef0123456789abcdef';

	private QueueService&MockObject $service;
	private ISecureRandom&MockObject $random;

	protected function setUp(): void {
		parent::setUp();

		$this->service = $this->createMock(QueueService::class);
		$this->random = $this->createMock(ISecureRandom::class);
		$this->random->method('generate')->with(32, '0123456789abcdef')->willReturn(self::TOKEN);
	}

	private function backendAppId(): string {
		$value = (new \ReflectionClass(Application::class))->getConstant('BACKEND_APP_ID');

		self::assertIsString($value, 'BACKEND_APP_ID is gone or is no longer a string');

		return $value;
	}

	private function controller(?string $callerAppId = null): QueueController {
		$caller = $callerAppId ?? $this->backendAppId();
		$request = $this->createMock(IRequest::class);
		$request->method('getHeader')->willReturnCallback(
			static fn (string $name): string => $name === 'EX-APP-ID' ? $caller : '',
		);

		return new QueueController($request, $this->service, $this->random, $this->createMock(LoggerInterface::class));
	}

	public function testAForeignExAppIsRefusedOnEveryRoute(): void {
		$this->service->expects(self::never())->method(self::anything());
		$controller = $this->controller('some_other_exapp');

		self::assertSame(Http::STATUS_FORBIDDEN, $controller->claim(5)->getStatus());
		self::assertSame(Http::STATUS_FORBIDDEN, $controller->ack(self::TOKEN, [1])->getStatus());
		self::assertSame(Http::STATUS_FORBIDDEN, $controller->unlock(self::TOKEN, [1])->getStatus());
	}

	/** @return array<string, array{mixed}> */
	public static function badLimits(): array {
		return [
			'zero' => [0],
			'too many' => [257],
			'negative' => [-1],
			'not canonical' => ['05'],
			'not a number' => ['5x'],
			'missing' => [null],
			'a list' => [[5]],
		];
	}

	#[DataProvider('badLimits')]
	public function testALimitOutsideOneTo256IsA400(mixed $limit): void {
		$this->service->expects(self::never())->method('claim');

		self::assertSame(Http::STATUS_BAD_REQUEST, $this->controller()->claim($limit)->getStatus());
	}

	public function testAClaimHandsOutTheDescribedItemsUnderAFreshToken(): void {
		$rows = [['id' => 7, 'kind' => 'content', 'fileId' => 42, 'storageId' => 3, 'attempts' => 1, 'origin' => 'event']];
		$item = array_fill_keys(QueueService::ITEM_KEYS, null);
		$item['queueId'] = 7;
		$open = array_fill_keys(QueueMapper::KINDS, 0);
		$this->service->expects(self::once())->method('claim')->with(256, self::TOKEN)->willReturn($rows);
		$this->service->expects(self::once())->method('describe')->with(self::TOKEN, $rows)
			->willReturn(['items' => [$item], 'dropped' => 2]);
		$this->service->method('stats')->willReturn(['ok' => true, 'open' => $open]);

		$response = $this->controller()->claim(256);

		self::assertSame(Http::STATUS_OK, $response->getStatus());
		self::assertSame(
			['claimToken' => self::TOKEN, 'items' => [$item], 'stats' => ['ok' => true, 'open' => $open, 'dropped' => 2]],
			$response->getData(),
		);
	}

	public function testALimitFromAQueryStringIsAccepted(): void {
		$this->service->expects(self::once())->method('claim')->with(1, self::TOKEN)->willReturn([]);
		$this->service->method('describe')->willReturn(['items' => [], 'dropped' => 0]);
		$this->service->method('stats')->willReturn(['ok' => true, 'open' => []]);

		self::assertSame(Http::STATUS_OK, $this->controller()->claim('1')->getStatus());
	}

	/** @return array<string, array{mixed, mixed}> */
	public static function badAcks(): array {
		$tooMany = range(1, 257);

		return [
			'too many ids' => [self::TOKEN, $tooMany],
			'not numbers' => [self::TOKEN, ['x']],
			'a zero id' => [self::TOKEN, [0]],
			'no list' => [self::TOKEN, 5],
			'an empty list' => [self::TOKEN, []],
			'a short token' => ['abc', [1]],
			'an upper case token' => [strtoupper(self::TOKEN), [1]],
			'no token' => [null, [1]],
		];
	}

	#[DataProvider('badAcks')]
	public function testAnInvalidAckOrUnlockIsA400(mixed $token, mixed $ids): void {
		$this->service->expects(self::never())->method('acknowledge');
		$this->service->expects(self::never())->method('unlock');
		$controller = $this->controller();

		self::assertSame(Http::STATUS_BAD_REQUEST, $controller->ack($token, $ids)->getStatus());
		self::assertSame(Http::STATUS_BAD_REQUEST, $controller->unlock($token, $ids)->getStatus());
	}

	public function testAckAndUnlockPassTheTokenAndTheIds(): void {
		$this->service->expects(self::once())->method('acknowledge')->with(self::TOKEN, [1, 2])->willReturn(2);
		$this->service->expects(self::once())->method('unlock')->with(self::TOKEN, [3])->willReturn(1);
		$controller = $this->controller();

		self::assertSame(['acknowledged' => 2], $controller->ack(self::TOKEN, [1, 2, 2])->getData());
		self::assertSame(['released' => 1], $controller->unlock(self::TOKEN, ['3'])->getData());
	}

	public function testAListOf256IdsIsAccepted(): void {
		$ids = range(1, 256);
		$this->service->expects(self::once())->method('acknowledge')->with(self::TOKEN, $ids)->willReturn(256);

		self::assertSame(Http::STATUS_OK, $this->controller()->ack(self::TOKEN, $ids)->getStatus());
	}
}
