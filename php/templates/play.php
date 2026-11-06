<?php

declare(strict_types=1);

/**
 * The playback page: heading, start line, state banners, the medium, the
 * action row and the excerpt, in this order (UI-SPEC, surface 2).
 *
 * Everything is rendered here with the real values of the request, so the
 * page plays from the time mark with JavaScript switched off: the fragment on
 * the source of the medium does the seek. play.js only adds the jump button,
 * a second seek after the metadata and the mapping of a playback error to one
 * of the banners below; it flips hidden attributes and never builds markup.
 *
 * Every visible string runs through $l->t(), every value somebody else wrote
 * (file name, excerpt, addresses) is printed with p(). No inline script (CSP),
 * no style attribute (theme). The medium never starts on its own.
 *
 * @var array<string,mixed> $_ the parameters of PageController::play()
 * @var \OCP\IL10N $l
 */

// Here and not in the controller: the layout collects its resource lists
// after the template has been rendered.
\OCP\Util::addScript('audio_video_search', 'play');
\OCP\Util::addStyle('audio_video_search', 'play');

// Material Design Icons by Pictogrammers (Apache-2.0), path data only.
$icons = [
	'error' => 'M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z',
	'warning' => 'M12,2L1,21H23M12,6L19.53,19H4.47M11,10V14H13V10M11,16V18H13V16',
	'info' => 'M11,9H13V7H11M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M11,17H13V11H11V17Z',
];

// The parameters, read defensively.
$state = is_string($_['state'] ?? null) ? $_['state'] : 'unavailable';
$fileName = is_string($_['fileName'] ?? null) ? $_['fileName'] : '';
$mediaTag = ($_['mediaTag'] ?? '') === 'audio' ? 'audio' : 'video';
$src = is_string($_['src'] ?? null) ? $_['src'] : '';
$mediaSrc = is_string($_['mediaSrc'] ?? null) ? $_['mediaSrc'] : '';
$startMs = is_int($_['startMs'] ?? null) ? $_['startMs'] : 0;
$startSeconds = is_string($_['startSeconds'] ?? null) ? $_['startSeconds'] : '0.0';
$startClock = is_string($_['startClock'] ?? null) ? $_['startClock'] : '0:00';
$startIso = is_string($_['startIso'] ?? null) ? $_['startIso'] : 'PT0S';
$excerptState = is_string($_['excerptState'] ?? null) ? $_['excerptState'] : 'skipped';
$excerpt = is_string($_['excerpt'] ?? null) ? $_['excerpt'] : '';
$filesUrl = is_string($_['filesUrl'] ?? null) ? $_['filesUrl'] : '';
$downloadAllowed = ($_['downloadAllowed'] ?? false) === true;

$ready = $state === 'ready' && $src !== '';
// A missing file and a forbidden one look the same: no name anywhere.
$heading = $state === 'unavailable' ? $l->t('Playback') : $fileName;

// The start line carries the clock inside a time element. The translated
// sentence is split around a private use character, so the element sits where
// the language puts the placeholder.
$marker = "\u{E000}";
$startParts = explode($marker, $l->t('Starts at %s', [$marker]), 2) + ['', ''];

// Every banner of the state table. The server shows the one that fits its
// own verdict; the ones only the browser can detect (a medium that fails to
// play) are rendered hidden on a ready page and revealed by play.js.
// 'action' is one of: files, reload, download, none.
$banners = [
	'unavailable' => [
		'kind' => 'error',
		'title' => $l->t('This file is not available'),
		'text' => $l->t('It was deleted or moved, or it is no longer shared. A new search shows the current results.'),
		'action' => 'files',
		'actionText' => $l->t('Go to Files'),
		'server' => true,
		'client' => false,
	],
	'not_media' => [
		'kind' => 'info',
		'title' => $l->t('This file is not an audio or video file'),
		'text' => $l->t('This view only plays audio and video.'),
		'action' => 'files',
		'actionText' => $l->t('Show in Files'),
		'server' => true,
		'client' => false,
	],
	'download_blocked' => [
		'kind' => 'info',
		'title' => $l->t('Playback is blocked for this share'),
		'text' => $l->t('This share does not allow downloads, so this instance does not play the file. The person who shared it can allow downloads. The result stays visible in search.'),
		'action' => 'none',
		'actionText' => '',
		'server' => true,
		'client' => true,
	],
	'moved' => [
		'kind' => 'warning',
		'title' => $l->t('The file was moved or renamed in the meantime'),
		'text' => $l->t('Reload to find it at its new location.'),
		'action' => 'reload',
		'actionText' => $l->t('Reload page'),
		'server' => false,
		'client' => true,
	],
	'format' => [
		'kind' => 'error',
		'title' => $l->t('The file cannot be played here'),
		'text' => $l->t('The browser does not support the format, or the file is damaged. Download the file and open it in another program, or try another browser.'),
		'action' => $downloadAllowed ? 'download' : 'none',
		'actionText' => $l->t('Download file'),
		'server' => false,
		'client' => true,
	],
	'network' => [
		'kind' => 'error',
		'title' => $l->t('The connection to the server was lost'),
		'text' => $l->t('Check the connection and reload the page.'),
		'action' => 'reload',
		'actionText' => $l->t('Reload page'),
		'server' => false,
		'client' => true,
	],
	'other' => [
		'kind' => 'error',
		'title' => $l->t('The file could not be loaded'),
		'text' => $l->t('Reload the page. If the error stays, tell the administrators of this instance.'),
		'action' => 'reload',
		'actionText' => $l->t('Reload page'),
		'server' => false,
		'client' => true,
	],
];
?>
<div id="app-content" class="avs-play">
<div class="avs-play__column">

	<div class="avs-play__head">
		<h2 class="avs-play__title"><?php p($heading); ?></h2>
		<?php if ($ready) { ?>
			<p class="avs-play__meta"><?php p($startParts[0]); ?><time class="avs-play__time" datetime="<?php p($startIso); ?>"><?php p($startClock); ?></time><?php p($startParts[1]); ?></p>
		<?php } ?>
	</div>

	<div id="avs-play-state" class="avs-play__state">
		<?php foreach ($banners as $name => $banner) {
			$shown = $banner['server'] && $state === $name;
			if (!$shown && !($ready && $banner['client'])) {
				continue;
			}
			// A banner that replaces the medium is announced and takes the
			// focus; the hint banners the server shows are read in order.
			$alert = $banner['kind'] === 'error' || !$shown;
			?>
			<div id="avs-banner-<?php p($name); ?>" class="avs-banner avs-banner--<?php p($banner['kind']); ?>"<?php if ($alert) { ?> role="alert" tabindex="-1"<?php } ?><?php if (!$shown) { ?> hidden<?php } ?>>
				<span class="avs-banner__icon"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icons[$banner['kind']]); ?>"/></svg></span>
				<div class="avs-banner__body">
					<p class="avs-banner__title"><?php p($banner['title']); ?></p>
					<p class="avs-banner__text"><?php p($banner['text']); ?></p>
					<?php if ($banner['action'] === 'files' && $filesUrl !== '') { ?>
						<a class="avs-banner__action" href="<?php p($filesUrl); ?>"><?php p($banner['actionText']); ?></a>
					<?php } elseif ($banner['action'] === 'reload') { ?>
						<button type="button" class="avs-banner__action avs-reload"><?php p($banner['actionText']); ?></button>
					<?php } elseif ($banner['action'] === 'download') { ?>
						<a class="avs-banner__action" href="<?php p($src); ?>" download><?php p($banner['actionText']); ?></a>
					<?php } ?>
				</div>
			</div>
		<?php } ?>
	</div>

	<?php if ($ready) { ?>
		<<?php p($mediaTag); ?> id="avs-media" class="avs-media avs-media--<?php p($mediaTag); ?>" controls preload="metadata" playsinline src="<?php p($mediaSrc); ?>" data-start="<?php p($startSeconds); ?>" aria-label="<?php p($l->t('Playback: %s', [$fileName])); ?>"></<?php p($mediaTag); ?>>

		<div class="avs-play__actions">
			<?php if ($startMs > 0) { ?>
				<button type="button" id="avs-jump" class="avs-play__jump" hidden><?php p($l->t('Jump to %s', [$startClock])); ?></button>
			<?php } ?>
			<a class="avs-play__files" href="<?php p($filesUrl); ?>"><?php p($l->t('Show in Files')); ?></a>
		</div>

		<section class="avs-excerpt" aria-labelledby="avs-excerpt-label">
			<p id="avs-excerpt-label" class="avs-excerpt__label"><?php p($l->t('Excerpt at this point')); ?></p>
			<?php if ($excerptState === 'ok' && $excerpt !== '') { ?>
				<blockquote class="avs-excerpt__text"><?php p($excerpt); ?></blockquote>
			<?php } elseif ($excerptState === 'none') { ?>
				<p class="avs-excerpt__hint"><?php p($l->t('There is no transcript for this file yet.')); ?></p>
			<?php } else { ?>
				<p class="avs-excerpt__hint"><?php p($l->t('The excerpt cannot be loaded right now. Playback works regardless.')); ?></p>
			<?php } ?>
		</section>
	<?php } ?>

</div>
</div>
