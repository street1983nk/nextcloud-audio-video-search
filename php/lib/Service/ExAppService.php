<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCP\App\IAppManager;
use OCP\Http\Client\IResponse;
use OCP\IAppConfig;
use OCP\IUserManager;
use Psr\Container\ContainerExceptionInterface;
use Psr\Container\NotFoundExceptionInterface;
use Psr\Log\LoggerInterface;

/**
 * The one and only place in this app that talks to the container.
 *
 * A reduced copy of the Findling class of the same name. Keeping the call in a
 * single class keeps the timeout, the shape of an error and the way this app
 * degrades in exactly one spot; backend/tests/test_php_gates.py (rule 3) holds
 * the AppAPI call to this file. Every failure mode ends in null: a missing,
 * stopped or slow backend must cost the user a result group, never the whole
 * search.
 *
 * The container is outside the trust boundary. Everything it sends is checked
 * field by field (types and ranges) and whatever does not fit is dropped. A
 * hit is reduced to file id, start time, excerpt and the sample flag; a title
 * or a path the container volunteers never gets through, because title and
 * path of a hit come out of the node the provider confirmed.
 *
 * Nothing here writes user content into the log: routes, status codes and
 * timings are logged, search terms, excerpts, user ids and file names are not.
 *
 * The contract, as the container implements it (plan 05):
 *   POST /search         {term, limit}         -> {appVersion, hits: [{fileId, startMs, excerpt, sample}]}
 *   POST /excerpt        {fileId, atMs}        -> {known, excerpt}
 *   POST /sample         {fileId, userId, atMs} -> {result, mediaId, indexRev} | {error}
 *   POST /sample/remove  {fileId}              -> {result, mediaId}
 *
 * The lockstep check is NOT an authentication. appVersion comes from the
 * environment AppAPI set, so it is as trustworthy as the registration. What
 * keeps a foreign container out is the signed AppAPI path plus
 * rejectForeignCaller on the routes of this app.
 *
 * @final Not meant to be extended. The keyword is missing only because PHPUnit
 *        cannot double a final class, and the provider and the occ command take
 *        this class by its concrete type.
 */
class ExAppService {
	/**
	 * One and a half seconds per call: the unified search waits for every
	 * provider, and the provider budgets 2.5 s for its whole result group.
	 */
	public const REQUEST_TIMEOUT_SECONDS = 1.5;

	/**
	 * The occ sample command has nobody waiting in a search dialog, and its
	 * call makes the container read the whole file through the content gateway
	 * and hash it. 1.5 s would refuse any real recording.
	 */
	public const SAMPLE_TIMEOUT_SECONDS = 120.0;

	public const LOCKSTEP_MATCH = 'match';
	public const LOCKSTEP_DRIFT = 'drift';
	public const LOCKSTEP_UNKNOWN = 'unknown';

	/** The version of the other half, as it was last reported. */
	public const KEY_BACKEND_VERSION = 'backend_app_version';

	/** The closed set of error codes of POST /sample. */
	public const SAMPLE_ERRORS = ['companion_missing', 'gateway_denied', 'gateway_failed'];

	private const SAMPLE_RESULTS = ['published', 'stale_rejected'];
	private const REMOVE_RESULTS = ['removed', 'not_found', 'not_sample'];

	/**
	 * What a version has to look like before it is compared or stored: major
	 * and minor mandatory, patch optional, a prerelease tail allowed.
	 */
	private const VERSION_PATTERN = '/^\d{1,5}\.\d{1,5}(?:\.[0-9A-Za-z][0-9A-Za-z.-]{0,19})?$/D';

	/** Hard ceiling on an answer before it is parsed. */
	private const MAX_BODY_BYTES = 1048576;

	/** The term ceiling of the contract, in characters. */
	public const MAX_TERM_LENGTH = 200;

	private const MIN_LIMIT = 1;
	private const MAX_LIMIT = 50;

	/** Defense in depth: the provider shortens to 120 characters anyway. */
	private const MAX_EXCERPT_LENGTH = 1000;

	public function __construct(
		private IAppManager $appManager,
		private IUserManager $userManager,
		private IAppConfig $appConfig,
		private LoggerInterface $logger,
	) {
	}

	// -- the four calls of the contract -----------------------------------------

	/**
	 * Hits for one term, or null when there is no usable answer.
	 *
	 * Null and an empty list are two different answers: null means the
	 * backend is missing, slow or broken, an empty list means it found nothing.
	 * An empty term is an empty list without a call.
	 *
	 * @return list<array{fileId:int,startMs:int,excerpt:string,sample:bool}>|null
	 */
	public function search(string $uid, string $term, int $limit): ?array {
		$term = mb_substr(trim($term), 0, self::MAX_TERM_LENGTH);
		if ($term === '') {
			return [];
		}

		$answer = $this->call('/search', $uid, [
			'term' => $term,
			'limit' => max(self::MIN_LIMIT, min(self::MAX_LIMIT, $limit)),
		], self::REQUEST_TIMEOUT_SECONDS);
		if ($answer === null || !isset($answer['hits']) || !is_array($answer['hits'])) {
			return null;
		}

		if (is_string($answer['appVersion'] ?? null)) {
			$version = $this->versionOrNothing($answer['appVersion']);
			if ($version !== '') {
				$this->rememberBackendVersion($version);
			}
		}

		return $this->filterHits($answer['hits']);
	}

	/**
	 * The excerpt of one file at one point in time.
	 *
	 * @return array{known:bool,excerpt:?string}|null
	 */
	public function excerpt(string $uid, int $fileId, int $startMs): ?array {
		if ($fileId <= 0 || $startMs < 0) {
			return null;
		}

		$answer = $this->call('/excerpt', $uid, ['fileId' => $fileId, 'atMs' => $startMs], self::REQUEST_TIMEOUT_SECONDS);
		if ($answer === null || !is_bool($answer['known'] ?? null)) {
			return null;
		}

		$raw = $answer['excerpt'] ?? null;
		if ($raw === null) {
			return ['known' => $answer['known'], 'excerpt' => null];
		}
		if (!is_string($raw)) {
			return null;
		}

		$text = self::plainText($raw, self::MAX_EXCERPT_LENGTH);

		return $text === null ? null : ['known' => $answer['known'], 'excerpt' => $text];
	}

	/**
	 * Ask the container to publish a test result for one file (occ only).
	 *
	 * @return array{result:string,mediaId:int,indexRev:?int}|array{error:string}|null
	 */
	public function sample(string $uid, int $fileId, int $atMs): ?array {
		if ($fileId <= 0 || $atMs < 0) {
			return null;
		}

		$answer = $this->call('/sample', $uid, [
			'fileId' => $fileId,
			'userId' => $uid,
			'atMs' => $atMs,
		], self::SAMPLE_TIMEOUT_SECONDS);
		if ($answer === null) {
			return null;
		}

		if (isset($answer['error'])) {
			return is_string($answer['error']) && in_array($answer['error'], self::SAMPLE_ERRORS, true)
				? ['error' => $answer['error']]
				: null;
		}

		$result = $answer['result'] ?? null;
		$mediaId = $answer['mediaId'] ?? null;
		$indexRev = $answer['indexRev'] ?? null;
		if (!is_string($result) || !in_array($result, self::SAMPLE_RESULTS, true)
			|| !is_int($mediaId) || $mediaId <= 0
			|| ($indexRev !== null && (!is_int($indexRev) || $indexRev < 0))) {
			return null;
		}

		return ['result' => $result, 'mediaId' => $mediaId, 'indexRev' => $indexRev];
	}

	/**
	 * Ask the container to remove a test result with its index entries (occ
	 * only). A real transcript is answered with not_sample and stays.
	 *
	 * @return array{result:string,mediaId:?int}|null
	 */
	public function removeSample(string $uid, int $fileId): ?array {
		if ($fileId <= 0) {
			return null;
		}

		$answer = $this->call('/sample/remove', $uid, ['fileId' => $fileId], self::SAMPLE_TIMEOUT_SECONDS);
		if ($answer === null) {
			return null;
		}

		$result = $answer['result'] ?? null;
		$mediaId = $answer['mediaId'] ?? null;
		if (!is_string($result) || !in_array($result, self::REMOVE_RESULTS, true)
			|| ($mediaId !== null && (!is_int($mediaId) || $mediaId <= 0))) {
			return null;
		}

		return ['result' => $result, 'mediaId' => $mediaId];
	}

	// -- lockstep ---------------------------------------------------------------

	/**
	 * The lockstep verdict for a version the other half reported.
	 *
	 * Major and minor are compared exactly, the patch part is not: the
	 * protocol between the halves changes with a minor by release policy. A
	 * missing or malformed version is unknown and never drift, because a
	 * container that answers nonsense is a broken container, not a reason to
	 * switch the search off. A valid version is remembered.
	 */
	public function lockstep(?string $backendVersion): string {
		$own = $this->ownVersion();
		$other = $this->versionOrNothing($backendVersion ?? '');
		if ($own === '' || $other === '') {
			return self::LOCKSTEP_UNKNOWN;
		}

		$this->rememberBackendVersion($other);

		return $this->majorMinor($own) === $this->majorMinor($other)
			? self::LOCKSTEP_MATCH
			: self::LOCKSTEP_DRIFT;
	}

	/**
	 * The drift on record, for a caller that cannot ask the container. Null
	 * means nothing to act on: the versions agree, or none was ever recorded.
	 *
	 * @return array{companion:string, container:string}|null
	 */
	public function driftOnRecord(): ?array {
		$container = $this->versionOrNothing(
			$this->appConfig->getValueString(Application::APP_ID, self::KEY_BACKEND_VERSION, ''),
		);
		if ($container === '') {
			return null;
		}

		$companion = $this->ownVersion();
		if ($companion === '' || $this->majorMinor($companion) === $this->majorMinor($container)) {
			return null;
		}

		return ['companion' => $companion, 'container' => $container];
	}

	/**
	 * Whether the search may ask the container at all. A drift of major or
	 * minor answers nothing rather than something: neither half can say what
	 * the other one meant, so a hit would be a guess. Plan 07 extends this.
	 */
	public function searchAllowed(): bool {
		return $this->driftOnRecord() === null;
	}

	/** The version of this half, or an empty string when it has no shape. */
	public function ownVersion(): string {
		return $this->versionOrNothing($this->appManager->getAppVersion(Application::APP_ID));
	}

	/** Major and minor of a version as one string, or null for a non version. */
	public function majorMinor(string $version): ?string {
		$candidate = $this->versionOrNothing($version);
		if ($candidate === '') {
			return null;
		}

		$parts = explode('.', $candidate);

		return $parts[0] . '.' . $parts[1];
	}

	private function versionOrNothing(string $version): string {
		$candidate = trim($version);

		return preg_match(self::VERSION_PATTERN, $candidate) === 1 ? $candidate : '';
	}

	/** Remember the version of the other half, and only when it changed. */
	private function rememberBackendVersion(string $version): void {
		if ($version === $this->appConfig->getValueString(Application::APP_ID, self::KEY_BACKEND_VERSION, '')) {
			return;
		}

		$this->appConfig->setValueString(Application::APP_ID, self::KEY_BACKEND_VERSION, $version);
	}

	// -- transport --------------------------------------------------------------

	/**
	 * The single outbound call of this app, through AppAPI.
	 *
	 * Protected rather than private as the one concession to the unit suite:
	 * the AppAPI class is absent from the autoload space the suite runs in, so
	 * this method is what gets doubled. Nothing in this repository overrides it.
	 *
	 * @param array<string,mixed> $params
	 * @return array<mixed>|IResponse|null null when the pre-flight refused, an
	 *                                     array when AppAPI turned a transport
	 *                                     failure into one, a response otherwise
	 */
	protected function proxyRequest(string $route, string $userId, string $method, array $params, float $timeout): array|IResponse|null {
		$appApi = $this->publicFunctions($userId);
		if ($appApi === null) {
			return null;
		}

		return $appApi->exAppRequest(
			Application::BACKEND_APP_ID,
			$route,
			$userId,
			$method,
			$params,
			['timeout' => $timeout],
		);
	}

	/**
	 * The pre-flight: a real user, app_api enabled for them, and the public
	 * functions of AppAPI resolvable. info.xml cannot declare an app to app
	 * dependency, so the bond to app_api is a runtime check.
	 */
	private function publicFunctions(string $userId): ?\OCA\AppAPI\PublicFunctions {
		$user = $this->userManager->get($userId);
		if ($user === null) {
			$this->logger->info('Audio & Video Search: unknown user, no call to the backend');
			return null;
		}

		if (!$this->appManager->isEnabledForUser('app_api', $user)) {
			$this->logger->info('Audio & Video Search: app_api is not enabled, no call to the backend');
			return null;
		}

		try {
			return \OCP\Server::get(\OCA\AppAPI\PublicFunctions::class);
		} catch (ContainerExceptionInterface|NotFoundExceptionInterface) {
			$this->logger->info('Audio & Video Search: AppAPI public functions unavailable');
			return null;
		}
	}

	/**
	 * The four silent failure cases, in one place for every call: an array
	 * from AppAPI (transport failure), a status of 400 and above, a body that
	 * is not a bounded string, a body that does not parse into an object.
	 * None of them throws, every one of them ends in null.
	 *
	 * @param array<string,mixed> $body
	 * @return array<mixed>|null
	 */
	private function call(string $route, string $userId, array $body, float $timeout): ?array {
		$startedAt = hrtime(true);
		$response = $this->proxyRequest($route, $userId, 'POST', $body, $timeout);
		$innerMs = round((hrtime(true) - $startedAt) / 1000000, 1);

		if ($response === null) {
			return null;
		}

		// Case 1 first, always: AppAPI catches every transport exception and
		// hands back an array. Calling a method on it would be a fatal error.
		if (is_array($response)) {
			$this->logger->warning('Audio & Video Search: backend unreachable', [
				'route' => $route,
				'error' => is_string($response['error'] ?? null) ? mb_substr($response['error'], 0, 200) : 'unknown',
				'innerMs' => $innerMs,
			]);
			return null;
		}

		// Case 2: AppAPI sets http_errors to false, so 4xx and 5xx arrive here.
		if ($response->getStatusCode() >= 400) {
			$this->logger->warning('Audio & Video Search: backend returned an error', [
				'route' => $route,
				'status' => $response->getStatusCode(),
				'innerMs' => $innerMs,
			]);
			return null;
		}

		// Case 3: the length is checked before the parser builds the tree.
		$responseBody = $response->getBody();
		if (!is_string($responseBody) || strlen($responseBody) > self::MAX_BODY_BYTES) {
			$this->logger->warning('Audio & Video Search: backend answer is not a bounded string body', [
				'route' => $route,
				'innerMs' => $innerMs,
			]);
			return null;
		}

		// Case 4: only a JSON object is an answer; a list is not.
		$decoded = json_decode($responseBody, true);
		if (!is_array($decoded) || ($decoded !== [] && array_is_list($decoded))) {
			$this->logger->warning('Audio & Video Search: malformed backend response', [
				'route' => $route,
				'innerMs' => $innerMs,
			]);
			return null;
		}

		return $decoded;
	}

	// -- field checks -----------------------------------------------------------

	/**
	 * What survives of a hit: file id, start time, excerpt and the sample flag,
	 * each with its type and range, and nothing else.
	 *
	 * @param array<mixed> $hits
	 * @return list<array{fileId:int,startMs:int,excerpt:string,sample:bool}>
	 */
	private function filterHits(array $hits): array {
		$kept = [];
		$dropped = 0;

		foreach ($hits as $hit) {
			if (!is_array($hit)) {
				$dropped++;
				continue;
			}

			$fileId = $hit['fileId'] ?? null;
			$startMs = $hit['startMs'] ?? null;
			$excerpt = $hit['excerpt'] ?? null;
			$sample = $hit['sample'] ?? null;
			if (!is_int($fileId) || $fileId <= 0
				|| !is_int($startMs) || $startMs < 0
				|| !is_string($excerpt) || !is_bool($sample)) {
				$dropped++;
				continue;
			}

			$text = self::plainText($excerpt, self::MAX_EXCERPT_LENGTH);
			if ($text === null) {
				$dropped++;
				continue;
			}

			$kept[] = ['fileId' => $fileId, 'startMs' => $startMs, 'excerpt' => $text, 'sample' => $sample];
		}

		if ($dropped > 0) {
			$this->logger->warning('Audio & Video Search: dropped malformed hits', ['count' => $dropped]);
		}

		return $kept;
	}

	/**
	 * A string as plain text: valid UTF-8, control characters replaced by a
	 * space, at most $max characters. Null when it is not UTF-8 at all.
	 */
	private static function plainText(string $raw, int $max): ?string {
		if (!mb_check_encoding($raw, 'UTF-8')) {
			return null;
		}

		$clean = preg_replace('/[\x00-\x1F\x7F]/u', ' ', $raw);

		return is_string($clean) ? mb_substr($clean, 0, $max) : null;
	}
}
