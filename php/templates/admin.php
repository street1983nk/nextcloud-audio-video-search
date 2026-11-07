<?php

declare(strict_types=1);

/**
 * The admin section: state of the other half, versions, time of the check,
 * "Check again" and, in debug mode only, the test result switch (UI-SPEC,
 * surface 3), in this order.
 *
 * All seven state banners are rendered here, the current one visible and the
 * others hidden, plus the hidden warning for a failed recheck. admin.js flips
 * hidden attributes and replaces text nodes; it never builds markup. Without
 * JavaScript a reload shows the new state.
 *
 * The versions sit inside the translated sentences as spans: each sentence is
 * translated with private use characters in place of its placeholders and
 * split around them, so the language decides where a version goes and the
 * script can replace the version alone.
 *
 * Every visible string runs through $l->t(), every value from elsewhere is
 * printed with p(). No inline script (CSP), no style attribute (theme). No
 * file name and no path appears anywhere on this page (T-01-34).
 *
 * @var array<string,mixed> $_ the parameters of Settings\Admin::getForm()
 * @var \OCP\IL10N $l
 */

// Here and not in getForm(): the layout collects its resource lists after the
// template has been rendered. The banner rules live in play.css only.
\OCP\Util::addScript('audio_video_search', 'admin');
\OCP\Util::addStyle('audio_video_search', 'play');
\OCP\Util::addStyle('audio_video_search', 'admin');

// Material Design Icons by Pictogrammers (Apache-2.0), path data only.
$icons = [
	'error' => 'M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z',
	'warning' => 'M12,2L1,21H23M12,6L19.53,19H4.47M11,10V14H13V10M11,16V18H13V16',
	'info' => 'M11,9H13V7H11M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M11,17H13V11H11V17Z',
	'success' => 'M12,2C6.5,2 2,6.5 2,12C2,17.5 6.5,22 12,22C17.5,22 22,17.5 22,12C22,6.5 17.5,2 12,2M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M16.59,7.58L10,14.17L7.41,11.59L6,13L10,17L18,9L16.59,7.58Z',
];

// The parameters, read defensively.
$states = ['ok', 'version_patch_differs', 'version_drift', 'backend_missing', 'backend_disabled', 'backend_unreachable', 'no_app_api'];
$state = in_array($_['state'] ?? null, $states, true) ? $_['state'] : 'backend_unreachable';
$unknown = $l->t('unknown');
$own = is_string($_['own'] ?? null) && $_['own'] !== '' ? $_['own'] : $unknown;
$backend = is_string($_['backend'] ?? null) && $_['backend'] !== '' ? $_['backend'] : $unknown;
$checkedAtText = is_string($_['checkedAtText'] ?? null) ? $_['checkedAtText'] : '';
$checkedAtIso = is_string($_['checkedAtIso'] ?? null) ? $_['checkedAtIso'] : '';
// The app management of the server, the one action of an error banner.
// From Nextcloud 34 on it is the app "appstore"; up to 33 it belongs to
// settings. An unknown route gives an empty string, so the second name only
// counts where the first one does not exist.
$urlGenerator = \OCP\Server::get(\OCP\IURLGenerator::class);
$appsUrl = $urlGenerator->linkToRoute('appstore.page.viewApps');
if ($appsUrl === '') {
	$appsUrl = $urlGenerator->linkToRoute('settings.AppSettings.viewApps');
}
$debug = ($_['debug'] ?? false) === true;
$sampleVisible = ($_['sampleVisible'] ?? false) === true;
$sampleCount = is_int($_['sampleCount'] ?? null) ? $_['sampleCount'] : null;

// Placeholders: the own version, the backend version, the time of the check.
$markOwn = "\u{E000}";
$markBackend = "\u{E001}";
$markTime = "\u{E002}";

/**
 * A translated sentence as a list of pieces: [kind, text], kind one of
 * text, own, backend, time.
 *
 * @return list<array{string, string}>
 */
$pieces = static function (string $sentence) use ($markOwn, $markBackend, $markTime): array {
	$parts = preg_split('/(\x{E000}|\x{E001}|\x{E002})/u', $sentence, -1, PREG_SPLIT_DELIM_CAPTURE | PREG_SPLIT_NO_EMPTY);
	$found = [];
	foreach (is_array($parts) ? $parts : [] as $part) {
		$found[] = match ($part) {
			$markOwn => ['own', ''],
			$markBackend => ['backend', ''],
			$markTime => ['time', ''],
			default => ['text', $part],
		};
	}

	return $found;
};

// One banner per state; 'action' names the link to the app management.
$banners = [
	'ok' => ['kind' => 'success', 'action' => false,
		'text' => $l->t('Both apps are connected and run version %s.', [$markOwn])],
	'version_patch_differs' => ['kind' => 'info', 'action' => false,
		'text' => $l->t('Both apps are connected. Their versions differ only in the last part: this app %1$s, backend %2$s. Search works normally. Bring both apps to the same version at the next update.', [$markOwn, $markBackend])],
	'version_drift' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('The two apps run different versions: this app %1$s, backend %2$s. As long as they do not match, search returns no results from audio and video. Bring both apps to the same version.', [$markOwn, $markBackend])],
	'backend_missing' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('The app "Audio & Video Search Backend" is not installed. Without it, search finds nothing in audio and video. Install the app under Apps.')],
	'backend_disabled' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('The app "Audio & Video Search Backend" is installed but disabled. Until it is enabled, search returns no results from audio and video. Enable the app under Apps.')],
	'backend_unreachable' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('The backend does not answer. Until it does, search returns no results from audio and video. Check under Apps that "Audio & Video Search Backend" is running, and in the AppAPI settings that the deploy daemon can be reached.')],
	'no_app_api' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('The AppAPI app is not enabled. The backend of this app only runs through AppAPI. Enable AppAPI under Apps and set up a deploy daemon.')],
];
?>
<div id="avs-admin" class="section avs-admin" data-unknown="<?php p($unknown); ?>">
	<h2><?php p($l->t('Connection to the backend')); ?></h2>

	<div id="avs-backend-state" class="avs-admin__state" role="status" aria-live="polite" tabindex="-1">
		<?php foreach ($banners as $name => $banner) { ?>
			<div class="avs-banner avs-banner--<?php p($banner['kind']); ?>" data-state="<?php p($name); ?>"<?php if ($name !== $state) { ?> hidden<?php } ?>>
				<span class="avs-banner__icon"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icons[$banner['kind']]); ?>"/></svg></span>
				<div class="avs-banner__body">
					<p class="avs-banner__text"><?php foreach ($pieces($banner['text']) as [$kind, $text]) {
						if ($kind === 'own') {
							?><span class="avs-version-own"><?php p($own); ?></span><?php
						} elseif ($kind === 'backend') {
							?><span class="avs-version-backend"><?php p($backend); ?></span><?php
						} else {
							p($text);
						}
					} ?></p>
					<?php if ($banner['action'] && $appsUrl !== '') { ?>
						<a class="avs-banner__action" href="<?php p($appsUrl); ?>"><?php p($l->t('Open Apps')); ?></a>
					<?php } ?>
				</div>
			</div>
		<?php } ?>

		<div id="avs-recheck-failed" class="avs-banner avs-banner--warning" hidden>
			<span class="avs-banner__icon"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icons['warning']); ?>"/></svg></span>
			<div class="avs-banner__body">
				<p class="avs-banner__text"><?php p($l->t('The state could not be checked again. Shown is the state from when the page was loaded.')); ?></p>
			</div>
		</div>
	</div>

	<p class="avs-admin__line"><?php foreach ($pieces($l->t('This app: %1$s · Backend: %2$s', [$markOwn, $markBackend])) as [$kind, $text]) {
		if ($kind === 'own') {
			?><span class="avs-version-own"><?php p($own); ?></span><?php
		} elseif ($kind === 'backend') {
			?><span class="avs-version-backend"><?php p($backend); ?></span><?php
		} else {
			p($text);
		}
	} ?></p>

	<p class="avs-admin__line"><?php foreach ($pieces($l->t('Last checked: %s', [$markTime])) as [$kind, $text]) {
		if ($kind === 'time') {
			?><time id="avs-checked-at" class="avs-admin__time" datetime="<?php p($checkedAtIso); ?>"><?php p($checkedAtText); ?></time><?php
		} else {
			p($text);
		}
	} ?></p>

	<div class="avs-admin__actions">
		<button type="button" id="avs-recheck" class="avs-admin__recheck" data-checking="<?php p($l->t('Checking…')); ?>">
			<span id="avs-recheck-spinner" class="icon-loading-small avs-admin__spinner" aria-hidden="true" hidden></span>
			<span id="avs-recheck-label"><?php p($l->t('Check again')); ?></span>
		</button>
	</div>

	<?php if ($debug) { ?>
		<div class="avs-admin__debug">
			<h3 class="avs-admin__subheading"><?php p($l->t('Test result')); ?></h3>
			<p class="avs-admin__switch">
				<input type="checkbox" id="avs-sample-visible" class="checkbox" aria-describedby="avs-sample-hint"<?php if ($sampleVisible) { ?> checked<?php } ?>>
				<label for="avs-sample-visible"><?php p($l->t('Show the test result in search')); ?></label>
				<span id="avs-sample-status" class="avs-admin__status" role="status" data-saved="<?php p($l->t('Saved')); ?>" data-failed="<?php p($l->t('Not saved. Try again.')); ?>"></span>
			</p>
			<p id="avs-sample-hint" class="settings-hint"><?php p($l->t('For testing only. The test result only appears while this switch is on and the instance runs in debug mode. Switching it off hides it at once, the test data stays.')); ?></p>
			<p id="avs-sample-empty" class="settings-hint"<?php if ($sampleCount !== null && $sampleCount > 0) { ?> hidden<?php } ?>><?php p($l->t('No test result yet. Create one with:')); ?> <code class="avs-admin__command">occ audio_video_search:sample &lt;fileId&gt;</code></p>
		</div>
	<?php } ?>
</div>
