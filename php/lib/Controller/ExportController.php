<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Controller;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Search\Provider;
use OCA\AudioVideoSearch\Service\DownloadPolicy;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ExclusionService;
use OCA\AudioVideoSearch\Service\FileAccess;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCA\AudioVideoSearch\Service\SidecarWriter;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataDisplayResponse;
use OCP\AppFramework\Http\DataDownloadResponse;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\Files\File;
use OCP\Files\IRootFolder;
use OCP\IL10N;
use OCP\IRequest;
use OCP\IURLGenerator;
use OCP\IUserSession;
use Psr\Log\LoggerInterface;

/**
 * The export of the subtitle draft: three downloads, the track of the
 * player and the sidecar next to the medium, all only over the routes of
 * this app (D-04-01, EXP-03).
 *
 * The order of the checks is the contract of this controller, in all three
 * methods, and gate rule 19 of backend/tests/test_php_gates.py holds it:
 *
 * 1. resolve: the file id is untrusted and is confirmed as the signed in
 *    user through FileAccess::readableFile (gate rule 4). A missing, foreign
 *    or closed file is the same 404 page without a name and without a path.
 * 2. The download policy, BEFORE the exclusions and before anything that
 *    could reach the container: X3 hangs on the share attribute only
 *    (UI-SPEC leak rule), so the 403 of a blocked share is byte for byte
 *    the same whether the file is excluded or not, and the block is no
 *    oracle about exclusions or transcripts (T-04-29, T-04-29a). The export
 *    fails closed: an attribute nobody can read blocks it (T-04-30).
 * 3. The exclusions, by the rules of now (gate rule 14), before the
 *    container; a question that fails excludes.
 * 4. searchAllowed and the container. known false, excluded and unreadable
 *    all end in pages that cannot be told apart beyond what the user may
 *    know anyway.
 *
 * Errors of the download are a small page in the app frame, never JSON
 * (UI-SPEC D2, O9); errors of the track are empty answers with the status,
 * because the track element of the player shows no page.
 */
final class ExportController extends Controller {
	/** The cases of the error page, the closed list export_error.php knows. */
	public const CASE_UNAVAILABLE = 'unavailable';
	public const CASE_BLOCKED = 'blocked';
	public const CASE_NONE = 'none';
	public const CASE_UNREACHABLE = 'unreachable';

	/** The media type of each format (research: subtitles over HTTP). */
	public const MIME_TYPES = [
		'srt' => 'application/x-subrip; charset=utf-8',
		'vtt' => 'text/vtt; charset=utf-8',
		'txt' => 'text/plain; charset=utf-8',
	];

	public function __construct(
		IRequest $request,
		private IRootFolder $rootFolder,
		private IUserSession $userSession,
		private IURLGenerator $urlGenerator,
		private IL10N $l10n,
		private ExAppService $exAppService,
		private ReaderContext $readerContext,
		private LoggerInterface $logger,
		private ExclusionService $exclusions,
		private DownloadPolicy $downloadPolicy,
		private SidecarWriter $sidecarWriter,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	/**
	 * GET /apps/audio_video_search/export/{fileId}/{format}?t=42.0
	 *
	 * The subtitle draft as a download: SRT and VTT with time marks, TXT as
	 * plain text with a header (D-04-03), named <name>.<de|en|fr>.<format>
	 * (D-04-04). A signed in session and nothing else, like the playback
	 * page: the route reads and changes nothing, and the link of the page
	 * carries no request token. ?t= only feeds the way back of the error
	 * page.
	 */
	#[\OCP\AppFramework\Http\Attribute\NoAdminRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\UserRateLimit(limit: 30, period: 60)]
	#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'GET', url: '/export/{fileId}/{format}', requirements: ['fileId' => '\d+', 'format' => 'srt|vtt|txt'])]
	public function download(int $fileId, string $format): TemplateResponse|DataDownloadResponse {
		$startMs = PageController::startMs($this->request->getParam('t', ''));
		$found = $this->resolve($fileId);
		if ($found === null) {
			return $this->errorPage(self::CASE_UNAVAILABLE, Http::STATUS_NOT_FOUND, $fileId, $startMs);
		}
		[$file, $uid] = $found;

		// The block first, fail closed: see the class comment and gate rule 19.
		if (!$this->downloadPolicy->allowsExport($file, $fileId)) {
			return $this->errorPage(self::CASE_BLOCKED, Http::STATUS_FORBIDDEN, $fileId, $startMs);
		}

		try {
			// The rules of now, as on the playback page (owner 14.11.2026).
			$this->exclusions->reload();
			$excluded = $this->exclusions->isExcludedUser($uid) || $this->exclusions->isExcludedFile($fileId);
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the exclusions could not be asked for the export, none is given', [
				'class' => $e::class,
			]);
			$excluded = true;
		}
		if ($excluded) {
			return $this->errorPage(self::CASE_NONE, Http::STATUS_NOT_FOUND, $fileId, $startMs);
		}

		if (!$this->exAppService->searchAllowed()) {
			return $this->errorPage(self::CASE_UNREACHABLE, Http::STATUS_SERVICE_UNAVAILABLE, $fileId, $startMs);
		}
		$answer = $this->exAppService->export($uid, $fileId, $format);
		if ($answer === null) {
			return $this->errorPage(self::CASE_UNREACHABLE, Http::STATUS_SERVICE_UNAVAILABLE, $fileId, $startMs);
		}
		if ($answer['known'] !== true) {
			// Byte for byte the page of an excluded file: not active and
			// unknown may not be told apart (X4 leak rule).
			return $this->errorPage(self::CASE_NONE, Http::STATUS_NOT_FOUND, $fileId, $startMs);
		}

		$fileName = (string)$file->getName();

		return new DataDownloadResponse(
			$this->payload($format, $answer, $fileName, $fileId),
			self::attachmentName(self::downloadName($fileName, $answer['language'], $format)),
			self::MIME_TYPES[$format],
		);
	}

	/**
	 * GET /apps/audio_video_search/track/{fileId}
	 *
	 * The same VTT as the download, for the track element of the player
	 * (D-04-18): text/vtt without a Content-Disposition, same checks in the
	 * same order. Errors are empty answers with the status, never a page:
	 * nobody sees them but the player, which silently keeps playing.
	 */
	#[\OCP\AppFramework\Http\Attribute\NoAdminRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\UserRateLimit(limit: 30, period: 60)]
	#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'GET', url: '/track/{fileId}', requirements: ['fileId' => '\d+'])]
	public function track(int $fileId): DataDisplayResponse {
		$found = $this->resolve($fileId);
		if ($found === null) {
			return $this->emptyAnswer(Http::STATUS_NOT_FOUND);
		}
		[$file, $uid] = $found;

		// The block first, fail closed: see the class comment and gate rule 19.
		if (!$this->downloadPolicy->allowsExport($file, $fileId)) {
			return $this->emptyAnswer(Http::STATUS_FORBIDDEN);
		}

		try {
			// The rules of now, as on the playback page (owner 14.11.2026).
			$this->exclusions->reload();
			$excluded = $this->exclusions->isExcludedUser($uid) || $this->exclusions->isExcludedFile($fileId);
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the exclusions could not be asked for the track, none is given', [
				'class' => $e::class,
			]);
			$excluded = true;
		}
		if ($excluded) {
			return $this->emptyAnswer(Http::STATUS_NOT_FOUND);
		}

		if (!$this->exAppService->searchAllowed()) {
			return $this->emptyAnswer(Http::STATUS_SERVICE_UNAVAILABLE);
		}
		$answer = $this->exAppService->export($uid, $fileId, 'vtt');
		if ($answer === null) {
			return $this->emptyAnswer(Http::STATUS_SERVICE_UNAVAILABLE);
		}
		if ($answer['known'] !== true) {
			return $this->emptyAnswer(Http::STATUS_NOT_FOUND);
		}

		$vtt = self::withNote(
			$answer['body'],
			$this->noteSafe($this->headerLines($answer['partial'], $answer['untilMs']), $fileId),
		);
		$response = new DataDisplayResponse($vtt, Http::STATUS_OK, ['Content-Type' => self::MIME_TYPES['vtt']]);
		// The constructor forces an inline disposition; the track carries
		// none at all, it is no download and no attachment (D-04-18).
		$response->addHeader('Content-Disposition', null);

		return $response;
	}

	/**
	 * POST /apps/audio_video_search/sidecar/{fileId}
	 *
	 * The same VTT as the download, laid next to the medium as
	 * <name>.<de|en|fr>.vtt (EXP-03, D-04-06, D-04-07). The route changes the
	 * folder of the user, so unlike the two GET routes it keeps the CSRF
	 * check (no NoCSRFRequired; gate rule 20 holds that) and carries a
	 * tighter rate limit. Same check order as the downloads, then two more
	 * questions in the view of the user: isCreatable of the parent, before
	 * the container is asked, and the write itself through SidecarWriter,
	 * which never touches an existing file (D-04-05). The file is written
	 * once and never refreshed; there is no comparison against the medium
	 * and no staleness notice (D-04-08).
	 *
	 * The answers are the closed list play.js knows (UI-SPEC E1 to E7): 201
	 * and 409 carry the checked name, the two 403 reasons are 'blocked' and
	 * 'not_writable', 400 is 'name_too_long', 404 and 503 carry nothing. A
	 * collision reports and writes nothing; BUSY is the same collision told
	 * a moment earlier.
	 */
	#[\OCP\AppFramework\Http\Attribute\NoAdminRequired]
	#[\OCP\AppFramework\Http\Attribute\UserRateLimit(limit: 10, period: 60)]
	#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'POST', url: '/sidecar/{fileId}', requirements: ['fileId' => '\d+'])]
	public function sidecar(int $fileId): DataResponse {
		$found = $this->resolve($fileId);
		if ($found === null) {
			return new DataResponse([], Http::STATUS_NOT_FOUND);
		}
		[$file, $uid] = $found;

		// The block first, fail closed: see the class comment and gate rule 19.
		if (!$this->downloadPolicy->allowsExport($file, $fileId)) {
			return new DataResponse(['reason' => 'blocked'], Http::STATUS_FORBIDDEN);
		}

		try {
			// The rules of now, as on the playback page (owner 14.11.2026).
			$this->exclusions->reload();
			$excluded = $this->exclusions->isExcludedUser($uid) || $this->exclusions->isExcludedFile($fileId);
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the exclusions could not be asked for the sidecar, none is given', [
				'class' => $e::class,
			]);
			$excluded = true;
		}
		if ($excluded) {
			return new DataResponse([], Http::STATUS_NOT_FOUND);
		}

		// Whether the folder takes a new file, decided as the user: quota,
		// the Team Folder ACL and files_accesscontrol answer only in that
		// view. A question that fails is a no (fail closed), and the
		// container is never asked for a folder nobody may write to.
		try {
			$creatable = $this->readerContext->actAs($uid, static fn (): bool => $file->getParent()->isCreatable());
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the folder of the medium could not be asked, no sidecar', [
				'fileId' => $fileId,
				'class' => $e::class,
			]);
			$creatable = false;
		}
		if (!$creatable) {
			return new DataResponse(['reason' => 'not_writable'], Http::STATUS_FORBIDDEN);
		}

		if (!$this->exAppService->searchAllowed()) {
			return new DataResponse([], Http::STATUS_SERVICE_UNAVAILABLE);
		}
		$answer = $this->exAppService->export($uid, $fileId, 'vtt');
		if ($answer === null) {
			return new DataResponse([], Http::STATUS_SERVICE_UNAVAILABLE);
		}
		if ($answer['known'] !== true) {
			// Byte for byte the answer of an unreadable file: not active and
			// unknown may not be told apart (X4 leak rule).
			return new DataResponse([], Http::STATUS_NOT_FOUND);
		}

		$name = self::downloadName((string)$file->getName(), $answer['language'], 'vtt');
		if (strlen($name) > SidecarWriter::MAX_NAME_BYTES) {
			return new DataResponse(['reason' => 'name_too_long'], Http::STATUS_BAD_REQUEST);
		}

		$content = self::withNote(
			(string)$answer['body'],
			$this->noteSafe($this->headerLines((bool)$answer['partial'], (int)$answer['untilMs']), $fileId),
		);

		try {
			$result = $this->readerContext->actAs(
				$uid,
				fn (): string => $this->sidecarWriter->write($file->getParent(), $name, $content),
			);
		} catch (\Throwable $e) {
			// Past the closed answers of the writer: a parent that vanished,
			// a storage error, or a medium whose name is legal in Nextcloud
			// but no plain sidecar name (a backslash). The catch-all answer
			// of the page (E7), the class only in the log.
			$this->logger->warning('Audio & Video Search: the sidecar could not be written', [
				'fileId' => $fileId,
				'class' => $e::class,
			]);

			return new DataResponse([], Http::STATUS_SERVICE_UNAVAILABLE);
		}

		return match ($result) {
			SidecarWriter::CREATED => new DataResponse(['name' => $name], Http::STATUS_CREATED),
			// A name that is taken and a creation that lost the race by a
			// moment are the same truth: the file next to the medium is not
			// this draft, and nothing was written (D-04-05).
			SidecarWriter::EXISTS, SidecarWriter::BUSY => new DataResponse(['name' => $name], Http::STATUS_CONFLICT),
			default => new DataResponse(['reason' => 'not_writable'], Http::STATUS_FORBIDDEN),
		};
	}

	/**
	 * The name of the download (D-04-04): the file name in NFC, the last
	 * extension cut (a name without a dot, or with only a leading one, stays
	 * whole), then the language and the format. "sitzung.mp4" becomes
	 * "sitzung.de.srt", "Übung.final.webm" becomes "Übung.final.fr.vtt".
	 * DataDownloadResponse does the header work: slashes replaced, an ASCII
	 * fallback next to the UTF-8 name (T-04-32).
	 */
	public static function downloadName(string $fileName, string $language, string $format): string {
		$name = self::composed($fileName);
		$dot = strrpos($name, '.');
		$base = $dot === false || $dot === 0 ? $name : substr($name, 0, $dot);

		return $base . '.' . $language . '.' . $format;
	}

	/**
	 * The download name as the Content-Disposition header can carry it:
	 * control characters become spaces, as in the TXT head. The ASCII
	 * fallback of DownloadResponse keeps them, and Symfony refuses such a
	 * fallback with an exception, so a medium with a tab in its name would
	 * end in a server error instead of the download. Only the header name
	 * changes; the sidecar keeps downloadName() so it stays next to its
	 * medium under the pattern of D-04-04.
	 */
	public static function attachmentName(string $name): string {
		$safe = preg_replace('/[\x00-\x1F\x7F]/u', ' ', $name);

		return is_string($safe) ? $safe : (string)preg_replace('/[\x00-\x1F\x7F]/', ' ', $name);
	}

	/**
	 * The VTT with the draft notice as a NOTE block after the header
	 * (D-04-03, EXP-04): the header of the container is replaced by
	 * "WEBVTT", the note lines follow, then its cues. Without a line the
	 * note block is left out. SRT has no comment mechanism and stays as it
	 * came (D-04-16).
	 *
	 * @param list<string> $lines
	 */
	public static function withNote(string $vtt, array $lines): string {
		$separator = strpos($vtt, "\n\n");
		$rest = str_starts_with($vtt, 'WEBVTT')
			? ($separator === false ? '' : substr($vtt, $separator + 2))
			: $vtt;
		if ($lines === []) {
			return "WEBVTT\n\n" . $rest;
		}

		return "WEBVTT\n\nNOTE\n" . implode("\n", $lines) . "\n\n" . $rest;
	}

	/**
	 * The TXT with its header (D-04-03): the file name with control
	 * characters replaced by spaces, the note lines, a blank line, then the
	 * text of the container.
	 *
	 * @param list<string> $lines
	 */
	public static function withHeader(string $txt, string $fileName, array $lines): string {
		$name = preg_replace('/[\x00-\x1F\x7F]/u', ' ', $fileName);
		$head = array_merge([is_string($name) ? $name : ''], $lines);

		return implode("\n", $head) . "\n\n" . $txt;
	}

	/**
	 * The body of one format: SRT untouched, VTT with the note, TXT with the header.
	 *
	 * @param array{known:true,partial:bool,untilMs:int,language:string,body:string} $answer
	 */
	private function payload(string $format, array $answer, string $fileName, int $fileId): string {
		$body = (string)$answer['body'];
		if ($format === 'srt') {
			return $body;
		}

		$lines = $this->headerLines((bool)$answer['partial'], (int)$answer['untilMs']);
		if ($format === 'vtt') {
			return self::withNote($body, $this->noteSafe($lines, $fileId));
		}

		return self::withHeader($body, $fileName, $lines);
	}

	/**
	 * The draft notice and, for a partial transcript, the line that names up
	 * to where it reaches (D-04-17), in the display language of the user.
	 *
	 * @return list<string>
	 */
	private function headerLines(bool $partial, int $untilMs): array {
		$lines = [$this->l10n->t('Subtitle draft, created automatically and not reviewed.')];
		if ($partial) {
			$lines[] = $this->l10n->t('Transcript up to %s, the file is still being processed.', [Provider::clock($untilMs)]);
		}

		return $lines;
	}

	/**
	 * Only lines that cannot break a NOTE block: an arrow or a line break
	 * would end the note and turn the rest into cue text, so such a line is
	 * left out and logged with the file id only (T-04-32; the text gate
	 * holds the catalogues to the same rule).
	 *
	 * @param list<string> $lines
	 * @return list<string>
	 */
	private function noteSafe(array $lines, int $fileId): array {
		$safe = [];
		foreach ($lines as $line) {
			if (str_contains($line, '-->') || str_contains($line, "\n") || str_contains($line, "\r")) {
				$this->logger->warning('Audio & Video Search: a catalogue line cannot stand in a VTT note and is left out', [
					'fileId' => $fileId,
				]);
				continue;
			}
			$safe[] = $line;
		}

		return $safe;
	}

	/**
	 * The confirmed file and the uid, or null. The lookup runs as the signed
	 * in user through ReaderContext, like every other lookup of this app, so
	 * the Team Folder ACL answers as in the Files app (gate rule 4).
	 *
	 * @return array{File, string}|null
	 */
	private function resolve(int $fileId): ?array {
		$uid = $this->userSession->getUser()?->getUID();
		if (!is_string($uid) || $uid === '') {
			return null;
		}

		try {
			return $this->readerContext->actAs($uid, function () use ($uid, $fileId): ?array {
				$file = FileAccess::readableFile($this->rootFolder->getUserFolder($uid), $fileId);

				return $file === null ? null : [$file, $uid];
			});
		} catch (\Throwable $e) {
			// Class name only: a library message is where a path shows up.
			$this->logger->warning('Audio & Video Search: a file for the export could not be resolved', [
				'fileId' => $fileId,
				'class' => $e::class,
			]);

			return null;
		}
	}

	/**
	 * The error page of the download (UI-SPEC D2): title T29, one sentence
	 * for the case, the way back to the playback page with the same file id
	 * and, when the request carried a valid one, the same time mark. The
	 * pages of 'none' are byte for byte equal for every reason that ends
	 * there (X4 leak rule).
	 */
	private function errorPage(string $case, int $status, int $fileId, int $startMs): TemplateResponse {
		$parameters = ['fileId' => $fileId];
		$raw = $this->request->getParam('t', '');
		if ($startMs > 0 && is_string($raw)) {
			$parameters['t'] = $raw;
		}

		$response = new TemplateResponse(Application::APP_ID, 'export_error', [
			'case' => $case,
			'backUrl' => $this->urlGenerator->linkToRoute('audio_video_search.page.play', $parameters),
			// The page has no app navigation; the skip link of the layout
			// must not point at one.
			'id-app-navigation' => null,
		], TemplateResponse::RENDER_AS_USER);
		$response->setStatus($status);

		return $response;
	}

	/** An empty answer with a status, for the track: no page, no body, no disposition. */
	private function emptyAnswer(int $status): DataDisplayResponse {
		$response = new DataDisplayResponse('', $status);
		$response->addHeader('Content-Disposition', null);

		return $response;
	}

	/** The file name in NFC, as ExclusionService composes its rules. */
	private static function composed(string $value): string {
		if (!class_exists(\Normalizer::class)) {
			return $value;
		}
		$composed = \Normalizer::normalize($value, \Normalizer::FORM_C);

		return is_string($composed) ? $composed : $value;
	}
}
