<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCP\App\IAppManager;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\Http\Client\IResponse;
use OCP\IAppConfig;
use OCP\IGroupManager;
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
 *   GET  /status                               -> {appVersion, companion, sampleCount, ...}
 *   GET  /workstock      ?state&after&limit    -> {files: [{fileId, mediaId, storageId, state, stage, reason}], next}
 *   GET  /coverage                             -> {contents, transcribed, files, byState, byStage, dueWork}
 *
 * The state of the other half (plan 07, research decision 6) is read in two
 * steps: the registration in AppAPI first, without a network call, then
 * GET /status. Seven codes come out of it, and only ok and
 * version_patch_differs let the search ask the container.
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

	/** Ten seconds for the two admin routes of occ (plan 02-10): counting 140,000 rows takes well under one. */
	public const ADMIN_TIMEOUT_SECONDS = 10.0;

	/** One reconcile round walks mounts and asks PHP for slices: a longer ceiling (plan 02-19). */
	public const RECONCILE_TIMEOUT_SECONDS = 120.0;

	/** The counters of POST /reconcile/run of the container, in this order, and no other. */
	public const RECONCILE_KEYS = ['swept', 'vanished', 'orphaned', 'walkedMounts', 'requeued', 'rejected', 'reproofDue', 'skippedReason'];

	/** The closed lists of the container (backend store/repo.py STATES, STAGES). */
	public const WORK_STATES = ['active', 'unreadable', 'vanished', 'trashed'];
	public const WORK_STAGES = ['pending', 'probing', 'fetching', 'keyed', 'failed'];
	/**
	 * The names of byPreview (backend store/repo.py PREVIEW_STATES and
	 * PREVIEW_REASONS, plan 03-09): a job counts under its reason code, or
	 * under its state when it has none.
	 */
	public const PREVIEW_NAMES = [
		'queued', 'running', 'waiting', 'complete', 'skipped',
		'too_long', 'no_audio', 'damaged', 'protected', 'format_unsupported',
		'no_speech', 'unsupported_language', 'disk_full', 'engine_failed',
	];
	/** The keys of one work stock entry, exactly. */
	public const WORKSTOCK_KEYS = ['fileId', 'mediaId', 'storageId', 'state', 'stage', 'reason'];
	/** The keys of the coverage answer, exactly. */
	public const COVERAGE_KEYS = ['contents', 'transcribed', 'files', 'byState', 'byStage', 'dueWork', 'byPreview'];
	public const WORKSTOCK_MAX_LIMIT = 1000;
	/** A reason is a code of the closed list of the container, never free text. */
	private const REASON_PATTERN = '/^[a-z_]{1,32}$/D';

	public const LOCKSTEP_MATCH = 'match';
	public const LOCKSTEP_DRIFT = 'drift';
	public const LOCKSTEP_UNKNOWN = 'unknown';

	/** The version of the other half, as it was last reported. */
	public const KEY_BACKEND_VERSION = 'backend_app_version';

	/** The seven states of the other half, in the order they are checked. */
	public const STATE_NO_APP_API = 'no_app_api';
	public const STATE_BACKEND_MISSING = 'backend_missing';
	public const STATE_BACKEND_DISABLED = 'backend_disabled';
	public const STATE_VERSION_DRIFT = 'version_drift';
	public const STATE_BACKEND_UNREACHABLE = 'backend_unreachable';
	public const STATE_VERSION_PATCH_DIFFERS = 'version_patch_differs';
	public const STATE_OK = 'ok';

	public const STATES = [
		self::STATE_NO_APP_API,
		self::STATE_BACKEND_MISSING,
		self::STATE_BACKEND_DISABLED,
		self::STATE_VERSION_DRIFT,
		self::STATE_BACKEND_UNREACHABLE,
		self::STATE_VERSION_PATCH_DIFFERS,
		self::STATE_OK,
	];

	/** The two states in which the search asks the container at all. */
	private const SEARCHABLE_STATES = [self::STATE_OK, self::STATE_VERSION_PATCH_DIFFERS];

	/** The last verdict, as JSON of codes, versions and numbers only. */
	public const KEY_BACKEND_STATE = 'backend_state';

	/** How long the search trusts the last verdict before it asks again. */
	public const STATE_MAX_AGE_SECONDS = 60;

	/** What GET /status may say about the PHP half, seen from the container. */
	private const COMPANION_VALUES = ['ok', 'missing', 'unknown'];

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

	/** The deepest offset the container accepts (plan 03-08, MAX_OFFSET). */
	public const MAX_OFFSET = 1200;

	/**
	 * The stages a hit may carry. Anything else, and a missing stage, is shown
	 * as a preview: in doubt a hit is honestly preliminary (UI-SPEC).
	 */
	public const HIT_STAGES = ['preview', 'final', 'sample'];

	/** Defense in depth: the provider shortens to 120 characters anyway. */
	private const MAX_EXCERPT_LENGTH = 1000;

	public function __construct(
		private IAppManager $appManager,
		private IUserManager $userManager,
		private IAppConfig $appConfig,
		private LoggerInterface $logger,
		private IGroupManager $groupManager,
		private ITimeFactory $timeFactory,
	) {
	}

	// -- the four calls of the contract -----------------------------------------

	/**
	 * One page of hits for one term, or null when there is no usable answer.
	 *
	 * Null and an empty page are two different answers: null means the
	 * backend is missing, slow or broken, an empty page means it found nothing.
	 * An empty term is an empty, final page without a call.
	 *
	 * The page is a cut [offset, offset + limit) of the fixed order of the
	 * container (plan 03-08). nextOffset and hasMore are part of the contract:
	 * an answer without them, or with them out of type or range, is no answer
	 * at all, because a provider that guessed them would page into gaps or
	 * doublets.
	 *
	 * @return array{hits:list<array{fileId:int,startMs:int,excerpt:string,sample:bool,stage:string}>,nextOffset:int,hasMore:bool}|null
	 */
	public function search(string $uid, string $term, int $limit, int $offset = 0): ?array {
		$term = mb_substr(trim($term), 0, self::MAX_TERM_LENGTH);
		$offset = max(0, min(self::MAX_OFFSET, $offset));
		if ($term === '') {
			return ['hits' => [], 'nextOffset' => $offset, 'hasMore' => false];
		}

		$answer = $this->call('/search', $uid, [
			'term' => $term,
			'limit' => max(self::MIN_LIMIT, min(self::MAX_LIMIT, $limit)),
			'offset' => $offset,
		], self::REQUEST_TIMEOUT_SECONDS);
		if ($answer === null || !isset($answer['hits']) || !is_array($answer['hits'])) {
			return null;
		}
		$nextOffset = $answer['nextOffset'] ?? null;
		$hasMore = $answer['hasMore'] ?? null;
		if (!is_int($nextOffset) || $nextOffset < 0 || !is_bool($hasMore)) {
			return null;
		}

		if (is_string($answer['appVersion'] ?? null)) {
			$version = $this->versionOrNothing($answer['appVersion']);
			if ($version !== '') {
				$this->rememberBackendVersion($version);
			}
		}

		return ['hits' => $this->filterHits($answer['hits']), 'nextOffset' => $nextOffset, 'hasMore' => $hasMore];
	}

	/**
	 * The excerpt of one file at one point in time, with the stage of the
	 * text, the state of a file that is still being transcribed and the reason
	 * of a file that was not (plan 03-16).
	 *
	 * The container answers {known: false} for every file it may not speak
	 * about (UI-SPEC, leak rule); with known false every other field is
	 * ignored, so nothing it sent along can reach the page. With known true
	 * each field is checked for its type and range, and one field out of type
	 * makes the whole answer no answer (state A12): a page that guessed would
	 * show a reason or a hint that may not be true.
	 *
	 * - stage: one of HIT_STAGES or null; another text is null (shown as a
	 *   preview, like a hit of the search), anything else invalidates.
	 * - partial, pendingHere: bool, missing is false.
	 * - reason: a text or null. It is a key for the closed list of the
	 *   controller and never printed; the controller maps an unknown text to
	 *   "another reason".
	 * - limitHours: an int from 1 to 24, missing or null is null. It is the
	 *   setting of the instance, never the length of the file.
	 *
	 * @return array{known:bool,excerpt:?string,stage:?string,partial:bool,pendingHere:bool,reason:?string,limitHours:?int}|null
	 */
	public function excerpt(string $uid, int $fileId, int $startMs): ?array {
		if ($fileId <= 0 || $startMs < 0) {
			return null;
		}

		$answer = $this->call('/excerpt', $uid, ['fileId' => $fileId, 'atMs' => $startMs], self::REQUEST_TIMEOUT_SECONDS);
		if ($answer === null || !is_bool($answer['known'] ?? null)) {
			return null;
		}

		$unknown = [
			'known' => false,
			'excerpt' => null,
			'stage' => null,
			'partial' => false,
			'pendingHere' => false,
			'reason' => null,
			'limitHours' => null,
		];
		if ($answer['known'] === false) {
			return $unknown;
		}

		$raw = $answer['excerpt'] ?? null;
		$text = null;
		if ($raw !== null) {
			if (!is_string($raw)) {
				return null;
			}
			$text = self::plainText($raw, self::MAX_EXCERPT_LENGTH);
			if ($text === null) {
				return null;
			}
		}

		$stage = $answer['stage'] ?? null;
		if ($stage !== null && !is_string($stage)) {
			return null;
		}
		if ($stage !== null && !in_array($stage, self::HIT_STAGES, true)) {
			$stage = null;
		}

		$partial = array_key_exists('partial', $answer) ? $answer['partial'] : false;
		$pendingHere = array_key_exists('pendingHere', $answer) ? $answer['pendingHere'] : false;
		if (!is_bool($partial) || !is_bool($pendingHere)) {
			return null;
		}

		$reason = $answer['reason'] ?? null;
		if ($reason !== null && !is_string($reason)) {
			return null;
		}

		$limitHours = $answer['limitHours'] ?? null;
		if ($limitHours !== null && (!is_int($limitHours) || $limitHours < 1 || $limitHours > 24)) {
			return null;
		}

		return [
			'known' => true,
			'excerpt' => $text,
			'stage' => $stage,
			'partial' => $partial,
			'pendingHere' => $pendingHere,
			'reason' => $reason,
			'limitHours' => $limitHours,
		];
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

	/**
	 * One page of the work stock of the container (occ audio_video_search:files).
	 *
	 * $query takes state (a code of WORK_STATES), after (>= 0) and limit (1 to
	 * 1000); anything else is not sent. The answer is checked key by key and
	 * value by value: a page with one entry out of shape is no page at all,
	 * so the command never prints a half answer.
	 *
	 * @param array{state?: string, after?: int, limit?: int} $query
	 * @return array{files: list<array{fileId: int, mediaId: ?int, storageId: int, state: string, stage: string, reason: ?string}>, next: ?int}|null
	 */
	public function workstock(array $query): ?array {
		$params = [];
		if (isset($query['state'])) {
			if (!in_array($query['state'], self::WORK_STATES, true)) {
				return null;
			}
			$params['state'] = $query['state'];
		}
		if (isset($query['after'])) {
			if ($query['after'] < 0) {
				return null;
			}
			$params['after'] = $query['after'];
		}
		if (isset($query['limit'])) {
			if ($query['limit'] < 1 || $query['limit'] > self::WORKSTOCK_MAX_LIMIT) {
				return null;
			}
			$params['limit'] = $query['limit'];
		}

		$uid = $this->firstAdmin();
		if ($uid === null) {
			return null;
		}
		$answer = $this->call('/workstock', $uid, $params, self::ADMIN_TIMEOUT_SECONDS, 'GET');
		if ($answer === null || !self::hasExactKeys($answer, ['files', 'next'])) {
			return null;
		}

		$next = $answer['next'];
		if ($next !== null && (!is_int($next) || $next <= 0)) {
			return null;
		}
		if (!is_array($answer['files']) || !array_is_list($answer['files'])) {
			return null;
		}

		$files = [];
		foreach ($answer['files'] as $entry) {
			$checked = self::workstockEntry($entry);
			if ($checked === null) {
				$this->logger->warning('Audio & Video Search: malformed work stock entry, page dropped');
				return null;
			}
			$files[] = $checked;
		}

		return ['files' => $files, 'next' => $next];
	}

	/**
	 * @return array{fileId: int, mediaId: ?int, storageId: int, state: string, stage: string, reason: ?string}|null
	 */
	private static function workstockEntry(mixed $entry): ?array {
		if (!is_array($entry) || !self::hasExactKeys($entry, self::WORKSTOCK_KEYS)) {
			return null;
		}
		$fileId = $entry['fileId'];
		$mediaId = $entry['mediaId'];
		$storageId = $entry['storageId'];
		$state = $entry['state'];
		$stage = $entry['stage'];
		$reason = $entry['reason'];
		if (!is_int($fileId) || $fileId <= 0
			|| ($mediaId !== null && (!is_int($mediaId) || $mediaId <= 0))
			|| !is_int($storageId) || $storageId < 0
			|| !is_string($state) || !in_array($state, self::WORK_STATES, true)
			|| !is_string($stage) || !in_array($stage, self::WORK_STAGES, true)
			|| ($reason !== null && (!is_string($reason) || preg_match(self::REASON_PATTERN, $reason) !== 1))) {
			return null;
		}

		return [
			'fileId' => $fileId,
			'mediaId' => $mediaId,
			'storageId' => $storageId,
			'state' => $state,
			'stage' => $stage,
			'reason' => $reason,
		];
	}

	/**
	 * The numbers of D-02-06 from the container (occ audio_video_search:status).
	 *
	 * Every key of COVERAGE_KEYS, a whole number of zero or more each, byState,
	 * byStage and byPreview with exactly the codes of the closed lists, and
	 * transcribed never above contents. Anything else is no answer.
	 *
	 * @return array{contents: int, transcribed: int, files: int, byState: array<string, int>, byStage: array<string, int>, dueWork: int, byPreview: array<string, int>}|null
	 */
	public function coverage(): ?array {
		$uid = $this->firstAdmin();
		if ($uid === null) {
			return null;
		}
		$answer = $this->call('/coverage', $uid, [], self::ADMIN_TIMEOUT_SECONDS, 'GET');
		if ($answer === null || !self::hasExactKeys($answer, self::COVERAGE_KEYS)) {
			return null;
		}

		foreach (['contents', 'transcribed', 'files', 'dueWork'] as $key) {
			if (!is_int($answer[$key]) || $answer[$key] < 0) {
				return null;
			}
		}
		$byState = self::countsOf($answer['byState'], self::WORK_STATES);
		$byStage = self::countsOf($answer['byStage'], self::WORK_STAGES);
		$byPreview = self::countsOf($answer['byPreview'], self::PREVIEW_NAMES);
		if ($byState === null || $byStage === null || $byPreview === null
			|| $answer['transcribed'] > $answer['contents']) {
			$this->logger->warning('Audio & Video Search: malformed coverage answer');
			return null;
		}

		return [
			'contents' => $answer['contents'],
			'transcribed' => $answer['transcribed'],
			'files' => $answer['files'],
			'byState' => $byState,
			'byStage' => $byStage,
			'dueWork' => $answer['dueWork'],
			'byPreview' => $byPreview,
		];
	}

	/**
	 * True when $array has exactly these keys, in any order.
	 *
	 * @param array<mixed> $array
	 * @param list<string> $keys
	 */
	private static function hasExactKeys(array $array, array $keys): bool {
		$found = array_map('strval', array_keys($array));
		sort($found);
		sort($keys);

		return $found === $keys;
	}

	/**
	 * A map of exactly the given codes to whole numbers of zero or more, in
	 * the order of the list.
	 *
	 * @param list<string> $codes
	 * @return array<string, int>|null
	 */
	private static function countsOf(mixed $map, array $codes): ?array {
		if (!is_array($map) || count($map) !== count($codes)) {
			return null;
		}
		$counts = [];
		foreach ($codes as $code) {
			if (!array_key_exists($code, $map) || !is_int($map[$code]) || $map[$code] < 0) {
				return null;
			}
			$counts[$code] = $map[$code];
		}

		return $counts;
	}

	/**
	 * One round of the reconcile of the container at once (occ
	 * audio_video_search:reconcile, plan 02-19). $reprove asks the container
	 * to renew the read proof of every grouped reference now (D-02-12).
	 *
	 * The answer is the closed set of counters of RECONCILE_KEYS: whole
	 * numbers of zero or more, and skippedReason null or a reason code. Any
	 * other shape is no answer.
	 *
	 * @return array{swept: int, vanished: int, orphaned: int, walkedMounts: int, requeued: int, rejected: int, reproofDue: int, skippedReason: ?string}|null
	 */
	public function reconcileNow(bool $reprove): ?array {
		$uid = $this->firstAdmin();
		if ($uid === null) {
			return null;
		}
		$answer = $this->call('/reconcile/run', $uid, ['reprove' => $reprove], self::RECONCILE_TIMEOUT_SECONDS);
		if ($answer === null || !self::hasExactKeys($answer, self::RECONCILE_KEYS)) {
			return null;
		}

		$counters = [];
		foreach (self::RECONCILE_KEYS as $key) {
			$value = $answer[$key];
			if ($key === 'skippedReason') {
				if ($value !== null && (!is_string($value) || preg_match(self::REASON_PATTERN, $value) !== 1)) {
					$this->logger->warning('Audio & Video Search: malformed reconcile answer');
					return null;
				}
			} elseif (!is_int($value) || $value < 0) {
				$this->logger->warning('Audio & Video Search: malformed reconcile answer');
				return null;
			}
			$counters[$key] = $value;
		}

		/** @var array{swept: int, vanished: int, orphaned: int, walkedMounts: int, requeued: int, rejected: int, reproofDue: int, skippedReason: ?string} $counters */
		return $counters;
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
	 * Whether the search may ask the container at all.
	 *
	 * A drift of major or minor on record answers nothing rather than
	 * something: neither half can say what the other one meant, so a hit would
	 * be a guess. Beyond that the last verdict of backendState decides, as long
	 * as it is at most sixty seconds old; an older or unreadable one is
	 * determined again under the first enabled admin, because the question
	 * whether the backend is there has the same answer for every user. An
	 * instance without any enabled admin keeps the search open: the call
	 * itself fails silently into an empty group when the backend is missing.
	 */
	public function searchAllowed(): bool {
		if ($this->driftOnRecord() !== null) {
			return false;
		}

		$state = $this->rememberedState();
		if ($state === null) {
			$admin = $this->firstAdmin();
			if ($admin === null) {
				$this->logger->info('Audio & Video Search: no enabled admin to check the backend state with');
				return true;
			}
			$state = $this->backendState($admin)['state'];
		}

		return in_array($state, self::SEARCHABLE_STATES, true);
	}

	// -- the state of the other half ------------------------------------------------

	/**
	 * The state of the other half, for the admin page and for the search.
	 *
	 * The order is the one of research pattern 1: AppAPI, registration,
	 * enabled flag, version of the registration, reachability, version the
	 * container reports. A drift is decided before the container is asked, so
	 * a container of the wrong version is never asked anything.
	 *
	 * The answer carries codes, versions, a closed word and a count, never a
	 * path, a file name or a sentence; it is remembered as such.
	 *
	 * @return array{state:string,own:string,backend:?string,companion:?string,sampleCount:?int,checkedAt:int}
	 */
	public function backendState(string $uid): array {
		$result = $this->determineState($uid);
		$this->rememberState($result);

		return $result;
	}

	/**
	 * What AppAPI knows about the backend: an array with appid, version, name
	 * and enabled, null when it is not registered, false when the public
	 * functions of AppAPI cannot be resolved.
	 *
	 * Protected for the same reason as proxyRequest: the AppAPI class is
	 * absent from the autoload space of the unit suite. The lookup reads the
	 * database of AppAPI and makes no network call.
	 *
	 * @return array<mixed>|false|null
	 */
	protected function exAppInfo(string $uid): array|false|null {
		$appApi = $this->publicFunctions($uid);
		if ($appApi === null) {
			return false;
		}

		$info = $appApi->getExApp(Application::BACKEND_APP_ID);

		return is_array($info) ? $info : null;
	}

	/** @return array{state:string,own:string,backend:?string,companion:?string,sampleCount:?int,checkedAt:int} */
	private function determineState(string $uid): array {
		$own = $this->ownVersion();
		$result = [
			'state' => self::STATE_NO_APP_API,
			'own' => $own,
			'backend' => null,
			'companion' => null,
			'sampleCount' => null,
			'checkedAt' => $this->timeFactory->getTime(),
		];

		if (!$this->appApiEnabledFor($uid)) {
			return $result;
		}

		try {
			$info = $this->exAppInfo($uid);
		} catch (\Throwable $e) {
			// Class name only: a library message is where a path shows up.
			$this->logger->warning('Audio & Video Search: the registration of the backend could not be read', [
				'class' => $e::class,
			]);
			$result['state'] = self::STATE_BACKEND_UNREACHABLE;

			return $result;
		}

		if ($info === false) {
			return $result;
		}
		if ($info === null) {
			$result['state'] = self::STATE_BACKEND_MISSING;

			return $result;
		}

		$registered = is_string($info['version'] ?? null) ? $this->versionOrNothing($info['version']) : '';
		if ($registered !== '') {
			$result['backend'] = $registered;
			$this->rememberBackendVersion($registered);
		}

		if (!self::isEnabledFlag($info['enabled'] ?? null)) {
			$result['state'] = self::STATE_BACKEND_DISABLED;

			return $result;
		}

		if ($this->drifts($own, $registered)) {
			$result['state'] = self::STATE_VERSION_DRIFT;

			return $result;
		}

		$status = $this->call('/status', $uid, [], self::REQUEST_TIMEOUT_SECONDS, 'GET');
		if ($status === null) {
			$result['state'] = self::STATE_BACKEND_UNREACHABLE;

			return $result;
		}

		// The version the running container reports wins over the registration.
		$reported = is_string($status['appVersion'] ?? null) ? $this->versionOrNothing($status['appVersion']) : '';
		if ($reported !== '') {
			$result['backend'] = $reported;
			$this->rememberBackendVersion($reported);
		}

		$companion = $status['companion'] ?? null;
		if (is_string($companion) && in_array($companion, self::COMPANION_VALUES, true)) {
			$result['companion'] = $companion;
		}

		$sampleCount = $status['sampleCount'] ?? null;
		if (is_int($sampleCount) && $sampleCount >= 0) {
			$result['sampleCount'] = $sampleCount;
		}

		$backend = $result['backend'] ?? '';
		if ($this->drifts($own, $backend)) {
			$result['state'] = self::STATE_VERSION_DRIFT;

			return $result;
		}

		// An unknown version on either side is a hint and never ok: the search
		// works, but nobody can say that the two halves match.
		$result['state'] = $own !== '' && $own === $backend
			? self::STATE_OK
			: self::STATE_VERSION_PATCH_DIFFERS;

		return $result;
	}

	/** True when both versions are known and differ in major or minor. */
	private function drifts(string $own, string $other): bool {
		return $own !== '' && $other !== '' && $this->majorMinor($own) !== $this->majorMinor($other);
	}

	/** The enabled flag of AppAPI: a boolean, or 0 and 1 out of the database. */
	private static function isEnabledFlag(mixed $flag): bool {
		return $flag === true || $flag === 1 || $flag === '1';
	}

	/** A real user with app_api enabled, without resolving AppAPI itself. */
	private function appApiEnabledFor(string $uid): bool {
		$user = $this->userManager->get($uid);

		return $user !== null && $this->appManager->isEnabledForUser('app_api', $user);
	}

	/** @param array{state:string,own:string,backend:?string,companion:?string,sampleCount:?int,checkedAt:int} $result */
	private function rememberState(array $result): void {
		$encoded = json_encode($result);
		if (is_string($encoded)) {
			$this->appConfig->setValueString(Application::APP_ID, self::KEY_BACKEND_STATE, $encoded);
		}
	}

	/** The remembered state code, or null when it is missing, malformed or too old. */
	private function rememberedState(): ?string {
		$raw = $this->appConfig->getValueString(Application::APP_ID, self::KEY_BACKEND_STATE, '');
		if ($raw === '') {
			return null;
		}

		$decoded = json_decode($raw, true);
		if (!is_array($decoded)) {
			return null;
		}

		$state = $decoded['state'] ?? null;
		$checkedAt = $decoded['checkedAt'] ?? null;
		if (!is_string($state) || !in_array($state, self::STATES, true) || !is_int($checkedAt)) {
			return null;
		}

		$age = $this->timeFactory->getTime() - $checkedAt;

		return $age >= 0 && $age <= self::STATE_MAX_AGE_SECONDS ? $state : null;
	}

	/** The uid of the first enabled member of the admin group, or null. */
	public function firstAdmin(): ?string {
		$group = $this->groupManager->get('admin');
		if ($group === null) {
			return null;
		}

		foreach ($group->getUsers() as $user) {
			if ($user->isEnabled()) {
				return $user->getUID();
			}
		}

		return null;
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
	private function call(string $route, string $userId, array $body, float $timeout, string $method = 'POST'): ?array {
		$startedAt = hrtime(true);
		$response = $this->proxyRequest($route, $userId, $method, $body, $timeout);
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
	 * What survives of a hit: file id, start time, excerpt, the sample flag and
	 * the stage, each with its type and range, and nothing else.
	 *
	 * The stage is a closed list. A missing or unknown stage becomes 'preview',
	 * a stage that is not a string drops the hit, and a sample is always the
	 * stage 'sample', whatever the container said.
	 *
	 * @param array<mixed> $hits
	 * @return list<array{fileId:int,startMs:int,excerpt:string,sample:bool,stage:string}>
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
			$stage = $hit['stage'] ?? null;
			if (!is_int($fileId) || $fileId <= 0
				|| !is_int($startMs) || $startMs < 0
				|| !is_string($excerpt) || !is_bool($sample)
				|| ($stage !== null && !is_string($stage))) {
				$dropped++;
				continue;
			}

			$text = self::plainText($excerpt, self::MAX_EXCERPT_LENGTH);
			if ($text === null) {
				$dropped++;
				continue;
			}

			if ($sample) {
				$stage = 'sample';
			} elseif (!in_array($stage, self::HIT_STAGES, true) || $stage === 'sample') {
				// 'sample' without the flag is a contradiction of the container;
				// it is no test result here, so it is the honest preview.
				$stage = 'preview';
			}

			$kept[] = ['fileId' => $fileId, 'startMs' => $startMs, 'excerpt' => $text, 'sample' => $sample, 'stage' => $stage];
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
