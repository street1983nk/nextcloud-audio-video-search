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
 * The addresses the admin page asks, and the only ones (Findling pattern).
 *
 * One reads the state of the other half for "Check again", one writes the
 * switch of the test result, and since plan 05-05 two read and write profile,
 * threads, window and offline switch of the container. All live under
 * /apps/audio_video_search/ and outside the OCS space.
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
	/** The keys a resources body may carry, and no other. */
	private const RESOURCE_BODY_KEYS = ['profile', 'threads', 'window', 'offline'];

	/** What the framework itself adds to the request parameters. */
	private const FRAMEWORK_KEYS = ['_route'];

	private const NO_BACKEND = 'The backend did not answer.';

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
			$this->logger->error('Audio & Video Search: could not check the backend state', ['class' => $e::class]);

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
			$this->logger->error('Audio & Video Search: could not store the test result switch', ['class' => $e::class]);

			return new DataResponse(
				['error' => 'The switch could not be saved.'],
				Http::STATUS_INTERNAL_SERVER_ERROR,
			);
		}

		return new DataResponse(['visible' => $wish]);
	}

	/**
	 * GET /apps/audio_video_search/admin/resources
	 *
	 * Profile, threads, window, models and offline switch of the container in
	 * the contract shape ExAppService checked, plus the zones PHP knows and
	 * the zone the window field starts with. A silent container is 503.
	 */
	#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'GET', url: '/admin/resources')]
	public function resources(): DataResponse {
		$resources = $this->exAppService->resources();
		if ($resources === null) {
			return new DataResponse(['error' => self::NO_BACKEND], Http::STATUS_SERVICE_UNAVAILABLE);
		}

		return new DataResponse($this->withZones($resources));
	}

	/**
	 * POST /apps/audio_video_search/admin/resources
	 *   {profile?, threads?, window?, offline?}, at least one of them
	 *
	 * Checked strictly here before the container is asked (T-05-11), and once
	 * more by the container: profile one of the three ids, threads null (the
	 * default) or a whole number from 1 to the default of the container
	 * (only lowering, T-05-08), window null (always, D-05-03) or exactly
	 * {start, end, zone} with HH:MM times that differ and a zone of
	 * DateTimeZone::listIdentifiers(), offline a boolean, no other key. A
	 * refusal is 400 with the field code. 409 profile_locked of the container
	 * comes through with its numbers.
	 */
	#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'POST', url: '/admin/resources')]
	public function saveResources(mixed $profile = null, mixed $threads = null, mixed $window = null, mixed $offline = null): DataResponse {
		$sent = array_diff(array_map('strval', array_keys($this->request->getParams())), self::FRAMEWORK_KEYS);
		if ($sent === [] || array_diff($sent, self::RESOURCE_BODY_KEYS) !== []) {
			return $this->refuse('body');
		}

		$body = [];
		if (in_array('profile', $sent, true)) {
			if (!is_string($profile) || !in_array($profile, ExAppService::RESOURCE_PROFILES, true)) {
				return $this->refuse('profile');
			}
			$body['profile'] = $profile;
		}
		if (in_array('offline', $sent, true)) {
			if (!is_bool($offline)) {
				return $this->refuse('offline');
			}
			$body['offline'] = $offline;
		}
		if (in_array('window', $sent, true)) {
			$field = self::windowField($window);
			if ($field !== null) {
				return $this->refuse($field);
			}
			$body['window'] = $window;
		}
		if (in_array('threads', $sent, true)) {
			if ($threads !== null && (!is_int($threads) || $threads < 1)) {
				return $this->refuse('threads');
			}
			if ($threads !== null) {
				// The ceiling is the default of the container: the admin only lowers.
				$resources = $this->exAppService->resources();
				if ($resources === null) {
					return new DataResponse(['error' => self::NO_BACKEND], Http::STATUS_SERVICE_UNAVAILABLE);
				}
				$standard = $resources['threads']['standard'] ?? null;
				if (!is_int($standard) || $threads > $standard) {
					return $this->refuse('threads');
				}
			}
			$body['threads'] = $threads;
		}

		$answer = $this->exAppService->saveResources($body);
		$data = $answer['body'];
		if ($data === null || !in_array($answer['status'], [Http::STATUS_OK, Http::STATUS_BAD_REQUEST, Http::STATUS_CONFLICT], true)) {
			return new DataResponse(['error' => self::NO_BACKEND], Http::STATUS_SERVICE_UNAVAILABLE);
		}
		if ($answer['status'] === Http::STATUS_OK) {
			$data = $this->withZones($data);
		}

		return new DataResponse($data, $answer['status']);
	}

	/**
	 * The field code that refuses a window, or null when it is fine.
	 *
	 * null is "always". Otherwise exactly start, end and zone: a missing or
	 * malformed time names its field, an unknown zone window_zone, equal
	 * times window_same, a foreign key or a value that is no object body.
	 */
	private static function windowField(mixed $window): ?string {
		if ($window === null) {
			return null;
		}
		if (!is_array($window) || array_diff(array_map('strval', array_keys($window)), ['start', 'end', 'zone']) !== []) {
			return 'body';
		}
		$start = $window['start'] ?? null;
		$end = $window['end'] ?? null;
		$zone = $window['zone'] ?? null;
		if (!is_string($start) || preg_match(ExAppService::TIME_PATTERN, $start) !== 1) {
			return 'window_start';
		}
		if (!is_string($end) || preg_match(ExAppService::TIME_PATTERN, $end) !== 1) {
			return 'window_end';
		}
		if ($start === $end) {
			return 'window_same';
		}
		if (!is_string($zone) || !ExAppService::isZone($zone)) {
			return 'window_zone';
		}

		return null;
	}

	/** 400 with a field code; the log names the code, never what was sent. */
	private function refuse(string $field): DataResponse {
		$this->logger->warning('Audio & Video Search: refused a resources setting', ['field' => $field]);

		return new DataResponse(['field' => $field], Http::STATUS_BAD_REQUEST);
	}

	/**
	 * The answer of the container plus the zones of PHP and the zone the
	 * window field starts with; the rule itself lives in ExAppService, the
	 * admin page uses the same one.
	 *
	 * @param array<string, mixed> $resources
	 * @return array<string, mixed>
	 */
	private function withZones(array $resources): array {
		return ExAppService::withZones($resources, $this->config, $this->userId());
	}

	/** The signed in admin, or an empty string that ends in no_app_api. */
	private function userId(): string {
		return $this->userSession->getUser()?->getUID() ?? '';
	}
}
