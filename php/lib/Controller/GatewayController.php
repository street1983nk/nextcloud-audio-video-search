<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Controller;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Service\FileAccess;
use OCA\AudioVideoSearch\Service\ReaderContext;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\StreamResponse;
use OCP\AppFramework\OCSController;
use OCP\Files\File;
use OCP\Files\IRootFolder;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * The read only channel the container uses to get at file content.
 *
 * Taken over from Findling. The permission decision happens here and nowhere
 * else: the container names a user, this class resolves the file through that
 * user's own folder, so the real Nextcloud permission model answers the
 * question. There is no second, drifting permission model in Python.
 */
final class GatewayController extends OCSController {
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
	 * filtered. The digit requirement keeps the route from matching a sibling
	 * route under /files/ that a later plan may add.
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
			// The folder and the lookup run with the named user as the active
			// user of the request (see ReaderContext): groupfolders builds the
			// mount of a member as "in share" when somebody else is active.
			$file = $this->readerContext->actAs(
				$userId,
				fn (): ?File => FileAccess::readableFile($this->rootFolder->getUserFolder($userId), $fileId),
			);
			// Not visible, not readable and not existing deliberately give the
			// same answer, so the gateway cannot be used to probe for files.
			if ($file === null) {
				return new DataResponse(['error' => 'Node is not a file or could not be found.'], Http::STATUS_NOT_FOUND);
			}

			// The 'r' is the entire read only guarantee at this spot. It must
			// never become 'r+', 'w', 'a' or 'x'. Deliberately after the switch
			// above has been undone, so read hooks see the identity of the
			// request and not the member.
			$stream = $file->fopen('r');
			if (!$stream) {
				// A static sentence and the file id, never a path or a user.
				$this->logger->warning('Audio & Video Search: a file could not be opened for reading, answered 422', ['fileId' => $fileId]);
				return new DataResponse(['error' => 'File could not be opened for reading.'], Http::STATUS_UNPROCESSABLE_ENTITY);
			}

			return new StreamResponse($stream);
		} catch (\OC\User\NoUserException) {
			// Word for word the answer of the not-found branch above, so the
			// route cannot be used to enumerate the user names of an instance.
			$this->logger->debug('Audio & Video Search: content gateway asked for a user that does not exist');
			return new DataResponse(['error' => 'Node is not a file or could not be found.'], Http::STATUS_NOT_FOUND);
		} catch (\Throwable $e) {
			// A storage that is only down for a while is a 500 and never a 404:
			// the container judges the one file failed and tries again later.
			// The exception travels in the exception field, which Nextcloud
			// renders itself; the message of this app is a static sentence,
			// because a library message is where an absolute path shows up.
			$this->logger->error('Audio & Video Search: unknown error reading a file', ['exception' => $e]);
			return new DataResponse(['error' => 'Unknown error occurred.'], Http::STATUS_INTERNAL_SERVER_ERROR);
		}
	}

	/**
	 * The attribute on the method above answers "is this a registered external
	 * app", not "is this our external app". Every other backend on the
	 * instance passes that test, so without this comparison any other
	 * container could read any file of any user through this route. AppAPI
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
