<?php

declare(strict_types=1);

/**
 * The error page of the export routes (UI-SPEC D2, O9): one banner in the
 * app frame, never JSON. Title T29, one sentence for the case, the way back
 * to the playback page with the same file id and time mark (T30).
 *
 * The case is one of the closed list of ExportController. Excluded, unknown
 * and not active files all arrive as 'none' and render through the one and
 * the same branch, so those answers stay byte for byte equal (X4 leak rule).
 * A case outside the list falls back to the "right now" sentence and never
 * prints a value of the request.
 *
 * @var array<string,mixed> $_ the parameters of ExportController::errorPage()
 * @var \OCP\IL10N $l
 */

// Here and not in the controller: the layout collects its resource lists
// after the template has been rendered.
\OCP\Util::addStyle('audio_video_search', 'play');

// Material Design Icons by Pictogrammers (Apache-2.0), path data only.
$icon = 'M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z';

// The parameters, read defensively.
$case = is_string($_['case'] ?? null) ? $_['case'] : 'unreachable';
$backUrl = is_string($_['backUrl'] ?? null) ? $_['backUrl'] : '';

$texts = [
	'unavailable' => $l->t('This file is not available'),
	'blocked' => $l->t('This share does not allow downloads. Subtitles and transcript can therefore neither be downloaded nor saved.'),
	'none' => $l->t('There is no transcript for this file yet.'),
	'unreachable' => $l->t('The subtitle draft cannot be created right now. Playback works regardless. Try again later.'),
];
$text = $texts[$case] ?? $texts['unreachable'];
?>
<div id="app-content" class="avs-play">
<div class="avs-play__column">

	<div class="avs-play__state">
		<div class="avs-banner avs-banner--error" role="alert" tabindex="-1">
			<span class="avs-banner__icon"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($icon); ?>"/></svg></span>
			<div class="avs-banner__body">
				<p class="avs-banner__title"><?php p($l->t('The subtitle draft could not be created')); ?></p>
				<p class="avs-banner__text"><?php p($text); ?></p>
				<?php if ($backUrl !== '') { ?>
					<a class="avs-banner__action" href="<?php p($backUrl); ?>"><?php p($l->t('Back to playback')); ?></a>
				<?php } ?>
			</div>
		</div>
	</div>

</div>
</div>
