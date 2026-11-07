<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Controller;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Service\FileAccess;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataDisplayResponse;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\StreamResponse;
use OCP\AppFramework\OCSController;
use OCP\Files\File;
use OCP\Files\ForbiddenException;
use OCP\Files\IRootFolder;
use OCP\IRequest;
use OCP\Lock\LockedException;
use Psr\Log\LoggerInterface;

/**
 * The read only channel the container uses to get at file content.
 *
 * Taken over from Findling. The permission decision happens here and nowhere
 * else: the container names a user, this class resolves the file through that
 * user's own folder, so the real Nextcloud permission model answers the
 * question. There is no second, drifting permission model in Python.
 *
 * Two routes share one way to the file (resolve) and one translation of a
 * failure (failure): the full content for the capture, and the head of a file
 * for the read proof of a further copy (D-02-01a, plan 13). The reason of a
 * refusal travels in the header X-AVS-Reason as well as in the body, because
 * the OCS body is XML or JSON depending on the request while a header is the
 * same for both (container: nc.py, REASON_HEADER):
 *
 *   404                 not visible, not readable, not a file, unknown user
 *   403 access_control  files_accesscontrol refused the read (pitfall 7)
 *   423 locked          the file is locked, for example during an upload (pitfall 8)
 *   422                 fopen failed; the container reads it as read_denied
 *   500                 anything else; the container tries again later
 *
 * PHP cannot interrupt a hanging smbclient (Findling measurement A6: a DENY
 * READ ACE lists the file, isReadable() says yes and the download hangs). The
 * time limit and the circuit per storage live in the container (plan 13);
 * operators of php-fpm set request_terminate_timeout (documentation, plan 21).
 *
 * No branch of either route depends on debug, IConfig or IAppConfig: there is
 * no way to switch the read proof off (D-02-10, gate in plan 13).
 */
final class GatewayController extends OCSController {
	/** The head the read proof compares: the first 64 KiB of the content. */
	public const HEAD_BYTES = 65536;
	/** The header that names the reason of a 403 or 423 for the container. */
	public const REASON_HEADER = 'X-AVS-Reason';
	public const REASON_ACCESS_CONTROL = 'access_control';
	public const REASON_LOCKED = 'locked';
	/** Upper bound of read calls for one head, so a stream that never ends a read cannot spin. */
	private const MAX_HEAD_READS = 4096;

	public function __construct(
		IRequest $request,
		private IRootFolder $rootFolder,
		private LoggerInterface $logger,
		private ReaderContext $readerContext,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	/**
	 * Full path from the outside:
	 * GET /ocs/v2.php/apps/audio_video_search/files/{fileId}?userId=<uid>
	 *
	 * The first attribute locks browsers and ordinary users out; the signed
	 * AppAPI header is the credential, which is also why session CSRF does not
	 * apply. The attributes are spelled fully qualified, so the static gate in
	 * backend/tests/test_php_gates.py reads them off the source.
	 *
	 * The file id is an int and there is no path string anywhere in this
	 * signature, so path traversal is structurally impossible rather than
	 * filtered. The digit requirement keeps the route from matching the head
	 * route below.
	 */
	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'GET', url: '/files/{fileId}', requirements: ['fileId' => '\d+'])]
	public function getFileContents(int $fileId, string $userId): DataResponse|StreamResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		try {
			$file = $this->resolve($fileId, $userId);
			// Not visible, not readable and not existing deliberately give the
			// same answer, so the gateway cannot be used to probe for files.
			if ($file === null) {
				return $this->notFound();
			}

			// The 'r' is the entire read only guarantee at this spot. It must
			// never become 'r+', 'w', 'a' or 'x'. Deliberately after the switch
			// in resolve has been undone, so read hooks see the identity of the
			// request and not the member.
			$stream = $file->fopen('r');
			if (!$stream) {
				return $this->notOpened($fileId);
			}

			return new StreamResponse($stream);
		} catch (\Throwable $e) {
			return $this->failure($e, $fileId);
		}
	}

	/**
	 * The head of a file for the read proof:
	 * GET /ocs/v2.php/apps/audio_video_search/files/{fileId}/head?userId=<uid>
	 *
	 * Exactly min(65536, size) bytes as application/octet-stream, read
	 * through the same resolve as the full content, so the read proof asks
	 * exactly the question the capture asks. Every refusal is the answer of
	 * the gateway, word for word.
	 */
	#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
	#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
	#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'GET', url: '/files/{fileId}/head', requirements: ['fileId' => '\d+'])]
	public function getFileHead(int $fileId, string $userId): DataResponse|DataDisplayResponse {
		$foreign = $this->rejectForeignCaller();
		if ($foreign !== null) {
			return $foreign;
		}

		try {
			$file = $this->resolve($fileId, $userId);
			if ($file === null) {
				return $this->notFound();
			}

			// Read only, as above.
			$stream = $file->fopen('r');
			if (!$stream) {
				return $this->notOpened($fileId);
			}

			try {
				$head = self::readHead($stream);
			} finally {
				fclose($stream);
			}
			if ($head === null) {
				return $this->notOpened($fileId);
			}

			return new DataDisplayResponse($head, Http::STATUS_OK, ['Content-Type' => 'application/octet-stream']);
		} catch (\Throwable $e) {
			return $this->failure($e, $fileId);
		}
	}

	/**
	 * Up to HEAD_BYTES bytes from the start of a stream, null when a read
	 * fails. A short read is continued until the limit or the end.
	 *
	 * @param resource $stream
	 */
	private static function readHead($stream): ?string {
		$head = '';
		for ($reads = 0; $reads < self::MAX_HEAD_READS && strlen($head) < self::HEAD_BYTES; $reads++) {
			if (feof($stream)) {
				return $head;
			}
			$chunk = fread($stream, self::HEAD_BYTES - strlen($head));
			if ($chunk === false) {
				return null;
			}
			$head .= $chunk;
		}

		return strlen($head) === self::HEAD_BYTES || feof($stream) ? $head : null;
	}

	/**
	 * The file behind the id in the tree of the named user, or null.
	 *
	 * The folder and the lookup run with the named user as the active user of
	 * the request (see ReaderContext): groupfolders builds the mount of a
	 * member as "in share" when somebody else is active.
	 */
	private function resolve(int $fileId, string $userId): ?File {
		return $this->readerContext->actAs(
			$userId,
			fn (): ?File => FileAccess::readableFile($this->rootFolder->getUserFolder($userId), $fileId),
		);
	}

	private function notFound(): DataResponse {
		return new DataResponse(['error' => 'Node is not a file or could not be found.'], Http::STATUS_NOT_FOUND);
	}

	private function notOpened(int $fileId): DataResponse {
		// A static sentence and the file id, never a path or a user.
		$this->logger->warning('Audio & Video Search: a file could not be opened for reading, answered 422', ['fileId' => $fileId]);
		return new DataResponse(['error' => 'File could not be opened for reading.'], Http::STATUS_UNPROCESSABLE_ENTITY);
	}

	/**
	 * One translation of a failure for both routes. The messages of
	 * ForbiddenException and LockedException carry the path, so neither goes
	 * into the log; the line names the file id and the reason only.
	 */
	private function failure(\Throwable $e, int $fileId): DataResponse {
		if ($e instanceof \OC\User\NoUserException) {
			// Word for word the answer of the not-found branch, so the route
			// cannot be used to enumerate the user names of an instance.
			$this->logger->debug('Audio & Video Search: content gateway asked for a user that does not exist');
			return $this->notFound();
		}

		if ($e instanceof ForbiddenException) {
			$this->logger->info('Audio & Video Search: access control refused a read, answered 403', ['fileId' => $fileId, 'reason' => self::REASON_ACCESS_CONTROL]);
			$response = new DataResponse(
				['error' => 'Access denied by access control.', 'code' => self::REASON_ACCESS_CONTROL],
				Http::STATUS_FORBIDDEN,
			);
			$response->addHeader(self::REASON_HEADER, self::REASON_ACCESS_CONTROL);
			return $response;
		}

		if ($e instanceof LockedException) {
			$this->logger->info('Audio & Video Search: a file is locked, answered 423', ['fileId' => $fileId, 'reason' => self::REASON_LOCKED]);
			$response = new DataResponse(
				['error' => 'File is locked.', 'code' => self::REASON_LOCKED],
				Http::STATUS_LOCKED,
			);
			$response->addHeader(self::REASON_HEADER, self::REASON_LOCKED);
			return $response;
		}

		// A storage that is only down for a while is a 500 and never a 404:
		// the container judges the one file failed and tries again later.
		// The exception travels in the exception field, which Nextcloud
		// renders itself; the message of this app is a static sentence,
		// because a library message is where an absolute path shows up.
		$this->logger->error('Audio & Video Search: unknown error reading a file', ['exception' => $e]);
		return new DataResponse(['error' => 'Unknown error occurred.'], Http::STATUS_INTERNAL_SERVER_ERROR);
	}

	/**
	 * The attribute on the methods above answers "is this a registered
	 * external app", not "is this our external app". Every other backend on
	 * the instance passes that test, so without this comparison any other
	 * container could read any file of any user through these routes. AppAPI
	 * puts the calling app id into this header.
	 *
	 * Residual risk, written down rather than pretended away: this trusts
	 * AppAPI to have authenticated the caller before the request arrives.
	 * Whoever can forge that header has broken the AppAPI trust model itself.
	 */
	private function rejectForeignCaller(): ?DataResponse {
		$callerAppId = $this->request->getHeader('EX-APP-ID');
		if ($callerAppId === Application::BACKEND_APP_ID) {
			return null;
		}

		$this->logger->warning('Audio & Video Search: content gateway called by a foreign ExApp', ['app' => $callerAppId]);

		return new DataResponse(
			['error' => 'This route is reserved for the Audio & Video Search backend.'],
			Http::STATUS_FORBIDDEN,
		);
	}
}
