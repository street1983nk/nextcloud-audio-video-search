<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Settings;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Search\Provider;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCA\AudioVideoSearch\Service\ResourceFormat;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\AppFramework\Services\IInitialState;
use OCP\IAppConfig;
use OCP\IConfig;
use OCP\IDateTimeFormatter;
use OCP\IL10N;
use OCP\IUserSession;
use OCP\Settings\ISettings;
use Psr\Log\LoggerInterface;

/**
 * The form of the section: the state of the other half, in debug mode only
 * the switch of the test result (UI-SPEC surface 3), and since plan 05-09
 * profile, computing time and models of the container (05-UI-SPEC).
 *
 * The page is rendered with the real values on the server, so it reads
 * without JavaScript; admin.js only refreshes it in place. The initial state
 * and the template get codes, versions, numbers and booleans and nothing
 * else (T-01-34): every sentence is translated in the template.
 *
 * The container is asked for its resources once per page view. The byte
 * amounts go to the page as numbers (initial state, for admin.js) and as the
 * texts ResourceFormat made of them, so the one rounding rule decides what a
 * lock reads. A silent container is null: the page then says so (R9) and
 * still names origin and licence of every model.
 *
 * The debug block is decided here and not hidden by a script: without
 * 'debug' => true the template never renders it, the route refuses the switch
 * and the provider ignores it (T-01-33).
 */
final class Admin implements ISettings {
	public function __construct(
		private ExAppService $exAppService,
		private IAppConfig $appConfig,
		private IConfig $config,
		private IInitialState $initialState,
		private IUserSession $userSession,
		private IDateTimeFormatter $dateTimeFormatter,
		private LoggerInterface $logger,
		private IL10N $l,
	) {
	}

	public function getForm(): TemplateResponse {
		$state = $this->state();
		$debug = $this->config->getSystemValueBool('debug', false);

		$bootstrap = $state + [
			'debug' => $debug,
			'sampleVisible' => $debug && $this->appConfig->getValueBool(Application::APP_ID, Provider::KEY_SAMPLE_VISIBLE, false),
		];
		$this->initialState->provideInitialState('bootstrap', $bootstrap);

		$resources = $this->resources();
		$this->initialState->provideInitialState('resources', $resources);

		// RENDER_AS_BLANK: the settings page supplies the frame around the form.
		return new TemplateResponse(Application::APP_ID, 'admin', $bootstrap + [
			'checkedAtText' => $this->dateTimeFormatter->formatTime($state['checkedAt'], 'medium'),
			'checkedAtIso' => gmdate('Y-m-d\TH:i:s\Z', $state['checkedAt']),
			'resources' => $resources,
			'resourceText' => $resources === null ? null : $this->resourceText($resources),
		], TemplateResponse::RENDER_AS_BLANK);
	}

	public function getSection(): ?string {
		return Application::APP_ID;
	}

	public function getPriority(): int {
		// The only form of the section so far.
		return 50;
	}

	/**
	 * The state of the other half. backendState answers every failure with a
	 * code of its own; should it throw all the same, the page still renders
	 * and names the backend as unreachable rather than breaking the section.
	 *
	 * @return array{state:string,own:string,backend:?string,companion:?string,sampleCount:?int,checkedAt:int}
	 */
	private function state(): array {
		try {
			return $this->exAppService->backendState($this->userSession->getUser()?->getUID() ?? '');
		} catch (\Throwable $e) {
			$this->logger->error('Audio & Video Search: could not check the backend state for the admin page', ['class' => $e::class]);

			return [
				'state' => ExAppService::STATE_BACKEND_UNREACHABLE,
				'own' => $this->exAppService->ownVersion(),
				'backend' => null,
				'companion' => null,
				'sampleCount' => null,
				'checkedAt' => time(),
			];
		}
	}

	/**
	 * GET /resources of the container in its contract shape, plus the zones
	 * of PHP and the zone the window field starts with (the same rule the
	 * routes of the page use), or null when the container gave no answer.
	 *
	 * @return array<string, mixed>|null
	 */
	private function resources(): ?array {
		try {
			$resources = $this->exAppService->resources();
		} catch (\Throwable $e) {
			$this->logger->error('Audio & Video Search: could not read the resources for the admin page', ['class' => $e::class]);

			return null;
		}
		if ($resources === null) {
			return null;
		}

		return ExAppService::withZones($resources, $this->config, $this->userSession->getUser()?->getUID() ?? '');
	}

	/**
	 * Every byte amount of the page as the text it shows: a need rounded up,
	 * what is available rounded down, sizes and download progress half up
	 * (ResourceFormat). An amount the container does not know reads "unknown".
	 * unit and decimal let admin.js write a number the same way.
	 *
	 * @param array<string, mixed> $resources
	 * @return array<string, mixed>
	 */
	private function resourceText(array $resources): array {
		$unknown = $this->l->t('unknown');
		$need = fn (mixed $bytes): string => is_int($bytes)
			? ResourceFormat::gigabytes($bytes, ResourceFormat::MODE_NEED, $this->l)
			: $unknown;
		$size = fn (mixed $bytes): string => is_int($bytes)
			? ResourceFormat::gigabytes($bytes, ResourceFormat::MODE_SIZE, $this->l)
			: $unknown;

		$available = $resources['availableBytes'] ?? null;
		$needs = [];
		foreach (is_array($resources['profiles'] ?? null) ? $resources['profiles'] : [] as $profile) {
			if (is_array($profile) && is_string($profile['id'] ?? null)) {
				$needs[$profile['id']] = $need($profile['needBytes'] ?? null);
			}
		}
		$models = [];
		foreach (is_array($resources['models'] ?? null) ? $resources['models'] : [] as $model) {
			if (is_array($model) && is_string($model['id'] ?? null)) {
				$models[$model['id']] = [
					'size' => $size($model['totalBytes'] ?? null),
					'done' => $size($model['doneBytes'] ?? null),
					'free' => $need($model['needFreeBytes'] ?? null),
				];
			}
		}

		return [
			'available' => is_int($available)
				? ResourceFormat::gigabytes($available, ResourceFormat::MODE_AVAILABLE, $this->l)
				: $unknown,
			'minimum' => $need($resources['minimumBytes'] ?? null),
			'need' => $needs,
			'models' => $models,
			'unit' => $this->l->t('%s GB', ['%s']),
			'decimal' => str_contains(ResourceFormat::gigabytes(0, ResourceFormat::MODE_SIZE, $this->l), ',') ? ',' : '.',
		];
	}
}
