<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Controller;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Db\CrawlMapper;
use OCA\AudioVideoSearch\Db\QueueMapper;
use OCA\AudioVideoSearch\Db\StorageStateMapper;
use OCA\AudioVideoSearch\Service\QueueService;
use OCA\AudioVideoSearch\Service\StorageService;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\OCSController;
use OCP\Files\Cache\IFileAccess;
use OCP\Files\IMimeTypeLoader;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * The routes of the periodic reconcile of the container (plan 02-19, DISC-04,
 * after Findling's ReconcileController).
 *
 *   GET  /ocs/v2.php/apps/audio_video_search/reconcile/mounts
 *   GET  /ocs/v2.php/apps/audio_video_search/reconcile/mounts/{storageId}/slice?root=&after=&limit=
 *   POST /ocs/v2.php/apps/audio_video_search/reconcile/storages/classify  {"storageIds": [int]}
 *   POST /ocs/v2.php/apps/audio_video_search/reconcile/requeue            {"fileIds": [int]}
 *
 * The container compares what it holds with what these routes say and never
 * writes into the work stock itself: every file it finds new or changed goes
 * back through requeue, and requeue loads the cache entry, asks
 * QueueService::admissible (the one pre-check of event, crawl and reconcile,
 * D-02-05) and queues content only for an admissible file (T-02-69,
 * test_php_gates.py rule 16). It deletes at once only what classify confirms
 * as gone or deselected; a mount list that could not be read is ok false, so
 * a disturbed list never turns into deletions (T-02-70).
 *
 * Every route carries ExAppRequired and opens with the comparison against the
 * one backend app id (T-02-71). Answers carry ids, etags, numbers and flags,
 * never a path, a name, a host or a user (T-02-23). Bad input is a 400 whose
 * value never reaches the log.
 */
final class ReconcileController extends OCSController {
	/** How many storage or file ids one request may carry. */
	public const MAX_IDS = 256;

	/** Slice size when the container names none. */
	public const DEFAULT_SLICE = 500;

	public function __construct(
		IRequest $request,
		private StorageService $storageService,
		private QueueService $queueService,
		private CrawlMapper $crawlMapper,
		private StorageStateMapper $storageStates,
		private IFileAccess $fileAccess,
		private IMimeTypeLoader $mimeTypeLoader,
		private LoggerInterface $logger,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	/**
	 * Every mount of the mount set, once per (storage, walk root), with the
	 * flags the reconcile needs: is the first crawl of this mount finished
	 * (before that a missing file is no news), may its files be captured, is
	 * it external, and does it carry a share key (SMB, SFTP: the stored read
	 * proof is renewed, D-02-12).
	 *
	 * Anything that cannot be read makes the whole answer ok false with no
	 * mounts: half a list would read as missing mounts.
	 */
	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'GET', url: '/reconcile/mounts')]
	public function mounts(): DataResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		try {
			$mounts = [];
			foreach ($this->storageService->getMounts() as $mount) {
				$storageId = (int)$mount['storage_id'];
				$rootId = (int)$mount['overridden_root'];
				$crawl = $this->crawlMapper->find($storageId, $rootId);
				$external = $this->storageService->isExternal($storageId);
				$state = $external ? $this->storageStates->find($storageId) : null;
				$mounts[] = [
					'storageId' => $storageId,
					'rootId' => $rootId,
					'crawlFinished' => $crawl !== null && $crawl['finishedAt'] !== null,
					'capturable' => $this->queueService->storageCapturable($storageId),
					'external' => $external,
					'groupable' => $state !== null && $state['shareKeyHash'] !== null,
				];
			}
		} catch (\Throwable $e) {
			// The class only: a library message is where a path or a storage key turns up.
			$this->logger->error('Audio & Video Search: the mount list for the reconcile could not be read', ['class' => $e::class]);

			return new DataResponse(['ok' => false, 'mounts' => []]);
		}

		$this->logger->debug('Audio & Video Search: mount list handed to the reconcile', ['mounts' => count($mounts)]);

		return new DataResponse(['ok' => true, 'mounts' => $mounts]);
	}

	/**
	 * One slice of the media files below a walk root, file ids after $after in
	 * ascending order, at most $limit (1 to StorageService::MAX_SLICE). next is
	 * the last file id of a full slice and null for the last one. The root has
	 * to be a walk root of this storage in the mount set (404 otherwise), so no
	 * slice reaches into a trash bin or a versions folder.
	 */
	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'GET', url: '/reconcile/mounts/{storageId}/slice')]
	public function slice(mixed $storageId = null, mixed $root = null, mixed $after = null, mixed $limit = null): DataResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		$storage = self::positiveInt($storageId);
		$rootId = self::positiveInt($root);
		$cursor = $after === null ? 0 : self::wholeNumber($after);
		$size = $limit === null ? self::DEFAULT_SLICE : self::positiveInt($limit);
		if ($storage === null || $rootId === null || $cursor === null || $size === null || $size > StorageService::MAX_SLICE) {
			return $this->badInput();
		}

		try {
			$roots = array_column($this->storageService->mountRoots($storage), 'rootId');
			if (!in_array($rootId, $roots, true)) {
				return new DataResponse(['error' => 'Unknown mount.'], Http::STATUS_NOT_FOUND);
			}

			$files = [];
			foreach ($this->storageService->getFileSlice($storage, $rootId, $cursor, $size) as $entry) {
				$files[] = [
					'fileId' => (int)$entry->getId(),
					'etag' => (string)$entry->getEtag(),
					'size' => (int)$entry->getSize(),
					'mtime' => (int)$entry->getStorageMTime(),
				];
			}
		} catch (\Throwable $e) {
			$this->logger->error('Audio & Video Search: a slice for the reconcile could not be read', ['class' => $e::class, 'storage_id' => $storage]);

			return new DataResponse(['error' => 'File list is not available.'], Http::STATUS_INTERNAL_SERVER_ERROR);
		}

		$next = count($files) === $size && $files !== [] ? $files[count($files) - 1]['fileId'] : null;

		return new DataResponse(['files' => $files, 'next' => $next]);
	}

	/**
	 * gone, deselected and present for storages the container no longer finds
	 * in the mount list (StorageService::classifyAbsent). Capturable is the
	 * answer of QueueService, the same the pre-check uses.
	 */
	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'POST', url: '/reconcile/storages/classify')]
	public function classify(mixed $storageIds = null): DataResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		$ids = self::idList($storageIds);
		if ($ids === null) {
			return $this->badInput();
		}

		try {
			$answer = $this->storageService->classifyAbsent(
				$ids,
				fn (int $storageId): bool => $this->queueService->storageCapturable($storageId),
			);
		} catch (\Throwable $e) {
			$this->logger->error('Audio & Video Search: absent storages could not be classified', ['class' => $e::class]);

			return new DataResponse(['error' => 'Classification is not available.'], Http::STATUS_INTERNAL_SERVER_ERROR);
		}

		return new DataResponse([
			'gone' => $answer['gone'],
			'deselected' => $answer['deselected'],
			'present' => $answer['present'],
		]);
	}

	/**
	 * Files the reconcile found new or changed, handed back to the one
	 * pre-check. Each file id is looked up in the file cache; storage, media
	 * type and path below the walk root come from that entry and never from
	 * the caller. Admissible: queued as content. Unknown, outside every walk
	 * root (trash bin), another type or excluded: rejected, nothing queued.
	 * A work stock that cannot be written is a 500, so the container asks
	 * again in its next round.
	 */
	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'POST', url: '/reconcile/requeue')]
	public function requeue(mixed $fileIds = null): DataResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		$ids = self::idList($fileIds);
		if ($ids === null) {
			return $this->badInput();
		}

		$enqueued = 0;
		$rejected = 0;
		try {
			foreach ($ids as $fileId) {
				$facts = $this->cacheFacts($fileId);
				if ($facts === null) {
					$rejected++;
					continue;
				}
				[$storageId, $mimeId, $relative] = $facts;
				if (!$this->queueService->admissible($storageId, $mimeId, $relative)) {
					$rejected++;
					continue;
				}
				$this->queueService->enqueue(QueueMapper::KIND_CONTENT, $fileId, $storageId);
				$enqueued++;
			}
		} catch (\Throwable $e) {
			$this->logger->error('Audio & Video Search: files of the reconcile could not be queued', ['class' => $e::class, 'enqueued' => $enqueued]);

			return new DataResponse(['error' => 'Work stock is not available.'], Http::STATUS_INTERNAL_SERVER_ERROR);
		}

		$this->logger->debug('Audio & Video Search: reconcile handed files back', ['enqueued' => $enqueued, 'rejected' => $rejected]);

		return new DataResponse(['enqueued' => $enqueued, 'rejected' => $rejected]);
	}

	/**
	 * The arguments of QueueService::admissible for one file id, read from its
	 * cache entry: storage id, media type id, path below the walk root. null
	 * for a file that is gone, lies outside every walk root, or cannot be
	 * looked up.
	 *
	 * @return array{0: int, 1: int, 2: string}|null
	 */
	private function cacheFacts(int $fileId): ?array {
		try {
			$entry = $this->fileAccess->getByFileId($fileId);
			if ($entry === null) {
				return null;
			}
			$storageId = (int)$entry->getStorageId();
			$mime = (string)$entry->getMimeType();
			$mimeId = $mime !== '' && $this->mimeTypeLoader->exists($mime) ? $this->mimeTypeLoader->getId($mime) : 0;
			$relative = $this->storageService->mountRelativePath($storageId, (string)$entry->getPath());
		} catch (\Throwable $e) {
			$this->logger->debug('Audio & Video Search: a file of the reconcile could not be looked up', ['class' => $e::class]);

			return null;
		}

		return $relative === null ? null : [$storageId, $mimeId, $relative];
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

		$this->logger->warning('Audio & Video Search: reconcile route called by a foreign ExApp', ['app' => $callerAppId]);

		return new DataResponse(
			['error' => 'This route is reserved for the Audio & Video Search backend.'],
			Http::STATUS_FORBIDDEN,
		);
	}

	/**
	 * A non empty list of at most MAX_IDS positive ids, each once, or null.
	 *
	 * @return list<int>|null
	 */
	private static function idList(mixed $raw): ?array {
		if (!is_array($raw) || $raw === [] || !array_is_list($raw) || count($raw) > self::MAX_IDS) {
			return null;
		}

		$ids = [];
		foreach ($raw as $value) {
			$id = self::positiveInt($value);
			if ($id === null) {
				return null;
			}
			$ids[$id] = true;
		}

		return array_keys($ids);
	}

	/** A positive whole number from a JSON body (int) or a path or query (canonical digits). */
	private static function positiveInt(mixed $value): ?int {
		$number = self::wholeNumber($value);

		return $number !== null && $number > 0 ? $number : null;
	}

	/** A whole number of zero or more, same forms as positiveInt. */
	private static function wholeNumber(mixed $value): ?int {
		if (is_int($value)) {
			return $value >= 0 ? $value : null;
		}
		if (is_string($value) && ctype_digit($value)) {
			$number = (int)$value;

			return (string)$number === $value ? $number : null;
		}

		return null;
	}

	private function badInput(): DataResponse {
		$this->logger->warning('Audio & Video Search: rejected a reconcile request with invalid input');

		return new DataResponse(['error' => 'Invalid input.'], Http::STATUS_BAD_REQUEST);
	}
}
