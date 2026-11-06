<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\AppInfo;

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
	 */
	public function register(IRegistrationContext $context): void {
		$context->registerSearchProvider(Provider::class);
	}

	public function boot(IBootContext $context): void {
	}
}
