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
$excerptNote = is_string($_['excerptNote'] ?? null) ? $_['excerptNote'] : '';
$excerptHours = is_int($_['excerptHours'] ?? null) ? $_['excerptHours'] : 0;
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
		'text' => $l->t('It was deleted, moved or is no longer shared.'),
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
		'title' => $l->t('Playback blocked for this share'),
		'text' => $l->t('The person who shared the file can allow downloads.'),
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
		// Without a download there is no button, so the text must not send
		// anybody to download; it names who can lift the block instead.
		'text' => $downloadAllowed
			? $l->t('Download it and open it in another program.')
			: $l->t('This share does not allow downloads. The person who shared the file can allow them.'),
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

// The sentence for each state of the excerpt that names why there is no text
// (UI-SPEC, surface 2, A4 and A6 to A13). Only these fixed keys can show up;
// the controller maps every reason code onto one of its own state names, so
// no value out of the backend reaches the page. 'none' and 'unavailable' keep
// their own branches below, unchanged.
$excerptHints = [
	'pending_here' => $l->t('This point has not been transcribed yet. The file is being transcribed right now.'),
	'no_speech' => $l->t('No speech was found in this file, for example because it only contains music, silence or noise.'),
	'skipped_damaged' => $l->t('This file was not transcribed because it is damaged or incomplete. If it is replaced, transcription starts again automatically.'),
	'skipped_protected' => $l->t('This file was not transcribed because it is protected, for example by copy protection. An unprotected copy is transcribed automatically.'),
	'unsupported_language' => $l->t('The language of this recording is not supported. Transcription covers German, English and French.'),
	'disk_full' => $l->t('This file has not been transcribed yet because there is currently not enough free storage space on the server. Transcription will be retried automatically later.'),
	'skipped_other' => $l->t('This file was not transcribed. The administrators of this instance can see why.'),
];
// Too long names the limit of the instance in whole hours, singular or plural,
// and who can raise it, in one paragraph. Without a limit there is no number
// to name, so the page falls back to the sentence for any other reason.
if ($excerptHours >= 1) {
	$excerptHints['too_long'] = $l->n('This file is longer than %n hour and was therefore not transcribed.', 'This file is longer than %n hours and was therefore not transcribed.', $excerptHours)
		. ' ' . $l->t('The administrators of this instance can raise the limit.');
} else {
	$excerptHints['too_long'] = $excerptHints['skipped_other'];
}
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
				<?php if ($excerptNote === 'partial') { ?>
					<p class="avs-excerpt__note"><?php p($l->t('Preliminary transcript. The file is still being transcribed, later passages will follow.')); ?></p>
				<?php } elseif ($excerptNote === 'preview') { ?>
					<p class="avs-excerpt__note"><?php p($l->t('Preliminary transcript. It may contain errors.')); ?></p>
				<?php } ?>
			<?php } elseif ($excerptState === 'none') { ?>
				<p class="avs-excerpt__hint"><?php p($l->t('There is no transcript for this file yet.')); ?></p>
			<?php } elseif (isset($excerptHints[$excerptState])) { ?>
				<p class="avs-excerpt__hint"><?php p($excerptHints[$excerptState]); ?></p>
			<?php } else { ?>
				<p class="avs-excerpt__hint"><?php p($l->t('The excerpt cannot be loaded right now. Playback works regardless.')); ?></p>
			<?php } ?>
		</section>
	<?php } ?>

</div>
</div>
