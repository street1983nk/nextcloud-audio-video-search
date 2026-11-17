<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Listener;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\EventDispatcher\Event;
use OCP\EventDispatcher\IEventListener;
use OCP\IAppConfig;
use OCP\User\Events\UserDeletedEvent;
use Psr\Log\LoggerInterface;

/**
 * A deleted user is only a hint for the sweep of the container, never a deletion here.
 *
 * Removing references belongs to one place: the sweep of the reconcile asks
 * the PHP app which storages are gone (classifyAbsent) and only then marks or
 * forgets (RESEARCH, Pattern 2; D-02-13). A listener that deleted on its own
 * would be a second, untested way to the same result, and it would run before
 * the home storage is really gone. So the listener writes the time of the last
 * deletion into the app config; the reconcile (plan 02-20) reads it as a reason
 * to sweep at once instead of at its next cadence.
 *
 * No user id is written or logged. A failure never reaches the deletion.
 *
 * @template-implements IEventListener<Event>
 */
class UserEventListener implements IEventListener {
	/** App config key: the time of the last user deletion, a hint for the sweep. */
	public const SWEEP_HINT_KEY = 'sweep_hint_at';

	public function __construct(
		private IAppConfig $appConfig,
		private ITimeFactory $timeFactory,
		private LoggerInterface $logger,
	) {
	}

	public function handle(Event $event): void {
		if (!$event instanceof UserDeletedEvent) {
			return;
		}
		try {
			$this->appConfig->setValueInt(Application::APP_ID, self::SWEEP_HINT_KEY, $this->timeFactory->getTime());
		} catch (\Throwable $e) {
			$this->logger->warning('Audio & Video Search: the sweep hint for a deleted user could not be written', ['class' => $e::class]);
		}
	}
}
