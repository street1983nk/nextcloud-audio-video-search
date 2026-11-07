<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\AppInfo;

use OCA\AudioVideoSearch\Listener\CacheEventListener;
use OCA\AudioVideoSearch\Listener\FileEventListener;
use OCA\AudioVideoSearch\Listener\UserEventListener;
use OCA\AudioVideoSearch\Search\Provider;
use OCP\AppFramework\App;
use OCP\AppFramework\Bootstrap\IBootContext;
use OCP\AppFramework\Bootstrap\IBootstrap;
use OCP\AppFramework\Bootstrap\IRegistrationContext;

class Application extends App implements IBootstrap {
	public const APP_ID = 'audio_video_search';

	/**
	 * The ExApp half in the External Apps section of the store. Both ids are
	 * frozen: the app certificates are bound to them.
	 */
	public const BACKEND_APP_ID = 'audio_video_search_backend';

	public function __construct(array $urlParams = []) {
		parent::__construct(self::APP_ID, $urlParams);
	}

	/**
	 * The search provider is registered here and only here: registering it in
	 * boot() fails silently, without an error and without a result group in
	 * the search bar, because boot() runs too late (Findling finding).
	 *
	 * The listeners of the discovery (plan 02-07) are registered here as well,
	 * one list per listener, so the ways into the work stock stay countable.
	 * System tag events are not among them on purpose: tagging changes nothing
	 * to transcribe (RESEARCH, Befund 8).
	 */
	public function register(IRegistrationContext $context): void {
		$context->registerSearchProvider(Provider::class);

		foreach ([
			\OCP\Files\Events\Node\NodeCreatedEvent::class,
			\OCP\Files\Events\Node\NodeWrittenEvent::class,
			\OCP\Files\Events\Node\NodeTouchedEvent::class,
			\OCP\Files\Events\Node\NodeCopiedEvent::class,
			\OCP\Files\Events\Node\NodeRenamedEvent::class,
			\OCP\Files\Events\Node\NodeDeletedEvent::class,
		] as $event) {
			$context->registerEventListener($event, FileEventListener::class);
		}

		// What a scanner finds (occ files:scan, the rescan of external
		// storages) raises no node event, only these.
		foreach ([
			\OCP\Files\Cache\CacheEntryInsertedEvent::class,
			\OCP\Files\Cache\CacheEntryUpdatedEvent::class,
			\OCP\Files\Cache\CacheEntryRemovedEvent::class,
		] as $event) {
			$context->registerEventListener($event, CacheEventListener::class);
		}

		// A deleted user is only a hint for the sweep of the container.
		$context->registerEventListener(\OCP\User\Events\UserDeletedEvent::class, UserEventListener::class);
	}

	public function boot(IBootContext $context): void {
	}
}
