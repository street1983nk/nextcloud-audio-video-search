<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Settings;

use OCA\AudioVideoSearch\AppInfo\Application;
use OCA\AudioVideoSearch\Search\Provider;
use OCA\AudioVideoSearch\Service\ExAppService;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\AppFramework\Services\IInitialState;
use OCP\IAppConfig;
use OCP\IConfig;
use OCP\IDateTimeFormatter;
use OCP\IUserSession;
use OCP\Settings\ISettings;
use Psr\Log\LoggerInterface;

/**
 * The form of the section: the state of the other half and, in debug mode
 * only, the switch of the test result (UI-SPEC surface 3).
 *
 * The page is rendered with the real values on the server, so it reads
 * without JavaScript; admin.js only refreshes it in place. The initial state
 * and the template get codes, versions, numbers and booleans and nothing
 * else (T-01-34): every sentence is translated in the template.
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

		// RENDER_AS_BLANK: the settings page supplies the frame around the form.
		return new TemplateResponse(Application::APP_ID, 'admin', $bootstrap + [
			'checkedAtText' => $this->dateTimeFormatter->formatTime($state['checkedAt'], 'medium'),
			'checkedAtIso' => gmdate('Y-m-d\TH:i:s\Z', $state['checkedAt']),
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
			$this->logger->error('Audio & Video Search: could not check the backend state for the admin page', ['exception' => $e]);

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
}
