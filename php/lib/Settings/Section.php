<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Settings;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCP\IL10N;
use OCP\IURLGenerator;
use OCP\Settings\IIconSection;

/**
 * The own admin section "Audio & Video Search" (UI-SPEC surface 3, Findling
 * pattern): later phases add progress, profiles, languages and exclusions
 * here, so the page does not hide under "Additional settings".
 *
 * The Override attribute is absent on purpose: it is enforced from PHP 8.3
 * on, and this app supports PHP 8.2 (Findling finding IN-05).
 */
final class Section implements IIconSection {
	public function __construct(
		private IL10N $l,
		private IURLGenerator $url,
	) {
	}

	public function getID(): string {
		// The address as well: the section renders under
		// /settings/admin/audio_video_search.
		return Application::APP_ID;
	}

	public function getName(): string {
		// The app name stays the same in every language (UI-SPEC copy).
		return $this->l->t('Audio & Video Search');
	}

	public function getPriority(): int {
		// The lower half of the list, where the sections of apps belong.
		return 75;
	}

	public function getIcon(): string {
		// Monochrome, themed by the navigation.
		return $this->url->imagePath(Application::APP_ID, 'app-dark.svg');
	}
}
