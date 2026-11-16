<?php

declare(strict_types=1);

/**
 * The playback page: heading, start line, state banners, the medium, the
 * action row, the excerpt and the export section, in this order (UI-SPEC,
 * surface 2; 04-UI-SPEC for the export section and the subtitle track).
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
	// Checked against Templarian/MaterialDesign-SVG on 2026-11-16 (04-UI-SPEC).
	'download' => 'M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z',
	'file-plus' => 'M14 2H6C4.89 2 4 2.89 4 4V20C4 21.11 4.89 22 6 22H13.81C13.28 21.09 13 20.05 13 19C13 15.69 15.69 13 19 13C19.34 13 19.67 13.03 20 13.08V8L14 2M13 9V3.5L18.5 9H13M23 20H20V23H18V20H15V18H18V15H20V18H23V20Z',
	'check-circle-outline' => 'M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2M12 20C7.59 20 4 16.41 4 12S7.59 4 12 4 20 7.59 20 12 16.41 20 12 20M16.59 7.58L10 14.17L7.41 11.59L6 13L10 17L18 9L16.59 7.58Z',
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
// X3: where the share forbids the download, the native player offers none in
// its menu either (owner, UI acceptance 16.11.2026). Fail closed like the
// export: only an explicit false leaves the entry. A hurdle, not a lock: the
// medium still reaches the browser to be played.
$mediaNoDownload = ($_['mediaNoDownload'] ?? true) !== false;

// The export section (04-UI-SPEC, X1 to X4). A state outside the closed list
// is X4, and X1/X2 without all three addresses is X4 as well: no button may
// point nowhere.
$exportState = in_array($_['exportState'] ?? null, ['available', 'partial', 'blocked', 'none'], true) ? $_['exportState'] : 'none';
$exportUntilClock = is_string($_['exportUntilClock'] ?? null) ? $_['exportUntilClock'] : '';
$exportUntilIso = is_string($_['exportUntilIso'] ?? null) ? $_['exportUntilIso'] : '';
$exportUrls = is_array($_['exportUrls'] ?? null) ? $_['exportUrls'] : [];
$sidecarAllowed = ($_['sidecarAllowed'] ?? false) === true;
$sidecarName = is_string($_['sidecarName'] ?? null) ? $_['sidecarName'] : '';
$sidecarUrl = is_string($_['sidecarUrl'] ?? null) ? $_['sidecarUrl'] : '';
$trackUrl = is_string($_['trackUrl'] ?? null) ? $_['trackUrl'] : '';
$trackLang = in_array($_['trackLang'] ?? null, ['de', 'en', 'fr'], true) ? $_['trackLang'] : '';
$trackLabel = is_string($_['trackLabel'] ?? null) ? $_['trackLabel'] : '';

$ready = $state === 'ready' && $src !== '';
// A missing file and a forbidden one look the same: no name anywhere.
$heading = $state === 'unavailable' ? $l->t('Playback') : $fileName;

// The start line carries the clock inside a time element. The translated
// sentence is split around a private use character, so the element sits where
// the language puts the placeholder.
$marker = "\u{E000}";
$startParts = explode($marker, $l->t('Starts at %s', [$marker]), 2) + ['', ''];

// The three formats in their fixed order (D-04-02): SRT, VTT, TXT.
$exportFormats = [
	'srt' => $l->t('Download SRT'),
	'vtt' => $l->t('Download VTT'),
	'txt' => $l->t('Download TXT'),
];
$exportOpen = in_array($exportState, ['available', 'partial'], true);
foreach (array_keys($exportFormats) as $format) {
	if (!is_string($exportUrls[$format] ?? null) || $exportUrls[$format] === '') {
		$exportOpen = false;
	}
}
if (!$exportOpen && $exportState !== 'blocked') {
	$exportState = 'none';
}
// The draft track only on a video, never in X3 (D-04-18), never as default.
$track = $exportOpen && $ready && $mediaTag === 'video' && $trackUrl !== '' && $trackLang !== '' && $trackLabel !== '';
$sidecar = $exportOpen && $sidecarAllowed && $sidecarUrl !== '';

// The sentences that name a file split around the placeholder, like the
// start line: the name sits in a span of its own, which play.js fills with
// the name the server checked.
$untilParts = explode($marker, $l->t('Transcript up to %s, the file is still being processed.', [$marker]), 2) + ['', ''];
$sidecarHint = $sidecarName !== ''
	? explode($marker, $l->t('Saves %s in the same folder as the recording. An existing file is never overwritten.', [$marker]), 2) + ['', '']
	: [$l->t('Saves the subtitles as a VTT file in the same folder as the recording. An existing file is never overwritten.')];
$savedParts = explode($marker, $l->t('%s is now in the same folder as the recording.', [$marker]), 2) + ['', ''];
$notSaved = $l->t('The subtitles were not saved');

// The answers of the sidecar route that are no success (E2 to E7), all
// rendered hidden; play.js shows exactly one of them and focuses it.
$sidecarErrors = [
	'avs-sidecar-e2' => [
		'title' => $l->t('File already exists'),
		'parts' => explode($marker, $l->t('The folder already contains a file named %s. It is not overwritten. To save again, delete or rename the existing file first.', [$marker]), 2) + ['', ''],
	],
	'avs-sidecar-e3' => ['title' => $notSaved, 'parts' => [$l->t('Files cannot be created in this folder. Downloading still works.')]],
	'avs-sidecar-e4' => ['title' => $notSaved, 'parts' => [$l->t('This share does not allow downloads. Subtitles and transcript can therefore neither be downloaded nor saved.')]],
	'avs-sidecar-e5' => ['title' => $notSaved, 'parts' => [$l->t('The name of the subtitle file would be too long. Rename the recording to a shorter name and try again.')]],
	'avs-sidecar-e6' => ['title' => $notSaved, 'parts' => [$l->t('Too many attempts in a short time. Try again a little later.')]],
	'avs-sidecar-e7' => ['title' => $notSaved, 'parts' => [$l->t('The subtitle draft cannot be created right now. Playback works regardless. Try again later.')]],
];

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
		<<?php p($mediaTag); ?> id="avs-media" class="avs-media avs-media--<?php p($mediaTag); ?>" controls<?php if ($mediaNoDownload) { ?> controlslist="nodownload"<?php } ?> preload="metadata" playsinline src="<?php p($mediaSrc); ?>" data-start="<?php p($startSeconds); ?>" aria-label="<?php p($l->t('Playback: %s', [$fileName])); ?>"><?php if ($track) { ?>
			<track kind="subtitles" src="<?php p($trackUrl); ?>" srclang="<?php p($trackLang); ?>" label="<?php p($trackLabel); ?>">
		<?php } ?></<?php p($mediaTag); ?>>

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

		<?php if ($exportState !== 'none') { ?>
			<section class="avs-export" aria-labelledby="avs-export-title">
				<h3 id="avs-export-title" class="avs-export__title"><?php p($l->t('Subtitle draft')); ?></h3>
				<?php if ($exportState === 'blocked') { ?>
					<p class="avs-export__hint"><?php p($l->t('This share does not allow downloads. Subtitles and transcript can therefore neither be downloaded nor saved.')); ?></p>
				<?php } else { ?>
					<p class="avs-export__note"><?php p($l->t('Created automatically and not reviewed. SRT and VTT contain time marks, TXT only the text.')); ?></p>
					<?php if ($exportState === 'partial' && $exportUntilClock !== '') { ?>
						<p class="avs-export__partial"><?php p($untilParts[0]); ?><time class="avs-play__time" datetime="<?php p($exportUntilIso); ?>"><?php p($exportUntilClock); ?></time><?php p($untilParts[1]); ?></p>
					<?php } ?>
					<div class="avs-export__downloads" role="group" aria-labelledby="avs-export-title">
						<?php foreach ($exportFormats as $format => $label) { ?>
							<a class="button avs-export__download" href="<?php p($exportUrls[$format]); ?>"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icons['download']); ?>"/></svg><?php p($label); ?></a>
						<?php } ?>
					</div>
					<div class="avs-export__sidecar">
						<?php if ($sidecar) { ?>
							<?php if (count($sidecarHint) === 2) { ?>
								<p class="avs-export__hint"><?php p($sidecarHint[0]); ?><span class="avs-export__name"><?php p($sidecarName); ?></span><?php p($sidecarHint[1]); ?></p>
							<?php } else { ?>
								<p class="avs-export__hint"><?php p($sidecarHint[0]); ?></p>
							<?php } ?>
							<button type="button" id="avs-sidecar" class="avs-export__save" data-url="<?php p($sidecarUrl); ?>" hidden><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icons['file-plus']); ?>"/></svg><?php p($l->t('Save next to the file')); ?></button>
							<div id="avs-sidecar-result">
								<div id="avs-sidecar-e1" class="avs-banner avs-banner--success" role="status" hidden>
									<span class="avs-banner__icon"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icons['check-circle-outline']); ?>"/></svg></span>
									<div class="avs-banner__body">
										<p class="avs-banner__title"><?php p($savedParts[0]); ?><span class="avs-export__name"><?php p($sidecarName); ?></span><?php p($savedParts[1]); ?></p>
										<?php if ($filesUrl !== '') { ?>
											<a class="avs-banner__action" href="<?php p($filesUrl); ?>"><?php p($l->t('Show in Files')); ?></a>
										<?php } ?>
									</div>
								</div>
								<?php foreach ($sidecarErrors as $id => $error) { ?>
									<div id="<?php p($id); ?>" class="avs-banner avs-banner--error" role="alert" tabindex="-1" hidden>
										<span class="avs-banner__icon"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icons['error']); ?>"/></svg></span>
										<div class="avs-banner__body">
											<p class="avs-banner__title"><?php p($error['title']); ?></p>
											<?php if (count($error['parts']) === 2) { ?>
												<p class="avs-banner__text"><?php p($error['parts'][0]); ?><span class="avs-export__name"><?php p($sidecarName); ?></span><?php p($error['parts'][1]); ?></p>
											<?php } else { ?>
												<p class="avs-banner__text"><?php p($error['parts'][0]); ?></p>
											<?php } ?>
										</div>
									</div>
								<?php } ?>
							</div>
						<?php } else { ?>
							<p class="avs-export__hint"><?php p($l->t('Files cannot be created in this folder. Downloading still works.')); ?></p>
						<?php } ?>
					</div>
				<?php } ?>
			</section>
		<?php } ?>
	<?php } ?>

</div>
</div>
