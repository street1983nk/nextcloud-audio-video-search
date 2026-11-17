<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Controller;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Service\JobRegistry;
use OCP\App\IAppManager;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\OCSController;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * The answer to the question of the container: "is the PHP half there?"
 *
 * The container asks at its start and every five minutes. A 404 tells it the
 * PHP app is not installed or not enabled, and the container then refuses to
 * work (it reports companion "missing" in its /status). The answer carries
 * the version of this app and nothing else, so the container can show it.
 */
final class HandshakeController extends OCSController {
	public function __construct(
		IRequest $request,
		private IAppManager $appManager,
		private LoggerInterface $logger,
		private JobRegistry $jobs,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	/**
	 * Full path from the outside:
	 * GET /ocs/v2.php/apps/audio_video_search/api/v1/handshake
	 *
	 * Same attributes and the same first statement as the content gateway:
	 * the attribute admits every registered ExApp, the comparison below only
	 * the one backend of this app.
	 */
	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'GET', url: '/api/v1/handshake')]
	public function handshake(): DataResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		// Only for the own backend: put missing background jobs back
		// (JobRegistry). Nothing that happens there changes the answer.
		try {
			$this->jobs->ensure();
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the background jobs could not be checked', ['class' => $e::class]);
		}

		return new DataResponse(['companionVersion' => $this->appManager->getAppVersion(Application::APP_ID)]);
	}

	/**
	 * The comparison of the EX-APP-ID header against the one backend app id.
	 * AppAPI puts the calling app id into this header after it authenticated
	 * the caller; the residual risk is the same as at the content gateway.
	 */
	private function rejectForeignCaller(): ?DataResponse {
		$callerAppId = $this->request->getHeader('EX-APP-ID');
		if ($callerAppId === Application::BACKEND_APP_ID) {
			return null;
		}

		$this->logger->warning('Audio & Video Search: handshake called by a foreign ExApp', ['app' => $callerAppId]);

		return new DataResponse(
			['error' => 'This route is reserved for the Audio & Video Search backend.'],
			Http::STATUS_FORBIDDEN,
		);
	}
}
