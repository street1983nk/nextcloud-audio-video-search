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
		'text' => $l->t('Both apps are connected.')],
	'version_patch_differs' => ['kind' => 'info', 'action' => false,
		'text' => $l->t('Minor version difference. Search works; align both apps at the next update.')],
	'version_drift' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('The versions do not match. Search finds nothing in audio and video until both are the same.')],
	'backend_missing' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('The backend is not installed. Without it, search finds nothing in audio and video.')],
	'backend_disabled' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('The backend is disabled. Search finds nothing in audio and video until it is enabled again.')],
	'backend_unreachable' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('The backend does not respond. Check that it is running and that the deploy daemon can be reached.')],
	'no_app_api' => ['kind' => 'error', 'action' => true,
		'text' => $l->t('AppAPI is not enabled. The backend only runs through AppAPI.')],
];
?>
<div id="avs-admin" class="section avs-admin" data-unknown="<?php p($unknown); ?>">
	<h2><?php p($l->t('Connection to the backend')); ?></h2>

	<div id="avs-backend-state" class="avs-admin__state" role="status" aria-live="polite" tabindex="-1">
		<?php foreach ($banners as $name => $banner) { ?>
			<div class="avs-banner avs-banner--<?php p($banner['kind']); ?>" data-state="<?php p($name); ?>"<?php if ($name !== $state) { ?> hidden<?php } ?>>
				<span class="avs-banner__icon"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icons[$banner['kind']]); ?>"/></svg></span>
				<div class="avs-banner__body">
					<p class="avs-banner__text"><?php p($banner['text']); ?></p>
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
			<p id="avs-sample-hint" class="settings-hint"><?php p($l->t('For testing only, shown only in debug mode. Switching it off hides it, the data stays.')); ?></p>
			<?php // Only a count the backend reported as zero means "none yet"; an unknown count (backend down) says nothing. ?>
			<p id="avs-sample-empty" class="settings-hint"<?php if ($sampleCount !== 0) { ?> hidden<?php } ?>><?php p($l->t('No test result yet. Create one with:')); ?> <code class="avs-admin__command">occ audio_video_search:sample &lt;fileId&gt;</code></p>
		</div>
	<?php } ?>
</div>

<?php
// -- profile, computing time, models and licences (05-UI-SPEC, plan 05-09) -------
//
// Three more sections out of the same getForm(). Every state is rendered here,
// the current one visible and the others hidden: the two banners of the
// profile, the free and the locked line of each profile, the eleven states of
// each model. admin.js flips hidden, disabled and checked and replaces the
// text of the spans that carry data-value; it never builds markup.
//
// No path, no host and no address other than the fixed links to licence
// texts, README and THIRD-PARTY.md appears here (T-05-19b).

$icons['lock'] = 'M12,17C10.89,17 10,16.1 10,15C10,13.89 10.89,13 12,13A2,2 0 0,1 14,15A2,2 0 0,1 12,17M18,20V10H6V20H18M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6C4.89,22 4,21.1 4,20V10C4,8.89 4.89,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z';
$icons['download'] = 'M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z';

$resources = is_array($_['resources'] ?? null) ? $_['resources'] : null;
$resourceText = is_array($_['resourceText'] ?? null) ? $_['resourceText'] : [];

$profileIds = ['fast', 'balanced', 'quality'];
$profileNames = [
	'fast' => $l->t('Fast'),
	'balanced' => $l->t('Balanced'),
	'quality' => $l->t('Quality'),
];
$profileHints = [
	'fast' => $l->t('Parakeet for all files. Whisper turbo recomputes uncertain passages when memory allows.'),
	'balanced' => $l->t('Parakeet and Whisper turbo for all files, combined into one text.'),
	'quality' => $l->t('Like Balanced, with Whisper large-v3 in addition for German recordings. Slowest.'),
];

// Proper names, not translated.
$modelNames = [
	'parakeet' => 'Parakeet TDT 0.6B v3',
	'silero' => 'Silero VAD',
	'whisper-turbo' => 'Whisper large-v3-turbo',
	'whisper-large-v3' => 'Whisper large-v3',
];

// The licence texts: navigation the admin clicks, the app itself opens no
// connection for them.
$licenses = [
	'CC-BY-4.0' => 'https://creativecommons.org/licenses/by/4.0/',
	'MIT' => 'https://opensource.org/license/mit',
	'Apache-2.0' => 'https://www.apache.org/licenses/LICENSE-2.0',
	'LGPL-2.1-or-later' => 'https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html',
	'GPL-2.0-or-later' => 'https://www.gnu.org/licenses/old-licenses/gpl-2.0.html',
];
$readmeOffline = 'https://github.com/street1983nk/nextcloud-audio-video-search#offline';
$thirdParty = 'https://github.com/street1983nk/nextcloud-audio-video-search/blob/main/THIRD-PARTY.md';

// Placeholders of a sentence: private use characters again, sixteen of them.
$slot = static fn (int $position): string => mb_chr(0xE010 + $position, 'UTF-8');
$number = static fn (string $key, string $shown): array => ['number', $key, $shown];
$word = static fn (string $key, string $shown): array => ['word', $key, $shown];
$license = static fn (string $id): array => ['link', $licenses[$id] ?? '', $id];

/**
 * Print a translated sentence whose placeholders are slots: a number or a
 * word in a span admin.js can replace, or a licence id as a link. The
 * language decides where a slot stands.
 *
 * @param list<array{string, string, string}> $slots
 */
$say = static function (string $sentence, array $slots): void {
	$parts = preg_split('/([\x{E010}-\x{E01F}])/u', $sentence, -1, PREG_SPLIT_DELIM_CAPTURE | PREG_SPLIT_NO_EMPTY);
	foreach (is_array($parts) ? $parts : [] as $part) {
		$index = mb_ord($part, 'UTF-8') - 0xE010;
		$found = $index >= 0 && $index < 16 ? ($slots[$index] ?? null) : null;
		if ($found === null) {
			p($part);
		} elseif ($found[0] === 'link') {
			?><a href="<?php p($found[1]); ?>" rel="noreferrer noopener"><?php p($found[2]); ?></a><?php
		} elseif ($found[0] === 'number') {
			?><span class="avs-res__number" data-value="<?php p($found[1]); ?>"><?php p($found[2]); ?></span><?php
		} else {
			?><span data-value="<?php p($found[1]); ?>"><?php p($found[2]); ?></span><?php
		}
	}
};

$icon = static function (string $name) use ($icons): void {
	?><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icons[$name] ?? ''); ?>"/></svg><?php
};

// The values of the contract, read defensively. ExAppService let only the
// exact shape through; a hole here still must not break the page.
$shown = static fn (mixed $value): string => is_string($value) && $value !== '' ? $value : $unknown;
$availableBytes = is_int($resources['availableBytes'] ?? null) ? $resources['availableBytes'] : null;
$minimumBytes = is_int($resources['minimumBytes'] ?? null) ? $resources['minimumBytes'] : 0;
$proposed = in_array($resources['proposed'] ?? null, $profileIds, true) ? $resources['proposed'] : 'none';
$chosen = in_array($resources['chosen'] ?? null, $profileIds, true) ? $resources['chosen'] : null;
$effective = in_array($resources['effective'] ?? null, $profileIds, true) ? $resources['effective'] : 'none';
$profileLocked = [];
foreach (is_array($resources['profiles'] ?? null) ? $resources['profiles'] : [] as $profile) {
	if (is_array($profile) && in_array($profile['id'] ?? null, $profileIds, true)) {
		$profileLocked[$profile['id']] = ($profile['locked'] ?? true) !== false;
	}
}

// R2: below the minimum memory, without a proposal, or with an amount the
// container does not know (fail safe): every profile is locked.
$low = $availableBytes === null || $availableBytes < $minimumBytes || $proposed === 'none';
// R3: the stored choice no longer fits, the app computes with another profile.
$fallback = !$low && $chosen !== null && ($profileLocked[$chosen] ?? true) && $effective !== 'none' && $effective !== $chosen;
// The stored choice stays checked; without one the profile the app computes with.
$checkedProfile = $chosen ?? ($effective !== 'none' ? $effective : null);

$availableText = $shown($resourceText['available'] ?? null);
$minimumText = $shown($resourceText['minimum'] ?? null);
$needText = static fn (string $id): string => $shown(is_array($resourceText['need'] ?? null) ? ($resourceText['need'][$id] ?? null) : null);
$modelText = static fn (string $id, string $key): string => $shown(is_array($resourceText['models'] ?? null) && is_array($resourceText['models'][$id] ?? null) ? ($resourceText['models'][$id][$key] ?? null) : null);
$proposedName = $profileNames[$proposed] ?? $unknown;
$chosenName = $chosen !== null ? $profileNames[$chosen] : $unknown;
$effectiveName = $profileNames[$effective] ?? $chosenName;

$saved = $l->t('Saved');
$notSaved = $l->t('Not saved. Try again.');
?>
<div id="avs-profile" class="section avs-admin" data-unknown="<?php p($unknown); ?>" data-unit="<?php p($shown($resourceText['unit'] ?? '%s GB')); ?>" data-decimal="<?php p(($resourceText['decimal'] ?? '.') === ',' ? ',' : '.'); ?>">
	<h2><?php p($l->t('Transcription profile')); ?></h2>

	<?php if ($resources === null) { ?>
		<div id="avs-resources-unavailable" class="avs-banner avs-banner--warning avs-res__banner" role="status">
			<span class="avs-banner__icon"><?php $icon('warning'); ?></span>
			<div class="avs-banner__body">
				<p class="avs-banner__text"><?php p($l->t('Profile, computing time and model state cannot be loaded right now because the backend does not respond. Reload the page later.')); ?></p>
			</div>
		</div>
	<?php } else { ?>
		<div id="avs-profile-low" class="avs-banner avs-banner--error avs-res__banner" role="alert"<?php if (!$low) { ?> hidden<?php } ?>>
			<span class="avs-banner__icon"><?php $icon('error'); ?></span>
			<div class="avs-banner__body">
				<p class="avs-banner__title"><?php p($l->t('Not enough memory')); ?></p>
				<p class="avs-banner__text"><?php $say($l->t('The app needs at least %1$s, %2$s is available. It therefore transcribes nothing, Nextcloud keeps running normally. Give the container more memory and restart the backend.', [$slot(0), $slot(1)]), [$number('minimum', $minimumText), $number('available', $availableText)]); ?></p>
			</div>
		</div>
		<div id="avs-profile-fallback" class="avs-banner avs-banner--warning avs-res__banner" role="status"<?php if (!$fallback) { ?> hidden<?php } ?>>
			<span class="avs-banner__icon"><?php $icon('warning'); ?></span>
			<div class="avs-banner__body">
				<p class="avs-banner__text"><?php $say($l->t('The chosen profile %1$s no longer fits into memory (needs %2$s, %3$s available). The app uses %4$s until enough memory is free again.', [$slot(0), $slot(1), $slot(2), $slot(3)]), [$word('chosen-name', $chosenName), $number('chosen-need', $chosen !== null ? $needText($chosen) : $unknown), $number('available', $availableText), $word('effective-name', $effectiveName)]); ?></p>
			</div>
		</div>

		<p id="avs-profile-intro" class="avs-res__intro"<?php if ($low) { ?> hidden<?php } ?>><?php $say($l->t('Suggested for this server: %1$s. %2$s of memory is available to the app.', [$slot(0), $slot(1)]), [$word('proposed-name', $proposedName), $number('available', $availableText)]); ?></p>
		<p id="avs-profile-minimum" class="avs-res__hint"><?php $say($l->t('The app needs at least %s of memory.', [$slot(0)]), [$number('minimum', $minimumText)]); ?></p>

		<fieldset id="avs-profile-options" class="avs-res__options"<?php if (!$low) { ?> aria-describedby="avs-profile-intro"<?php } ?>>
			<legend class="hidden-visually"><?php p($l->t('Transcription profile')); ?></legend>
			<?php foreach ($profileIds as $id) {
				$locked = $low || ($profileLocked[$id] ?? true); ?>
				<div class="avs-res__option">
					<span class="avs-res__choice">
						<input type="radio" class="radio" id="avs-profile-<?php p($id); ?>" name="avs-profile" value="<?php p($id); ?>" aria-describedby="avs-profile-<?php p($id); ?>-desc avs-profile-<?php p($id); ?>-<?php p($locked ? 'lock' : 'need'); ?>"<?php if ($checkedProfile === $id) { ?> checked<?php } ?><?php if ($locked) { ?> disabled<?php } ?>>
						<label for="avs-profile-<?php p($id); ?>"><span data-profile-name="<?php p($id); ?>"><?php p($profileNames[$id]); ?></span><span class="avs-res__badge" data-badge="<?php p($id); ?>"<?php if ($low || $proposed !== $id) { ?> hidden<?php } ?>><?php p($l->t('Suggested')); ?></span></label>
					</span>
					<p id="avs-profile-<?php p($id); ?>-desc" class="avs-res__hint"><?php p($profileHints[$id]); ?></p>
					<p id="avs-profile-<?php p($id); ?>-need" class="avs-res__hint"<?php if ($locked) { ?> hidden<?php } ?>><?php $say($l->t('Needs %s of memory.', [$slot(0)]), [$number('need-' . $id, $needText($id))]); ?></p>
					<?php // Outside the label on purpose: the server mutes the label of a disabled radio, the reason must stay readable. ?>
					<p id="avs-profile-<?php p($id); ?>-lock" class="avs-res__lock"<?php if (!$locked) { ?> hidden<?php } ?>><span class="avs-res__icon"><?php $icon('lock'); ?></span><span><?php $say($l->t('Locked: needs %1$s, %2$s available.', [$slot(0), $slot(1)]), [$number('need-' . $id, $needText($id)), $number('available', $availableText)]); ?></span></p>
				</div>
			<?php } ?>
		</fieldset>
		<span id="avs-profile-status" class="avs-admin__status" role="status" data-saved="<?php p($saved); ?>" data-failed="<?php p($notSaved); ?>" data-locked="<?php p($l->t('Not saved. This profile has been locked in the meantime.')); ?>"></span>
	<?php } ?>
</div>

<?php if ($resources !== null) {
	$threads = is_array($resources['threads'] ?? null) ? $resources['threads'] : [];
	$cpus = is_int($threads['cpus'] ?? null) ? $threads['cpus'] : 1;
	$standard = is_int($threads['standard'] ?? null) ? $threads['standard'] : 1;
	$threadsValue = is_int($threads['admin'] ?? null) ? $threads['admin'] : $standard;
	$window = is_array($resources['window'] ?? null) ? $resources['window'] : [];
	$windowStart = is_string($window['start'] ?? null) ? $window['start'] : '';
	$windowEnd = is_string($window['end'] ?? null) ? $window['end'] : '';
	$hasWindow = $windowStart !== '' && $windowEnd !== '';
	$zones = is_array($resources['zones'] ?? null) ? $resources['zones'] : [];
	$defaultZone = is_string($resources['defaultZone'] ?? null) ? $resources['defaultZone'] : 'UTC';
	$windowZone = is_string($window['zone'] ?? null) ? $window['zone'] : $defaultZone;
	$openNow = ($window['openNow'] ?? false) === true;
	$changeAt = $shown($window['changeAt'] ?? null);
	?>
<div id="avs-compute" class="section avs-admin">
	<h2><?php p($l->t('Computing time')); ?></h2>

	<form id="avs-compute-form" class="avs-res__form" novalidate>
		<div class="avs-res__field">
			<label for="avs-threads"><?php p($l->t('Threads for recognition')); ?></label>
			<input type="number" id="avs-threads" min="1" max="<?php p((string)$standard); ?>" step="1" inputmode="numeric" value="<?php p((string)$threadsValue); ?>" aria-describedby="avs-threads-hint">
			<p id="avs-threads-hint" class="avs-res__hint"><?php p($l->t('Usable CPUs: %1$d. Default and maximum: %2$d. Fewer threads leave more room for Nextcloud, transcription then takes longer.', [$cpus, $standard])); ?></p>
			<p id="avs-threads-error" class="avs-res__error" hidden><span class="avs-res__icon"><?php $icon('error'); ?></span><span><?php p($l->t('Enter a whole number from 1 to %d.', [$standard])); ?></span></p>
		</div>

		<fieldset class="avs-res__window">
			<legend><?php p($l->t('When to compute')); ?></legend>
			<span class="avs-res__choice">
				<input type="radio" class="radio" id="avs-window-always" name="avs-window" value="always"<?php if (!$hasWindow) { ?> checked<?php } ?>>
				<label for="avs-window-always"><?php p($l->t('Always')); ?></label>
			</span>
			<span class="avs-res__choice">
				<input type="radio" class="radio" id="avs-window-set" name="avs-window" value="window"<?php if ($hasWindow) { ?> checked<?php } ?>>
				<label for="avs-window-set"><?php p($l->t('Only within a time window')); ?></label>
			</span>
			<div id="avs-window-fields"<?php if (!$hasWindow) { ?> hidden<?php } ?>>
				<div class="avs-res__times">
					<div class="avs-res__field">
						<label for="avs-window-start"><?php p($l->t('From')); ?></label>
						<input type="time" id="avs-window-start" step="60" value="<?php p($windowStart); ?>" aria-describedby="avs-window-hint">
					</div>
					<div class="avs-res__field">
						<label for="avs-window-end"><?php p($l->t('To')); ?></label>
						<input type="time" id="avs-window-end" step="60" value="<?php p($windowEnd); ?>" aria-describedby="avs-window-hint">
					</div>
				</div>
				<div class="avs-res__field">
					<label for="avs-window-zone"><?php p($l->t('Time zone')); ?></label>
					<select id="avs-window-zone" aria-describedby="avs-window-hint">
						<?php foreach ($zones as $zone) { ?>
							<option value="<?php p((string)$zone); ?>"<?php if ($zone === $windowZone) { ?> selected<?php } ?>><?php p((string)$zone); ?></option>
						<?php } ?>
					</select>
				</div>
				<p id="avs-window-hint" class="avs-res__hint"><?php p($l->t('A window across midnight works, for example 22:00 to 06:00. The window applies to every transcription, previews included. At the end of the window the current piece of about 10 minutes of recording is finished, then the app pauses until the next window. New files are registered outside the window too and transcribed later.')); ?></p>
				<p id="avs-window-error" class="avs-res__error" hidden><span class="avs-res__icon"><?php $icon('error'); ?></span><span data-error="window_same" hidden><?php p($l->t('Start and end must differ.')); ?></span><span data-error="window_time" hidden><?php p($l->t('Enter a time.')); ?></span><span data-error="window_zone" hidden><?php p($l->t('This time zone is unknown. Choose one from the list.')); ?></span></p>
			</div>
			<?php // Only for a stored window; the time is the one of the zone of the window. ?>
			<p id="avs-window-state" class="avs-res__hint"<?php if (!$hasWindow) { ?> hidden<?php } ?>><span data-window="open"<?php if (!$openNow) { ?> hidden<?php } ?>><?php $say($l->t('The time window is open until %s.', [$slot(0)]), [$number('change-at', $changeAt)]); ?></span><span data-window="closed"<?php if ($openNow) { ?> hidden<?php } ?>><?php $say($l->t('The time window is closed and opens at %s.', [$slot(0)]), [$number('change-at', $changeAt)]); ?></span></p>
		</fieldset>

		<div class="avs-admin__actions">
			<?php // Hidden until admin.js runs: without the script nothing could be saved. ?>
			<button type="submit" id="avs-compute-save" class="primary" hidden><?php p($l->t('Save computing time')); ?></button>
			<span id="avs-compute-status" class="avs-admin__status" role="status" data-saved="<?php p($saved); ?>" data-failed="<?php p($notSaved); ?>"></span>
		</div>
	</form>
</div>
<?php } ?>

<?php
// Origin and licence of each model: the licence id is a slot, so the language
// decides where it stands.
$modelOrigins = [
	'parakeet' => [$l->t('By NVIDIA, license %1$s. Converted to int8 by k2-fsa/sherpa-onnx, otherwise unchanged.', [$slot(0)]), [$license('CC-BY-4.0')]],
	'silero' => [$l->t('By the Silero team, license %1$s.', [$slot(0)]), [$license('MIT')]],
	'whisper-turbo' => [$l->t('By OpenAI, license %1$s. CTranslate2 version by deepdml, license %2$s.', [$slot(0), $slot(1)]), [$license('MIT'), $license('MIT')]],
	'whisper-large-v3' => [$l->t('Weights by OpenAI, license %1$s according to the model card. CTranslate2 version by Systran, license %2$s.', [$slot(0), $slot(1)]), [$license('Apache-2.0'), $license('MIT')]],
];
// The eleven states of a model (M1 to M11) with their icon; "not needed" has none.
$modelStates = [
	'in_image' => 'success',
	'present' => 'success',
	'not_needed' => '',
	'waiting' => 'download',
	'downloading' => 'download',
	'verifying' => 'download',
	'wrong_digest_download' => 'error',
	'wrong_digest_placed' => 'error',
	'offline_missing' => 'warning',
	'failed' => 'warning',
	'disk_full' => 'warning',
];
$modelNow = [];
foreach (is_array($resources['models'] ?? null) ? $resources['models'] : [] as $model) {
	if (is_array($model) && is_string($model['id'] ?? null)) {
		$modelNow[$model['id']] = $model;
	}
}
$offline = is_array($resources['offline'] ?? null) ? $resources['offline'] : [];
$offlineForced = ($offline['forcedByEnv'] ?? false) === true;
$offlineOn = $offlineForced || ($offline['value'] ?? false) === true;
?>
<div id="avs-models" class="section avs-admin">
	<h2><?php p($l->t('Models and licenses')); ?></h2>

	<?php if ($resources !== null) { ?>
		<div id="avs-models-stale" class="avs-banner avs-banner--warning avs-res__banner" role="status" hidden>
			<span class="avs-banner__icon"><?php $icon('warning'); ?></span>
			<div class="avs-banner__body">
				<p class="avs-banner__text"><?php p($l->t('The download progress could not be refreshed. Shown is the last known state.')); ?></p>
			</div>
		</div>
	<?php } ?>

	<ul class="avs-models">
		<?php foreach ($modelNames as $id => $modelName) {
			$now = $modelNow[$id] ?? null; ?>
			<li class="avs-models__item">
				<h3 class="avs-admin__subheading" id="avs-model-<?php p($id); ?>-name"><?php p($modelName); ?></h3>
				<p class="avs-res__hint"><?php $say($modelOrigins[$id][0], $modelOrigins[$id][1]); ?></p>
				<?php if ($now !== null) {
					$current = is_string($now['state'] ?? null) && isset($modelStates[$now['state']]) ? $now['state'] : 'failed';
					$doneBytes = is_int($now['doneBytes'] ?? null) ? $now['doneBytes'] : 0;
					$totalBytes = is_int($now['totalBytes'] ?? null) ? $now['totalBytes'] : 1; ?>
					<p class="avs-res__hint"><?php $say($l->t('Size: %s', [$slot(0)]), [$number('size-' . $id, $modelText($id, 'size'))]); ?></p>
					<div class="avs-models__state" data-model="<?php p($id); ?>">
						<?php foreach ($modelStates as $name => $kind) { ?>
							<p class="avs-models__line<?php if ($kind === '') { ?> avs-models__line--muted<?php } ?>" data-state="<?php p($name); ?>"<?php if ($name !== $current) { ?> hidden<?php } ?>><?php if ($kind !== '') { ?><span class="avs-res__icon avs-models__icon--<?php p($kind); ?>"><?php $icon($kind); ?></span><?php } ?><span<?php if ($name === 'downloading') { ?> id="avs-model-<?php p($id); ?>-text"<?php } ?>><?php
								if ($name === 'in_image') {
									p($l->t('Included in the image.'));
								} elseif ($name === 'present') {
									p($l->t('Present, checksum confirmed.'));
								} elseif ($name === 'not_needed') {
									$say($l->t('Not needed for the profile %s, not downloaded.', [$slot(0)]), [$word('effective-name', $effectiveName)]);
								} elseif ($name === 'waiting') {
									p($l->t('Waiting for the download.'));
								} elseif ($name === 'downloading') {
									$say($l->t('Downloading, %1$s of %2$s.', [$slot(0), $slot(1)]), [$number('done-' . $id, $modelText($id, 'done')), $number('size-' . $id, $modelText($id, 'size'))]);
								} elseif ($name === 'verifying') {
									p($l->t('Checking…'));
								} elseif ($name === 'wrong_digest_download') {
									p($l->t('The downloaded file had a wrong checksum and was discarded. Another attempt follows automatically.'));
								} elseif ($name === 'wrong_digest_placed') {
									p($l->t('The placed file has a wrong checksum and is never loaded. Place the correct file, then check it with'));
									?> <code class="avs-admin__command">occ audio_video_search:models --verify</code>.<?php
								} elseif ($name === 'offline_missing') {
									p($l->t('Missing. In offline mode the app downloads nothing, the file has to be placed.'));
								} elseif ($name === 'failed') {
									p($l->t('Download failed. Another attempt follows automatically.'));
								} else {
									$say($l->t('Not enough storage space for the download. %s of free space is needed.', [$slot(0)]), [$number('free-' . $id, $modelText($id, 'free'))]);
								}
							?></span></p>
						<?php } ?>
						<progress class="avs-models__progress" max="<?php p((string)$totalBytes); ?>" value="<?php p((string)min($doneBytes, $totalBytes)); ?>" aria-labelledby="avs-model-<?php p($id); ?>-name" aria-describedby="avs-model-<?php p($id); ?>-text"<?php if ($current !== 'downloading') { ?> hidden<?php } ?>></progress>
					</div>
				<?php } ?>
			</li>
		<?php } ?>
	</ul>

	<?php if ($resources !== null) { ?>
		<?php // Says a change of state only, never every step of a download. ?>
		<span id="avs-models-live" class="hidden-visually" role="status"></span>

		<div class="avs-models__offline">
			<p class="avs-admin__switch">
				<input type="checkbox" id="avs-offline" class="checkbox" aria-describedby="avs-offline-hint<?php if ($offlineForced) { ?> avs-offline-forced<?php } ?>"<?php if ($offlineOn) { ?> checked<?php } ?><?php if ($offlineForced) { ?> disabled<?php } ?>>
				<label for="avs-offline"><?php p($l->t('Offline mode, no connection to the internet')); ?></label>
				<span id="avs-offline-status" class="avs-admin__status" role="status" data-saved="<?php p($saved); ?>" data-failed="<?php p($notSaved); ?>"></span>
			</p>
			<p id="avs-offline-hint" class="settings-hint"><?php p($l->t('The app then downloads no models. Place the Whisper files for the chosen profile yourself, then check them with')); ?> <code class="avs-admin__command">occ audio_video_search:models --verify</code>. <a href="<?php p($readmeOffline); ?>" rel="noreferrer noopener"><?php p($l->t('Guide to offline operation')); ?></a></p>
			<p id="avs-offline-forced" class="settings-hint"<?php if (!$offlineForced) { ?> hidden<?php } ?>><?php p($l->t('Set by the deploy option AVS_OFFLINE. It can only be changed in the deploy options of the backend.')); ?></p>
		</div>
	<?php } ?>

	<h3 class="avs-admin__subheading avs-models__more"><?php p($l->t('Other components')); ?></h3>
	<ul class="avs-models__others">
		<li><?php $say($l->t('FFmpeg for decoding, LGPL build, license %1$s.', [$slot(0)]), [$license('LGPL-2.1-or-later')]); ?></li>
		<li><?php $say($l->t('PyAV ships its own FFmpeg libraries with the codecs libx264 and libx265, license %1$s. The app does not decode with them, they are only in the image as a dependency of faster-whisper.', [$slot(0)]), [$license('GPL-2.0-or-later')]); ?></li>
	</ul>
	<p class="avs-models__all"><a href="<?php p($thirdParty); ?>" rel="noreferrer noopener"><?php p($l->t('All third-party licenses in THIRD-PARTY.md')); ?></a></p>
</div>
