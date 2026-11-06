<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Controller;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Search\Provider;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataResponse;
use OCP\IAppConfig;
use OCP\IConfig;
use OCP\IRequest;
use OCP\IUserSession;
use Psr\Log\LoggerInterface;

/**
 * The two addresses the admin page asks, and the only two (Findling pattern).
 *
 * One reads the state of the other half for "Check again", one writes the
 * switch of the test result. Both live under /apps/audio_video_search/ and
 * outside the OCS space.
 *
 * Their protection is what is missing from them: neither carries an attribute
 * that lifts the admin requirement, the request token or the session, and
 * none that lets a registered container in. So the security middleware of the
 * server demands a signed in administrator with the request token of the
 * session (T-01-32). SettingsControllerTest reads the attributes and holds it.
 *
 * Every error answer is a static English sentence, every log line carries the
 * exception and nothing a user wrote.
 */
final class SettingsController extends Controller {
	public function __construct(
		IRequest $request,
		private ExAppService $exAppService,
		private IAppConfig $appConfig,
		private IConfig $config,
		private IUserSession $userSession,
		private LoggerInterface $logger,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	/**
	 * GET /apps/audio_video_search/admin/state
	 *
	 * The state of the other half, determined anew under the signed in admin:
	 * codes, versions and numbers, the same shape the admin page rendered.
	 */
	#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'GET', url: '/admin/state')]
	public function state(): DataResponse {
		try {
			return new DataResponse($this->exAppService->backendState($this->userId()));
		} catch (\Throwable $e) {
			$this->logger->error('Audio & Video Search: could not check the backend state', ['exception' => $e]);

			return new DataResponse(
				['error' => 'The state could not be checked.'],
				Http::STATUS_INTERNAL_SERVER_ERROR,
			);
		}
	}

	/**
	 * POST /apps/audio_video_search/admin/sample {"visible": bool}
	 *
	 * Only with 'debug' => true in config.php, decided here on the server and
	 * not only by hiding the switch (T-01-33); without it the answer is 403
	 * and nothing is written. The search provider reads the same two values.
	 *
	 * Only a real boolean is taken, or the exact words "true" and "false" of a
	 * form value. Anything else is refused with 400 and writes nothing.
	 */
	#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'POST', url: '/admin/sample')]
	public function setSample(mixed $visible = null): DataResponse {
		if (!$this->config->getSystemValueBool('debug', false)) {
			$this->logger->warning('Audio & Video Search: refused the test result switch outside debug mode');

			return new DataResponse(['error' => 'Debug mode is off.'], Http::STATUS_FORBIDDEN);
		}

		$wish = match (true) {
			$visible === true, $visible === 'true' => true,
			$visible === false, $visible === 'false' => false,
			default => null,
		};
		if ($wish === null) {
			$this->logger->warning('Audio & Video Search: refused a test result switch without a boolean');

			return new DataResponse(['error' => 'visible must be a boolean'], Http::STATUS_BAD_REQUEST);
		}

		try {
			$this->appConfig->setValueBool(Application::APP_ID, Provider::KEY_SAMPLE_VISIBLE, $wish);
		} catch (\Throwable $e) {
			$this->logger->error('Audio & Video Search: could not store the test result switch', ['exception' => $e]);

			return new DataResponse(
				['error' => 'The switch could not be saved.'],
				Http::STATUS_INTERNAL_SERVER_ERROR,
			);
		}

		return new DataResponse(['visible' => $wish]);
	}

	/** The signed in admin, or an empty string that ends in no_app_api. */
	private function userId(): string {
		return $this->userSession->getUser()?->getUID() ?? '';
	}
}
