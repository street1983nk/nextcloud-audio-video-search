<?php

declare(strict_types=1);

/**
 * Bootstrap of the PHPUnit suite of the PHP app (taken over from Findling).
 *
 * The suite mocks OCP interfaces, so OCP has to exist before the first test
 * class loads. The one supported way: run inside a checkout of
 * nextcloud/server with this app in apps/audio_video_search, server bootstrap
 * first, then the composer autoloader of this app for OCA\AudioVideoSearch and
 * OCA\AudioVideoSearch\Tests.
 *
 * A missing server checkout would otherwise surface much later as "Class
 * OCP\Files\IRootFolder not found" inside a test, which reads like a broken
 * test and is really a broken path. So the path is checked here, once.
 *
 * Default layout: the CI job puts the server at the workspace root and MOVES
 * the php directory of this repository to apps/audio_video_search, so the
 * server root is three levels above this directory. NEXTCLOUD_SERVER_ROOT
 * overrides that for any other layout.
 */
$serverRoot = getenv('NEXTCLOUD_SERVER_ROOT');
if (!is_string($serverRoot) || $serverRoot === '') {
	$serverRoot = dirname(__DIR__, 3);
	$origin = 'the default layout, three levels above ' . __DIR__;
} else {
	$origin = 'the environment variable NEXTCLOUD_SERVER_ROOT';
}

$serverBootstrap = rtrim($serverRoot, '/\\') . '/tests/bootstrap.php';

if (!is_file($serverBootstrap)) {
	fwrite(STDERR, <<<MESSAGE

		Audio & Video Search test bootstrap: no nextcloud/server checkout at this path.

		  looked for : {$serverBootstrap}
		  taken from : {$origin}

		This suite mocks OCP interfaces, so it can only run inside a checkout of
		nextcloud/server with this app placed in apps/audio_video_search. Point
		NEXTCLOUD_SERVER_ROOT at the root of that checkout, or move the app into
		apps/audio_video_search of one. The job "phpunit" in
		.github/workflows/php.yml is the reference layout.


		MESSAGE);
	exit(1);
}

require_once $serverBootstrap;

/**
 * The autoloader of this app, second on purpose: it adds OCA\AudioVideoSearch
 * and OCA\AudioVideoSearch\Tests on top of the server's autoload space.
 */
$appAutoload = dirname(__DIR__) . '/vendor/autoload.php';

if (!is_file($appAutoload)) {
	fwrite(STDERR, <<<MESSAGE

		Audio & Video Search test bootstrap: no vendor/autoload.php next to this suite.

		  looked for : {$appAutoload}

		Run "composer install" in the php directory of this app first.


		MESSAGE);
	exit(1);
}

require_once $appAutoload;
