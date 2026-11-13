<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Controller;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Search\Provider;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\FileAccess;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\Files\File;
use OCP\Files\Folder;
use OCP\Files\IRootFolder;
use OCP\Files\Storage\ISharedStorage;
use OCP\IAppConfig;
use OCP\IL10N;
use OCP\IRequest;
use OCP\IURLGenerator;
use OCP\IUserSession;
use Psr\Log\LoggerInterface;

/**
 * The playback page: one file, one point in time, one excerpt.
 *
 * The page plays nothing itself. The medium points at the WebDAV address of
 * the file, so range requests, the view only rules of shares and encrypted
 * storages are handled by the server exactly as for the viewer, and this app
 * has no stream route of its own.
 *
 * The file id in the address is untrusted. It is resolved in the folder of the
 * signed in user through FileAccess::readableFile, so a file that is missing,
 * foreign, in the trash or closed by a Team Folder ACL gives the same answer:
 * a 404 page without a name and without a path. The path of a confirmed file
 * is used once, encoded segment by segment into the WebDAV address, and never
 * logged.
 *
 * The start time in ?t= survives a login redirect, which a fragment does not.
 * It is read as seconds with at most three decimals, between 0 and one day;
 * anything else is 0 and no message. The page writes nothing.
 *
 * An excluded user and an excluded file get no excerpt (owner 13.11.2026,
 * plan 02-16b): the page shows the state of a file without a transcript and
 * the container is not asked. The question goes to ExclusionService like the
 * ones of the search provider and the content gateway (gate rule 14), and a
 * question that fails counts as excluded. The medium itself still plays:
 * that is WebDAV and the rights of the user, not the transcript.
 */
final class PageController extends Controller {
	/** One day, the ceiling of the start time in seconds. */
	public const MAX_START_SECONDS = 86400;

	private const START_PATTERN = '/^\d{1,5}(?:\.\d{1,3})?$/D';

	public const STATE_READY = 'ready';
	public const STATE_NOT_MEDIA = 'not_media';
	public const STATE_DOWNLOAD_BLOCKED = 'download_blocked';
	public const STATE_UNAVAILABLE = 'unavailable';

	public const EXCERPT_OK = 'ok';
	public const EXCERPT_NONE = 'none';
	public const EXCERPT_UNAVAILABLE = 'unavailable';
	/** No excerpt was asked for, because nothing is played. */
	public const EXCERPT_SKIPPED = 'skipped';

	public function __construct(
		IRequest $request,
		private IRootFolder $rootFolder,
		private IUserSession $userSession,
		private IURLGenerator $urlGenerator,
		private IAppConfig $appConfig,
		private IL10N $l10n,
		private ExAppService $exAppService,
		private ReaderContext $readerContext,
		private LoggerInterface $logger,
		private ExclusionService $exclusions,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	/**
	 * GET /apps/audio_video_search/play/{fileId}?t=42.0
	 *
	 * A signed in session is required and nothing else: ordinary users open
	 * this page, and a link from the search carries no request token. The
	 * route reads and changes nothing.
	 */
	#[\OCP\AppFramework\Http\Attribute\NoAdminRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'GET', url: '/play/{fileId}', requirements: ['fileId' => '\d+'])]
	public function play(int $fileId): TemplateResponse {
		$startMs = self::startMs($this->request->getParam('t', ''));
		$found = $this->resolve($fileId);
		if ($found === null) {
			return $this->unavailable($fileId, $startMs);
		}

		[$userFolder, $file, $uid] = $found;
		$mediaTag = self::mediaTag((string)$file->getMimetype());
		$downloadAllowed = $this->downloadAllowed($file, $fileId);

		$state = self::STATE_READY;
		if ($mediaTag === '') {
			$state = self::STATE_NOT_MEDIA;
		} elseif (!$downloadAllowed && !$this->viewWithoutDownload()) {
			$state = self::STATE_DOWNLOAD_BLOCKED;
		}

		$src = '';
		$mediaSrc = '';
		$excerptState = self::EXCERPT_SKIPPED;
		$excerpt = '';
		if ($state === self::STATE_READY) {
			$src = $this->davUrl($uid, $userFolder, $file);
			$mediaSrc = $startMs > 0 ? $src . '#t=' . self::seconds($startMs) : $src;
			[$excerptState, $excerpt] = $this->excerpt($uid, $fileId, $startMs);
		}

		$fileName = (string)$file->getName();

		return $this->render([
			'state' => $state,
			'fileName' => $fileName,
			'pageTitle' => $fileName,
			'mediaTag' => $mediaTag,
			'src' => $src,
			'mediaSrc' => $mediaSrc,
			'excerptState' => $excerptState,
			'excerpt' => $excerpt,
			'filesUrl' => $this->urlGenerator->linkToRoute('files.view.showFile', ['fileid' => $fileId]),
			'downloadAllowed' => $downloadAllowed,
		], $startMs);
	}

	/**
	 * Milliseconds from the raw ?t= value, or 0 for anything that is not a
	 * plain number of seconds between 0 and one day. Computed on the digits,
	 * so no float rounding moves the mark.
	 */
	public static function startMs(mixed $raw): int {
		if (!is_string($raw) || preg_match(self::START_PATTERN, $raw) !== 1) {
			return 0;
		}

		$parts = explode('.', $raw, 2);
		$milliseconds = (int)$parts[0] * 1000;
		if (isset($parts[1])) {
			$milliseconds += (int)str_pad($parts[1], 3, '0');
		}

		return $milliseconds > self::MAX_START_SECONDS * 1000 ? 0 : $milliseconds;
	}

	/** Seconds with one decimal, cut and never rounded up (as in the search link). */
	public static function seconds(int $milliseconds): string {
		$tenths = intdiv(max(0, $milliseconds), 100);

		return intdiv($tenths, 10) . '.' . ($tenths % 10);
	}

	/** An ISO 8601 duration for the datetime attribute of the time element. */
	public static function isoDuration(int $milliseconds): string {
		$seconds = intdiv(max(0, $milliseconds), 1000);
		$hours = intdiv($seconds, 3600);
		$minutes = intdiv($seconds % 3600, 60);

		return 'PT'
			. ($hours > 0 ? $hours . 'H' : '')
			. ($minutes > 0 ? $minutes . 'M' : '')
			. ($seconds % 60) . 'S';
	}

	private static function mediaTag(string $mime): string {
		if (str_starts_with($mime, 'video/')) {
			return 'video';
		}

		return str_starts_with($mime, 'audio/') ? 'audio' : '';
	}

	/**
	 * The user folder, the confirmed file and the uid, or null. The lookup runs
	 * as the signed in user through ReaderContext, like every other lookup of
	 * this app, so the Team Folder ACL answers as in the Files app.
	 *
	 * @return array{Folder, File, string}|null
	 */
	private function resolve(int $fileId): ?array {
		$uid = $this->userSession->getUser()?->getUID();
		if (!is_string($uid) || $uid === '') {
			return null;
		}

		try {
			return $this->readerContext->actAs($uid, function () use ($uid, $fileId): ?array {
				$userFolder = $this->rootFolder->getUserFolder($uid);
				$file = FileAccess::readableFile($userFolder, $fileId);

				return $file === null ? null : [$userFolder, $file, $uid];
			});
		} catch (\Throwable $e) {
			// Class name only: a library message is where a path shows up.
			$this->logger->warning('Audio & Video Search: a file for the playback page could not be resolved', [
				'fileId' => $fileId,
				'class' => $e::class,
			]);

			return null;
		}
	}

	/**
	 * False when the file sits in a received share whose download switch is
	 * off. Mirrors the server: Share::canDownload and the ViewOnlyPlugin of
	 * WebDAV read the same attribute. When this cannot be decided, the page
	 * plays and play.js maps a 403 of WebDAV to the same notice.
	 */
	private function downloadAllowed(File $file, int $fileId): bool {
		try {
			$storage = $file->getStorage();
			if (!$storage->instanceOfStorage(ISharedStorage::class)) {
				return true;
			}

			/** @var ISharedStorage $storage */
			return $storage->getShare()->getAttributes()?->getAttribute('permissions', 'download') !== false;
		} catch (\Throwable $e) {
			$this->logger->info('Audio & Video Search: the share rules of a file could not be read', [
				'fileId' => $fileId,
				'class' => $e::class,
			]);

			return true;
		}
	}

	/** The admin switch the server reads in Share20\Manager, same default. */
	private function viewWithoutDownload(): bool {
		return $this->appConfig->getValueBool('core', 'shareapi_allow_view_without_download', true);
	}

	/**
	 * The WebDAV address of the file as the signed in user sees it. The path
	 * comes out of the node and nowhere else; the uid and every segment are
	 * percent encoded, so a space, an @ or a # in a name cannot change the
	 * address.
	 */
	private function davUrl(string $uid, Folder $userFolder, File $file): string {
		$segments = array_map('rawurlencode', explode('/', FileAccess::relativePath($userFolder, $file)));

		return $this->urlGenerator->getWebroot() . '/remote.php/dav/files/'
			. rawurlencode($uid) . '/' . implode('/', $segments);
	}

	/**
	 * The excerpt state and text. A drift on record or a silent container is
	 * "cannot be loaded right now", an unknown file is "no transcript yet".
	 *
	 * An excluded user, by name or through a group, and an excluded file are
	 * answered first, before anything that could reach the container, and
	 * with the answer of a file without a transcript: the same state and the
	 * same empty text, whatever the container would have said and whether it
	 * can be reached or not. Every doubt excludes: ExclusionService answers
	 * yes for rules it cannot read, and a question that throws is a yes here.
	 * The log line names neither the user nor the file.
	 *
	 * @return array{string, string}
	 */
	private function excerpt(string $uid, int $fileId, int $startMs): array {
		try {
			$excluded = $this->exclusions->isExcludedUser($uid) || $this->exclusions->isExcludedFile($fileId);
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the exclusions could not be asked for the playback page, no excerpt is shown', [
				'class' => $e::class,
			]);
			$excluded = true;
		}
		if ($excluded) {
			return [self::EXCERPT_NONE, ''];
		}

		if (!$this->exAppService->searchAllowed()) {
			return [self::EXCERPT_UNAVAILABLE, ''];
		}

		$answer = $this->exAppService->excerpt($uid, $fileId, $startMs);
		if ($answer === null) {
			return [self::EXCERPT_UNAVAILABLE, ''];
		}

		$text = trim((string)($answer['excerpt'] ?? ''));
		if (!$answer['known'] || $text === '') {
			return [self::EXCERPT_NONE, ''];
		}

		return [self::EXCERPT_OK, $text];
	}

	private function unavailable(int $fileId, int $startMs): TemplateResponse {
		$this->logger->debug('Audio & Video Search: playback page for a file that is not readable', ['fileId' => $fileId]);

		$response = $this->render([
			'state' => self::STATE_UNAVAILABLE,
			'fileName' => '',
			'pageTitle' => $this->l10n->t('Playback'),
			'mediaTag' => '',
			'src' => '',
			'mediaSrc' => '',
			'excerptState' => self::EXCERPT_SKIPPED,
			'excerpt' => '',
			'filesUrl' => $this->urlGenerator->linkToRoute('files.view.index'),
			'downloadAllowed' => false,
		], $startMs);
		$response->setStatus(Http::STATUS_NOT_FOUND);

		return $response;
	}

	/** @param array<string, mixed> $params */
	private function render(array $params, int $startMs): TemplateResponse {
		$params += [
			'startMs' => $startMs,
			'startSeconds' => self::seconds($startMs),
			'startClock' => Provider::clock($startMs),
			'startIso' => self::isoDuration($startMs),
			// The page has no app navigation; the skip link of the layout
			// must not point at one.
			'id-app-navigation' => null,
		];

		return new TemplateResponse(Application::APP_ID, 'play', $params, TemplateResponse::RENDER_AS_USER);
	}
}
