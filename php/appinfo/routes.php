<?php

declare(strict_types=1);

/**
 * Both arrays stay empty on purpose: every route of this app is declared with
 * a route attribute on the controller method that implements it. The file has
 * to exist, otherwise Nextcloud reports a missing routes file for the app.
 */
return [
	'routes' => [],
	'ocs' => [],
];
