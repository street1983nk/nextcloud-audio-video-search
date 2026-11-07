<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Controller;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Service\QueueService;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\OCSController;
use OCP\IRequest;
use OCP\Security\ISecureRandom;
use Psr\Log\LoggerInterface;

/**
 * The work stock routes for the container (after Findling's QueueController).
 *
 *   POST /ocs/v2.php/apps/audio_video_search/queues/media/claim   {"limit": 1..256}
 *   POST /ocs/v2.php/apps/audio_video_search/queues/media/ack     {"claimToken", "queueIds"}
 *   POST /ocs/v2.php/apps/audio_video_search/queues/media/unlock  {"claimToken", "queueIds"}
 *
 * A claim answers {"claimToken", "items", "stats"}. Every item passed
 * QueueService::describe(), the second check at the hand over, and carries the
 * nine keys of QueueService::ITEM_KEYS and nothing else. Acknowledgement and
 * unlock touch only rows of the token they name (T-02-11), and every list is
 * bounded (T-02-10). Invalid input is a 400 whose value never reaches the log.
 */
final class QueueController extends OCSController {
	private const TOKEN_LENGTH = 32;
	private const TOKEN_CHARS = '0123456789abcdef';

	public function __construct(
		IRequest $request,
		private QueueService $queueService,
		private ISecureRandom $secureRandom,
		private LoggerInterface $logger,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'POST', url: '/queues/media/claim')]
	public function claim(mixed $limit = null): DataResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		$count = $this->positiveInt($limit);
		if ($count === null || $count > QueueMapper::MAX_BATCH) {
			return $this->badInput();
		}

		$token = $this->secureRandom->generate(self::TOKEN_LENGTH, self::TOKEN_CHARS);
		$described = $this->queueService->describe($token, $this->queueService->claim($count, $token));
		$stats = $this->queueService->stats();
		$stats['dropped'] = $described['dropped'];

		return new DataResponse([
			'claimToken' => $token,
			'items' => $described['items'],
			'stats' => $stats,
		]);
	}

	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'POST', url: '/queues/media/ack')]
	public function ack(mixed $claimToken = null, mixed $queueIds = null): DataResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		$token = $this->token($claimToken);
		$ids = $this->intList($queueIds);
		if ($token === null || $ids === null) {
			return $this->badInput();
		}

		return new DataResponse(['acknowledged' => $this->queueService->acknowledge($token, $ids)]);
	}

	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'POST', url: '/queues/media/unlock')]
	public function unlock(mixed $claimToken = null, mixed $queueIds = null): DataResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		$token = $this->token($claimToken);
		$ids = $this->intList($queueIds);
		if ($token === null || $ids === null) {
			return $this->badInput();
		}

		return new DataResponse(['released' => $this->queueService->unlock($token, $ids)]);
	}

	/**
	 * The route attributes answer "is this a registered external app", not "is
	 * this our external app"; this comparison keeps every other container out.
	 */
	private function rejectForeignCaller(): ?DataResponse {
		$callerAppId = $this->request->getHeader('EX-APP-ID');
		if ($callerAppId === Application::BACKEND_APP_ID) {
			return null;
		}

		$this->logger->warning('Audio & Video Search: queue route called by a foreign ExApp', ['app' => $callerAppId]);

		return new DataResponse(
			['error' => 'This route is reserved for the Audio & Video Search backend.'],
			Http::STATUS_FORBIDDEN,
		);
	}

	private function token(mixed $value): ?string {
		return is_string($value) && preg_match('/^[0-9a-f]{32}$/', $value) === 1 ? $value : null;
	}

	/**
	 * A non empty list of at most MAX_BATCH positive ids, or null.
	 *
	 * @return list<int>|null
	 */
	private function intList(mixed $raw): ?array {
		if (!is_array($raw) || $raw === [] || count($raw) > QueueMapper::MAX_BATCH) {
			return null;
		}

		$ids = [];
		foreach ($raw as $value) {
			$id = $this->positiveInt($value);
			if ($id === null) {
				return null;
			}
			$ids[] = $id;
		}

		return array_values(array_unique($ids));
	}

	/**
	 * A positive integer from a JSON body (int) or a query string (canonical
	 * digit string), nothing else (Findling positiveId).
	 */
	private function positiveInt(mixed $value): ?int {
		if (is_int($value)) {
			return $value > 0 ? $value : null;
		}
		if (is_string($value) && ctype_digit($value)) {
			$number = (int)$value;
			if ((string)$number !== $value) {
				return null;
			}

			return $number > 0 ? $number : null;
		}

		return null;
	}

	private function badInput(): DataResponse {
		$this->logger->warning('Audio & Video Search: rejected a queue request with invalid input');

		return new DataResponse(['error' => 'Invalid input.'], Http::STATUS_BAD_REQUEST);
	}
}
