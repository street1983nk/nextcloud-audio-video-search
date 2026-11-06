<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Service;

use OCP\IUserManager;
use OCP\IUserSession;

/**
 * Run a lookup as the member it is asked for, and only for that span.
 *
 * Taken over from Findling (issue #14 there). groupfolders builds the mount of
 * a Team Folder member with in_share=true whenever the request is not a CLI
 * run and the active user of the request is not that member. Under in_share
 * the ACL wrappers raise the minimum a path needs from READ to READ plus SHARE,
 * so a Team Folder with +read and -share is readable for every member in their
 * own browser and hidden in every request where this app asks on their behalf:
 * the content gateway (active user: nobody) and the occ command.
 *
 * The switch has to cover the FIRST mount setup of that member in the request
 * and the lookup after it; groupfolders fixes the flag once, when the mount is
 * built.
 *
 * setVolatileActiveUser() sets the active user of this request only: no
 * session write, no login event, no hook. The previous user is restored in
 * finally with the very object getUser() returned before the switch, because a
 * null handed back means "reload from the session storage" and not "nobody".
 *
 * An unknown uid is not switched to. The work runs unchanged, so the answer
 * for a user that does not exist stays word for word what it was, and the
 * switch cannot be used to find out which users exist.
 */
final class ReaderContext {
	public function __construct(
		private IUserSession $userSession,
		private IUserManager $userManager,
	) {
	}

	/**
	 * The result of $work, computed with $uid as the active user of the request.
	 *
	 * @template T
	 * @param \Closure(): T $work
	 * @return T
	 */
	public function actAs(string $uid, \Closure $work): mixed {
		$previous = $this->userSession->getUser();
		if ($previous !== null && $previous->getUID() === $uid) {
			return $work();
		}

		$member = $this->userManager->get($uid);
		if ($member === null) {
			return $work();
		}

		$this->userSession->setVolatileActiveUser($member);
		try {
			return $work();
		} finally {
			$this->userSession->setVolatileActiveUser($previous);
		}
	}
}
