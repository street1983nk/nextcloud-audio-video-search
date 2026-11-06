# Phase 1: Zwei-App-Gerüst und Integrationsbeweis - Pattern Map

**Mapped:** 2026-11-06
**Files analyzed:** 47 (neu oder geändert, zusammengefasst in 39 Zeilen)
**Analogs found:** 33 / 39

Quellen der Analoga:
- Findling: `C:/Users/Student/nextcloud-search` (im Folgenden `F:`), Stand 1.6.2
- Dieses Repo: `C:/Users/Student/nextcloud-audio-video-search` (im Folgenden `R:`), aus dem Skeleton erzeugt

Grundregel für den Planer: Findling-Code wird **kopiert und umbenannt** (`OCA\Findling` nach `OCA\AudioVideoSearch`, `findling` nach `audio_video_search`, `findling_backend` nach `audio_video_search_backend`, Präfix `findling-` nach `avs-`), nie importiert. Die langen Findling-Docblocks nicht 1:1 mitnehmen, nur die tragenden Begründungen.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `php/appinfo/info.xml` | config | n. a. | `F:/php/appinfo/info.xml` (Z. 278-345) | exact |
| `php/appinfo/routes.php` | config | n. a. | `F:/php/appinfo/routes.php` | exact (Kopie) |
| `php/lib/AppInfo/Application.php` | provider (Bootstrap) | event-driven | `F:/php/lib/AppInfo/Application.php` | exact |
| `php/lib/Search/Provider.php` | service (Search Provider) | request-response | `F:/php/lib/Search/Provider.php` | exact, erweitert um Zeitmarke |
| `php/lib/Service/ExAppService.php` | service | request-response | `F:/php/lib/Service/ExAppService.php` | exact, erweitert um `backendState()` |
| `php/lib/Service/ReaderContext.php` | utility | n. a. | `F:/php/lib/Service/ReaderContext.php` | exact (Kopie) |
| `php/lib/Service/FileAccess.php` (oder statische Methode) | utility | request-response | `F:/php/lib/Service/SearchService.php` Z. 723-742 | exact |
| `php/lib/Controller/PageController.php` (`play`) | controller | request-response | `F:/php/lib/Controller/PageController.php` Z. 182-303 | role-match |
| `php/lib/Controller/GatewayController.php` | controller | streaming (file-I/O) | `F:/php/lib/Controller/GatewayController.php` | exact (Kopie) |
| `php/lib/Controller/HandshakeController.php` | controller | request-response | `F:/php/lib/Controller/GatewayController.php` (Attribute, `rejectForeignCaller`) | role-match |
| `php/lib/Controller/SettingsController.php` (Neuprüfung, Debug-Schalter) | controller | request-response | `F:/php/lib/Controller/SettingsController.php` Z. 148-160, 507-535 | exact |
| `php/lib/Settings/Admin.php` | provider (ISettings) | request-response | `F:/php/lib/Settings/Admin.php` | exact |
| `php/lib/Settings/Section.php` | provider (IIconSection) | n. a. | `F:/php/lib/Settings/Section.php` | exact (Kopie) |
| `php/lib/Command/SampleCommand.php` | command (occ) | request-response | `F:/php/lib/Command/PauseCommand.php` | role-match |
| `php/templates/play.php` | component (Template) | request-response | `F:/php/templates/search.php` Z. 39-40, 213-221 + `F:/php/templates/admin.php` Z. 439-464 | role-match |
| `php/templates/admin.php` | component (Template) | request-response | `F:/php/templates/admin.php` Z. 1-40, 340-464 | exact |
| `php/js/play.js` | component (Browser-JS) | event-driven | RESEARCH Pattern 4 + Struktur `F:/php/js/admin.js` Z. 1-30 | partial |
| `php/js/admin.js` | component (Browser-JS) | request-response | `F:/php/js/admin.js` Z. 234-281, 1883-1911 | exact |
| `php/css/play.css`, `php/css/admin.css` | config (Stil) | n. a. | `F:/php/css/admin.css` Z. 57-123 | exact |
| `php/l10n/{de,de_DE,en,fr}.{json,js}` | config (Katalog) | n. a. | `F:/php/l10n/de.js` + `R:/scripts/l10n_js.py` | exact |
| `php/img/app.svg`, `php/img/app-dark.svg` | asset | n. a. | `R:/img/app.svg`, `R:/img/app-dark.svg` | exact (verschieben) |
| `php/composer.json`, `php/phpunit.xml`, `php/tests/bootstrap.php` | config/test | n. a. | `F:/php/composer.json`, `F:/php/phpunit.xml`, `F:/php/tests/bootstrap.php` | exact |
| `php/tests/Unit/{Provider,ExAppService,PageController,GatewayController,HandshakeController,SampleCommand}Test.php` | test | n. a. | `F:/php/tests/Unit/ProviderTest.php`, `ExAppServiceTest.php` Z. 228-257 | exact |
| `backend/appinfo/info.xml` | config | n. a. | `R:/appinfo/info.xml` (verschieben) + `F:/backend/appinfo/info.xml` | exact |
| `backend/src/audio_video_search_backend/{__init__,main,config,logs,nc,settings}.py` | service (FastAPI) | request-response | `R:/src/audio_video_search/*.py` (verschieben, umbenennen) | exact |
| `backend/src/.../api/status.py` | controller (Route) | request-response | `R:/src/audio_video_search/main.py` Z. 108-111 + `F:/backend/src/findling/api/status.py` Z. 340-350, 596-602 | exact |
| `backend/src/.../api/search.py` | controller (Route) | request-response | `F:/backend/src/findling/api/search.py` | role-match |
| `backend/src/.../api/sample.py` | controller (Route) | file-I/O + CRUD | `F:/backend/src/findling/nc/client.py` Z. 363-406 | partial |
| `backend/src/.../nc/client.py` (Gateway-Stream, Handshake) | service (Client) | streaming | `F:/backend/src/findling/nc/client.py` Z. 118, 363-406, 576-580 | exact |
| `backend/src/.../store/schema.sql` | migration | CRUD | `F:/backend/src/findling/store/schema.sql` Z. 1-40 | role-match (Tabellen neu) |
| `backend/src/.../store/repo.py` | service (Repository) | CRUD | `F:/backend/src/findling/store/repo.py` Z. 732-795, 957-966 | exact |
| `backend/src/.../model/provenance.py` | model (reine Funktion) | transform | keins | none |
| `backend/src/.../model/overlay.py` | model (reine Funktion) | transform | keins | none |
| `backend/src/.../index/{analyzer,schema,open}.py` | service (Index) | CRUD | `F:/backend/src/findling/index/analyzer.py`, `schema.py`, `open.py` | exact (Kopie, DE/EN/FR) |
| `backend/src/.../index/publish.py` | service (Index) | batch | `F:/backend/src/findling/index/writer.py` Z. 205, 330, 418, 486 | role-match |
| `backend/tests/test_lockstep_versions.py` | test | n. a. | `F:/backend/tests/test_lockstep_versions.py` | exact (Kopie) |
| `backend/tests/{test_index_open,test_index_publish,test_store_schema,test_provenance,test_corrections,test_handshake}.py` | test | n. a. | `F:/backend/tests/test_index_open.py` Z. 582-600; Rest ohne Analog | partial |
| `backend/tests/test_trilingual.py`, `test_workflows.py` (erweitern) | test | n. a. | `R:/tests/test_trilingual.py`, `R:/tests/test_workflows.py` | exact |
| `.github/workflows/php.yml` (neu) | config (CI) | batch | `F:/.github/workflows/php.yml` Z. 268-402 | exact |
| `.github/workflows/deploy-harp.yml` (erweitern) | config (CI) | batch | `R:/.github/workflows/deploy-harp.yml` + `F:/.github/workflows/deploy-harp.yml` Z. 286-336, 2003-2066, 2169-2205 | exact |
| `.github/workflows/{python,docker,release}.yml`, `scripts/release/store-archive.sh` | config (CI/Release) | batch | `R:` dieselben Dateien + `F:/scripts/release/store-archive.sh` Z. 72-117 | exact |
| `ci/playwright/play.spec.ts`, `ci/playwright/package.json` | test (e2e) | n. a. | keins | none |
| `testdata/tone-90s.webm`, `testdata/tone-90s.ogg` | fixture | n. a. | keins | none |
| `DESIGN.md`, `PRODUCT.md` (TODO(skeleton) füllen) | doc | n. a. | `R:/DESIGN.md`, `R:/PRODUCT.md` | exact |

---

## Pattern Assignments

### `php/appinfo/info.xml` (config)

**Analog:** `C:/Users/Student/nextcloud-search/php/appinfo/info.xml`

Pflichtteile (Findling Z. 179, 278-281, 321, 345), auf eine Zeile wie Findling:
```xml
<version>0.1.0</version>
<dependencies>
	<php min-version="8.2"/>
	<nextcloud min-version="33" max-version="35"/>
</dependencies>
<commands><command>OCA\AudioVideoSearch\Command\SampleCommand</command></commands>
<settings><admin>OCA\AudioVideoSearch\Settings\Admin</admin><admin-section>OCA\AudioVideoSearch\Settings\Section</admin-section></settings>
```
- Kein `<navigations>`-Block (UI-SPEC: kein Navigationseintrag in Phase 1), kein `<repair-steps>`.
- `<version>` muss gleich `backend/appinfo/info.xml` `<version>` und `<image-tag>` sein (Lockstep-Gate).
- name/summary/description in en, `lang="de"`, `lang="fr"` (Muster `R:/appinfo/info.xml` Z. 22-48; `test_trilingual.py` prüft das).

### `php/appinfo/routes.php` (config)

**Analog:** `C:/Users/Student/nextcloud-search/php/appinfo/routes.php` (Z. 11-14), 1:1:
```php
return [
	'routes' => [],
	'ocs' => [],
];
```
Alle Routen per Attribut am Controller.

### `php/lib/AppInfo/Application.php` (Bootstrap, event-driven)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/AppInfo/Application.php`

Konstanten und Registrierung (Z. 19-31, 54-55, 138-139), ohne Event-Listener (Discovery kommt in Phase 2):
```php
class Application extends App implements IBootstrap {
	public const APP_ID = 'findling';
	public const BACKEND_APP_ID = 'findling_backend';

	public function __construct(array $urlParams = []) {
		parent::__construct(self::APP_ID, $urlParams);
	}

	public function register(IRegistrationContext $context): void {
		$context->registerSearchProvider(Provider::class);
	}

	public function boot(IBootContext $context): void {
	}
}
```
Wichtig (Findling-Kommentar Z. 33-37): Provider-Registrierung nur in `register()`, in `boot()` scheitert sie still.

### `php/lib/Search/Provider.php` (Search Provider, request-response)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/Search/Provider.php`

**Imports** (Z. 7-20, reduziert):
```php
use OCA\AudioVideoSearch\Service\ExAppService;
use OCP\IL10N;
use OCP\IURLGenerator;
use OCP\IUser;
use OCP\Search\IFilteringProvider;
use OCP\Search\ISearchQuery;
use OCP\Search\SearchResult;
use OCP\Search\SearchResultEntry;
use Psr\Log\LoggerInterface;
```

**Budget und Kennung** (Z. 64, 133-151):
```php
private const BUDGET_SECONDS = 2.5;

#[\Override]
public function getId(): string { return 'findling'; }

#[\Override]
public function getName(): string { return $this->l10n->t('File contents'); }

#[\Override]
public function getOrder(string $route, array $routeParameters): ?int {
	return str_starts_with($route, 'files.') ? -5 : 25;
}
```
Anpassen: ID `audio_video_search`, Name `$this->l10n->t('Audio and video')`. `getOrder` nie `null` (blendet Provider aus).

**Leerer Begriff und leeres Ergebnis** (Z. 246-253, 287-305):
```php
$term = trim($query->getTerm());
if ($term === '') {
	return SearchResult::complete($this->getName(), []);
}
...
if ($outcome->hits === []) {
	if ($outcome->failure !== null) {
		$this->logger->debug('Findling: the shared search returned no hits', ['reason' => $outcome->failure]);
	}
	return SearchResult::complete($this->getName(), []);
}
```

**Eintrag bauen** (Z. 536-563), zu erweitern nach RESEARCH "Treffer-Eintrag" und UI-SPEC Fläche 1:
```php
$entry = new SearchResultEntry(
	thumbnailUrl: '',
	title: $hit->title,
	subline: $excerpt === null ? $hit->path : $excerpt['text'],
	resourceUrl: $this->resourceUrl($fileId),
	icon: 'icon-search',
);
$entry->addAttribute('fileId', (string)$fileId);
```
Änderungen: `subline` = `clock($startMs) . ' · ' . $ausschnitt` (bei Debug-Treffer `' · ' . $l->t('Test result') . ' · '` dazwischen), `resourceUrl` = `linkToRouteAbsolute('audio_video_search.page.play', ['fileId' => $id, 't' => sprintf('%.1f', $t)])`, `thumbnailUrl` = `IMimeTypeDetector::mimeTypeIcon($mime)` (Muster `F:/php/lib/Controller/PageController.php` Z. 795), zusätzlich `addAttribute('path', $relPath)`, nie `fileId` ohne `path`. Titel und Pfad immer aus dem geprüften Node, nie aus der Containerantwort (`F:/php/lib/Service/SearchService.php` Z. 744-768).

`getSupportedFilters()` in Phase 1 nur `[IFilter::BUILTIN_TERM]`; `getAlternateIds()` und `getCustomFilters()` leer (Findling Z. 182-245 als Gerüst).

### `php/lib/Service/ExAppService.php` (service, request-response)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/Service/ExAppService.php`

**Konstruktor und Konstanten** (Z. 95, 236-238, 256, 269-277):
```php
public const REQUEST_TIMEOUT_SECONDS = 1.5;
public const LOCKSTEP_MATCH = 'match';
public const LOCKSTEP_DRIFT = 'drift';
public const LOCKSTEP_UNKNOWN = 'unknown';
public const KEY_BACKEND_VERSION = 'backend_app_version';
private const VERSION_PATTERN = '/^\d{1,5}\.\d{1,5}(?:\.[0-9A-Za-z][0-9A-Za-z.-]{0,19})?$/D';

public function __construct(
	private IAppManager $appManager,
	private IUserManager $userManager,
	private IAppConfig $appConfig,
	private LoggerInterface $logger,
) {
}
```

**Lockstep** (Z. 303-325, 362-388) übernehmen: `lockstep()`, `ownVersion()`, `versionOrNothing()`, `majorMinor()`, `rememberBackendVersion()` (Z. 398-404), `driftOnRecord()` (Z. 338-352).

**Pre-flight AppAPI** (Z. 909-929), Kern der neuen `backendState()`:
```php
private function publicFunctions(string $userId): ?\OCA\AppAPI\PublicFunctions {
	$user = $this->userManager->get($userId);
	if ($user === null) { ...; return null; }
	if (!$this->appManager->isEnabledForUser('app_api', $user)) { ...; return null; }
	try {
		return \OCP\Server::get(\OCA\AppAPI\PublicFunctions::class);
	} catch (ContainerExceptionInterface|NotFoundExceptionInterface) {
		...; return null;
	}
}
```

**Testnaht** (Z. 882-896): `proxyRequest()` ist `protected`, damit der Test sie mockt:
```php
protected function proxyRequest(string $path, string $userId, string $method, array $params, float $timeout): array|IResponse|null {
	$appApi = $this->publicFunctions($userId);
	if ($appApi === null) { return null; }
	return $appApi->exAppRequest(Application::BACKEND_APP_ID, $path, $userId, $method, $params, ['timeout' => $timeout]);
}
```
Für `getExApp()` dieselbe Naht anlegen (z. B. `protected function exAppInfo(string $uid): ?array`), damit die fünf Zustände ohne AppAPI testbar sind.

**Vier stille Fehlerfälle** (Z. 954-1047): `is_array($response)` = unerreichbar, `getStatusCode() >= 400`, Body nicht String oder `> MAX_BODY_BYTES`, `json_decode` kein Array. Jeweils `warning` mit `path`, `status`, `innerMs`, nie Inhalt. 1:1 übernehmen.

**Neu:** `backendState(string $uid): array` nach RESEARCH Pattern 1 mit den Zuständen `no_app_api`, `backend_missing`, `backend_disabled`, `version_drift`, `backend_unreachable`, `version_patch_differs`, `ok`.

### `php/lib/Service/ReaderContext.php` (utility)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/Service/ReaderContext.php`, Kopie (Z. 58-90). Kern:
```php
public function actAs(string $uid, \Closure $work): mixed {
	$previous = $this->userSession->getUser();
	if ($previous !== null && $previous->getUID() === $uid) { return $work(); }
	$member = $this->userManager->get($uid);
	if ($member === null) { return $work(); }
	$this->userSession->setVolatileActiveUser($member);
	try { return $work(); } finally { $this->userSession->setVolatileActiveUser($previous); }
}
```

### Lesbarkeitsprüfung (`readableFile`)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/Service/SearchService.php` Z. 723-742:
```php
public static function readableFile(Folder $userFolder, int $fileId): ?File {
	return self::readableNode($userFolder->getFirstNodeById($fileId));
}
public static function readableNode(?Node $node): ?File {
	if (!$node instanceof File) { return null; }
	return $node->isReadable() ? $node : null;
}
```
Genau eine Stelle stellt diese Frage (Provider, PageController und Gateway rufen sie). Relativer Pfad wie `F:/php/lib/Service/SearchService.php` Z. 768: `ltrim((string)$userFolder->getRelativePath($node->getPath()), '/')`.

### `php/lib/Controller/PageController.php` (`play`, request-response)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/Controller/PageController.php`

**Konstruktor** (Z. 182-193), reduziert auf `IRequest`, `IRootFolder`, `IUserSession`, `IMimeTypeDetector`, `IURLGenerator`, `ExAppService`, `LoggerInterface`, `ReaderContext`.

**Attribute und Antwort** (Z. 217-220, 262-302):
```php
#[\OCP\AppFramework\Http\Attribute\NoAdminRequired]
#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'GET', url: '/')]
public function index(): TemplateResponse {
	...
	return new TemplateResponse(Application::APP_ID, 'search', [ ... ], TemplateResponse::RENDER_AS_USER);
}
```
Anpassen: `url: '/play/{fileId}', requirements: ['fileId' => '\d+']` (Requirement-Begründung `F:/php/lib/Controller/GatewayController.php` Z. 53-63), Methode `play(int $fileId)`, `t` per `$this->request->getParam('t', '')` lesen und still auf 0 fallen lassen (Findling-Regel Z. 204-215: jede Adressangabe fällt still zurück). Nicht verfügbar: `$response->setStatus(Http::STATUS_NOT_FOUND)` auf derselben TemplateResponse, ohne Dateinamen. DAV-Adresse nach RESEARCH "DAV-Adresse aus fileId" (`rawurlencode` je Segment und für die UID). Kein `#[PublicPage]`.

### `php/lib/Controller/GatewayController.php` (streaming)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/Controller/GatewayController.php`, Kopie.

**Routenattribute** (Z. 61-64):
```php
#[\OCP\AppFramework\Http\Attribute\ExAppRequired]
#[\OCP\AppFramework\Http\Attribute\NoCSRFRequired]
#[\OCP\AppFramework\Http\Attribute\ApiRoute(verb: 'GET', url: '/files/{fileId}', requirements: ['fileId' => '\d+'])]
public function getFileContents(int $fileId, string $userId): DataResponse|StreamResponse {
	$foreign = $this->rejectForeignCaller();
	if ($foreign !== null) { return $foreign; }
```
**Fehlerbehandlung** (Z. 90-145): 404 für "nicht sichtbar/nicht lesbar/nicht vorhanden/unbekannter Nutzer" wortgleich, 422 bei `fopen` fehlgeschlagen, 500 mit statischem Satz und `['exception' => $e]`, nie Pfad. `fopen('r')`, nie anderes Mode.

### `php/lib/Controller/HandshakeController.php` (request-response)

**Analog:** `GatewayController` (oben), Z. 27-35 und 170-182:
```php
private function rejectForeignCaller(): ?DataResponse {
	$callerAppId = $this->request->getHeader('EX-APP-ID');
	if ($callerAppId === Application::BACKEND_APP_ID) { return null; }
	$this->logger->warning('Findling: content gateway called by a foreign ExApp', ['app' => $callerAppId]);
	return new DataResponse(['error' => 'This route is reserved for the Findling backend.'], Http::STATUS_FORBIDDEN);
}
```
Route: `ApiRoute(verb: 'GET', url: '/api/v1/handshake')` mit `ExAppRequired` + `NoCSRFRequired`, erste Anweisung `rejectForeignCaller()`. Antwort `DataResponse(['companionVersion' => ...])` aus `IAppManager::getAppVersion`. `rejectForeignCaller` in beiden Controllern gleich geformt (Findling-Gate liest die erste Anweisung jeder Route).

### `php/lib/Controller/SettingsController.php` (Admin, request-response)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/Controller/SettingsController.php`

**Lesende Admin-Route** (Z. 148-160), ohne Attribute = nur Admin mit Request-Token:
```php
#[\OCP\AppFramework\Http\Attribute\FrontpageRoute(verb: 'GET', url: '/admin/overview')]
public function overview(): DataResponse {
	try {
		return new DataResponse($this->view->overview());
	} catch (\Throwable $e) {
		$this->logger->error('Findling: could not assemble the admin overview', ['exception' => $e]);
		return new DataResponse(['error' => 'Status is not available.'], Http::STATUS_INTERNAL_SERVER_ERROR);
	}
}
```
Für "Erneut prüfen": `GET /admin/state` liefert `backendState()` + Versionen + Zeitpunkt.

**Schreibender Schalter** (Z. 507-535), Vorbild für den Debug-Schalter `POST /admin/sample`:
```php
public function setPause(mixed $paused = null): DataResponse {
	$wish = match (true) {
		$paused === true, $paused === 'true' => true,
		$paused === false, $paused === 'false' => false,
		default => null,
	};
	if ($wish === null) { ...; return new DataResponse(['error' => 'paused must be a boolean'], Http::STATUS_BAD_REQUEST); }
	try { $this->settingsService->setPaused($wish); } catch (\Throwable $e) { ...; return new DataResponse([...], Http::STATUS_INTERNAL_SERVER_ERROR); }
	return new DataResponse(['paused' => $wish]);
}
```
Zusatz für Phase 1: ohne `config.php` `debug => true` Antwort 403/404, Schalter wirkungslos (UI-SPEC "serverseitig, nicht nur ausgeblendet"). Nutzer-ID der Sitzung wie Z. 590-592.

### `php/lib/Settings/Admin.php` und `Section.php` (provider)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/Settings/Admin.php` Z. 44-79 und `Section.php` Z. 36-67.

```php
public function getForm(): TemplateResponse {
	$overview = $this->view->overview();
	$this->initialState->provideInitialState('bootstrap', $overview);
	return new TemplateResponse(Application::APP_ID, 'admin', $overview, TemplateResponse::RENDER_AS_BLANK);
}
public function getSection(): ?string { return Application::APP_ID; }
public function getPriority(): int { return 50; }
```
Section: `IIconSection`, `getID()` = APP_ID, `getName()` = `$this->l->t('Audio & Video Search')`, `getPriority()` = 75, `getIcon()` = `imagePath(APP_ID, 'app-dark.svg')`. Kein `#[\Override]` (PHP 8.2-Boden, Begründung Section Z. 21-34). Initial-State nur Zahlen, Booleans, Codes, keine Prosa (Admin Z. 26-29).

### `php/lib/Command/SampleCommand.php` (occ)

**Analog:** `C:/Users/Student/nextcloud-search/php/lib/Command/PauseCommand.php` Z. 44-109:
```php
class PauseCommand extends Command {
	public function __construct(private SettingsService $settingsService, private ExAppService $exAppService, ...) {
		parent::__construct();
	}
	protected function configure(): void {
		$this->setName('findling:pause')->setDescription('...')->addOption('wait', null, InputOption::VALUE_OPTIONAL, '...', false);
	}
	protected function execute(InputInterface $input, OutputInterface $output): int {
		if (...) { $output->writeln('<error>...</error>'); return Command::INVALID; }
		...
	}
}
```
Name muss mit UI-SPEC übereinstimmen (`audio_video_search:sample`, Argument `fileId`). Ohne `debug` = `Command::FAILURE` mit klarer Zeile. Identität des Containeraufrufs: erster aktiver Admin (Begründung PauseCommand Z. 36-39, `IGroupManager`, Gruppe `admin`). In `info.xml` unter `<commands>` eintragen.

### `php/templates/play.php` (Template)

**Analog:** `C:/Users/Student/nextcloud-search/php/templates/search.php` Z. 39-40 und 213-221; Banner aus `admin.php` Z. 444-457.

```php
\OCP\Util::addScript('findling', 'search');
\OCP\Util::addStyle('findling', 'search');
?>
<div id="app-content">
<div class="findling-search">
```
Banner-Markup:
```php
<p class="findling-banner findling-banner--<?php p($banner['kind']); ?>" id="<?php p($banner['id']); ?>"<?php if (!$banner['shown']) { ?> hidden<?php } ?>>
	<svg class="findling-banner__icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false"><path fill="currentColor" d="<?php p($banner['icon']); ?>"/></svg>
	<span class="findling-banner__text" id="<?php p($banner['id']); ?>-text"><?php p($banner['text']); ?></span>
</p>
```
Anpassen an UI-SPEC: Wurzel `<div id="app-content" class="avs-play">`, `div` statt `p` für Banner mit Titel (700) + Satz, Icon 20 px in eigenem Flex-Container, `role="alert"` + `tabindex="-1"` bei Fehlern. Alle Fehler-Banner serverseitig rendern und mit `hidden` verbergen, JS schaltet nur das Attribut (Findling admin.php Z. 341-344). Jede Fremdangabe mit `p()`. Keine Inline-Skripte, kein `style`-Attribut.

### `php/templates/admin.php` (Template)

**Analog:** `C:/Users/Student/nextcloud-search/php/templates/admin.php` Z. 1-40 (Kopf, `addScript`/`addStyle` im Template, `IDateTimeFormatter` per `\OCP\Server::get`), Z. 345-416 (Banner-Array mit `id`, `kind`, `icon`, `text`, `shown`), Z. 439-464 (Ausgabe in `div.section` mit `h2`).

Version-Drift-Satz als Vorbild (Z. 360-364):
```php
'text' => $l->t('The two halves of Findling report different versions: this app is %1$s, the backend is %2$s. ...', [$companionVersion, $containerVersion]),
'shown' => $lockstepState === 'drift',
```
Für Phase 1: genau ein Zustands-Banner je Zustand (sieben Einträge, nur einer `shown`), Container `id="avs-backend-state" role="status" aria-live="polite" tabindex="-1"`. Debug-Block nur rendern, wenn `debug` an ist.

### `php/js/play.js` (Browser-JS, event-driven)

**Analog:** RESEARCH Pattern 4 (Code steht dort) plus Rahmen aus `C:/Users/Student/nextcloud-search/php/js/admin.js` Z. 25-27:
```js
'use strict'

;(function () {
  ...
})()
```
Fehlerzuordnung per `fetch(src, { method: 'HEAD', credentials: 'same-origin' })` (UI-SPEC Interaktion). Nur Textknoten und `hidden` setzen, nie Markup bauen (admin.js Z. 1-18, 283-290).

### `php/js/admin.js` (Browser-JS, request-response)

**Analog:** `C:/Users/Student/nextcloud-search/php/js/admin.js`

Lesen (Z. 234-250):
```js
async function ask (path, params, signal) {
  const query = params ? '?' + new URLSearchParams(params).toString() : ''
  const url = OC.generateUrl('/apps/findling/' + path) + query
  const response = await fetch(url, {
    signal: signal,
    headers: { requesttoken: document.head.dataset.requesttoken, Accept: 'application/json' }
  })
  if (!response.ok) { throw new Error('findling: ' + response.status) }
  return response.json()
}
```
Schreiben (Z. 269-281) mit `method: 'POST'`, JSON-Body, Token jedes Mal frisch aus `document.head.dataset.requesttoken`.
Schalter (Z. 1883-1900): `toggle.disabled = true` vor dem Senden, `finally` wieder frei. Für Phase 1 ergänzen: bei Fehler Checkbox zurücksetzen, Status "Gespeichert" 3 s, `aria-busy` am Statuscontainer während "Erneut prüfen", danach Fokus auf `#avs-backend-state`.

### `php/css/play.css`, `php/css/admin.css` (Stil)

**Analog:** `C:/Users/Student/nextcloud-search/php/css/admin.css` Z. 57-123:
```css
.findling-banner {
	display: flex;
	align-items: flex-start;
	gap: calc(var(--default-grid-baseline) * 2);
	margin-block: calc(var(--default-grid-baseline) * 2);
	padding: calc(var(--default-grid-baseline) * 4);
	border-radius: var(--border-radius-container);
}
.findling-banner--error { background-color: var(--color-error); color: var(--color-error-text); }
.findling-banner--warning { background-color: var(--color-warning); color: var(--color-warning-text); }
.findling-banner--info { background-color: var(--color-info); color: var(--color-info-text); }
.findling-banner__text { overflow-wrap: anywhere; }
```
Ergänzen: `--success`-Paar, Icon-Farben `--color-element-*` (UI-SPEC Statuspaare), Icon-Container mit `height: var(--default-line-height)` statt `margin-block-start`, Medium `width: 100%; max-height: 70vh; object-fit: contain`, `@media (pointer: coarse)` 44 px. Banner-Link (Z. 108-123) für "Apps öffnen" übernehmen. Nur Server-Variablen, kein `!important`, kein `outline: none`.

### `php/l10n/*` (Kataloge)

**Analog:** `C:/Users/Student/nextcloud-search/php/l10n/de.js` (Form `OC.L10N.register("findling", { "English": "Deutsch", ... })`) und Generator `C:/Users/Student/nextcloud-audio-video-search/scripts/l10n_js.py` (`.js` aus `.json`). `de` und `de_DE` mit identischem Text (Findling hat beide Dateien). Schlüssel = englischer Quelltext.

### `php/composer.json`, `php/phpunit.xml`, `php/tests/bootstrap.php`

**Analog:** `C:/Users/Student/nextcloud-search/php/composer.json` Z. 12-26:
```json
"require": { "php": ">=8.2" },
"require-dev": { "phpunit/phpunit": "11.5.57" },
"autoload": { "psr-4": { "OCA\\Findling\\": "lib/" } },
"autoload-dev": { "psr-4": { "OCA\\Findling\\Tests\\": "tests/" } }
```
`bootstrap.php` Z. 39-93 kopieren (Server-Bootstrap zuerst, dann `vendor/autoload.php`, klare Meldung bei fehlendem `NEXTCLOUD_SERVER_ROOT`), Pfad `apps/audio_video_search`. `composer.lock` per CI erzeugen (lokal kein PHP).

### `php/tests/Unit/*Test.php` (test)

**Analog:** `C:/Users/Student/nextcloud-search/php/tests/Unit/ProviderTest.php` Z. 1-23 (Imports, `CoversClass`, `MockObject`) und `ExAppServiceTest.php` Z. 235-257:
```php
private function service(?LoggerInterface $logger = null): ExAppService&MockObject {
	return $this->getMockBuilder(ExAppService::class)
		->setConstructorArgs([
			$this->createMock(IAppManager::class),
			$this->createMock(IUserManager::class),
			$this->createMock(IAppConfig::class),
			$logger ?? $this->createMock(LoggerInterface::class),
		])
		->onlyMethods(['proxyRequest'])
		->getMock();
}
private function answer(string $body, int $status = 200): IResponse&MockObject {
	$response = $this->createMock(IResponse::class);
	$response->method('getStatusCode')->willReturn($status);
	$response->method('getBody')->willReturn($body);
	...
}
```
Weitere Vorlagen: `F:/php/tests/Unit/PageControllerTest.php`, `GatewayControllerTest.php`, `PauseCommandTest.php`.

### `backend/appinfo/info.xml` (config)

**Analog:** `C:/Users/Student/nextcloud-audio-video-search/appinfo/info.xml` (verschieben). Ändern: `<id>audio_video_search_backend</id>` (Z. 21), `<image>street1983nk/audio_video_search_backend</image>` (Z. 63), Namen "Audio &amp; Video Search Backend". Routen-Form `^/<name>$` (Kommentar Z. 12-15); neue Routen `^/search$`, `^/sample$`, `^/excerpt$` je nach Plan:
```xml
<route>
	<url>^/status$</url>
	<verb>GET</verb>
	<access_level>ADMIN</access_level>
	<headers_to_exclude>[]</headers_to_exclude>
	<bruteforce_protection>[401]</bruteforce_protection>
</route>
```
Env-Präfix (Z. 77) auf `AVS_` oder `AUDIO_VIDEO_SEARCH_BACKEND_` festlegen. Beschreibung nennt die Pflicht-App "Audio & Video Search" (Findling-Muster backend info.xml: "does nothing without the Findling app").

### `backend/src/audio_video_search_backend/*.py` (verschoben)

**Analog:** `C:/Users/Student/nextcloud-audio-video-search/src/audio_video_search/` (main.py, config.py, logs.py, nc.py, settings.py). Unverändert übernehmen, nur Paketname und `APP_ID`. Tragende Regeln:
- Nur `nc.py` importiert `nc_py_api` (nc.py Z. 1-14, `tests/test_boundary.py`).
- Clients nur in `async with nc_app()` (nc.py Z. 59-66).
- Logzeilen nur mit `extra=` für IDs und Zahlen, nie Body/Pfad (logs.py Z. 1-11).
- Hintergrundaufgaben über `start_background()` (main.py Z. 47-52).
- `settings.py`: Formularbeschreibung durch den UI-SPEC-Satz "Backend-Beschreibung" ersetzen, Felder aus der Skeleton-Vorlage entfernen oder belassen (Planer).

Persistenter Pfad wie `F:/backend/src/findling/config.py` Z. 1521-1532:
```python
configured = os.environ.get("APP_PERSISTENT_STORAGE", "").strip()
if configured:
    return Path(configured)
return Path(tempfile.gettempdir()) / FALLBACK_STORAGE_DIRNAME
```

### `backend/src/.../api/status.py` (Route)

**Analog:** `R:/src/audio_video_search/main.py` Z. 108-111 plus Feldnamen aus `F:/backend/src/findling/api/status.py` Z. 348-350, 602:
```python
appVersion: str = ""
...
return os.environ.get("APP_VERSION", "").strip()
```
Feld heißt `appVersion` (PHP liest genau diesen Schlüssel, ExAppService Z. 306), zusätzlich `companion` (`ok`/`missing`) aus dem Handshake.

### `backend/src/.../api/search.py` (Route)

**Analog:** `C:/Users/Student/nextcloud-search/backend/src/findling/api/search.py` (407 Zeilen, vor dem Kopieren lesen). Antwort nur `file_id`, `start_ms`, Text, Score; Titel kommt nie vom Container (ExAppService Z. 28-35, `filterCandidates` Z. 1116).

### `backend/src/.../nc/client.py` und `api/sample.py` (streaming, file-I/O)

**Analog:** `C:/Users/Student/nextcloud-search/backend/src/findling/nc/client.py`

Gateway-Pfad (Z. 118): `GATEWAY_PATH = "/ocs/v2.php/apps/findling/files/{file_id}"`.
Stream (Z. 363-406): eigener `httpx`-Stream in `async with`, Schreiben per `asyncio.to_thread(fp.write, chunk)` (Z. 357), `ShortRead` bei zu wenig Bytes, `None` bei Rechte-Ablehnung. Für die Saat `hashlib.sha256().update(chunk)` im selben Loop ergänzen.
OCS-Aufruf an die PHP-App (Z. 576-580), Vorlage für den Handshake:
```python
return await nc._session.ocs(
    "GET",
    "/ocs/v2.php/apps/findling/queues/documents",
    params=params,
)
```
Achtung: in diesem Repo darf nur `nc.py` `nc_py_api` anfassen; Gateway-/OCS-Funktionen deshalb in `nc.py` oder ein Modul, das `test_boundary.py` ausdrücklich zulässt.

### `backend/src/.../store/schema.sql` und `repo.py` (CRUD)

**Analog:** `C:/Users/Student/nextcloud-search/backend/src/findling/store/schema.sql` Z. 1-27 (Datei als Artefakt, jedes Statement `IF NOT EXISTS`, `meta(key, value)`), Tabellen neu nach RESEARCH Entscheid 3 bis 5 (`media`, `media_key`, `file_ref`, `transcript`, `word`, `current`, `correction`, `index_outbox`).

`repo.py` Verbindung (Z. 752-795):
```python
connection = sqlite3.connect(path, autocommit=True, check_same_thread=False)
connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
connection.execute("PRAGMA foreign_keys = ON")
if read_only:
    connection.execute("PRAGMA query_only = 1")
else:
    connection.execute("PRAGMA synchronous = NORMAL")
```
WAL mit Prüfung (Z. 732-749), Transaktion (Z. 957-966):
```python
@contextmanager
def _transaction(self) -> Iterator[None]:
    self._conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        self._conn.execute("ROLLBACK")
        raise
    self._conn.execute("COMMIT")
```
Bedingter UPSERT aus RESEARCH Entscheid 5 / Pattern 2 innerhalb dieser Transaktion; `changes() == 0` heißt Rollback und `stale_rejected`. Grund-Codes als geschlossene Liste (Findling `STATE_REASONS` Z. 301), nie Freitext. SQL-Konstanten als `Final`-Strings auf Modulebene (Findling Z. 350 ff.).

### `backend/src/.../index/{analyzer,schema,open}.py` und `publish.py`

**Analog:** `C:/Users/Student/nextcloud-search/backend/src/findling/index/`

`open.py` (Z. 145-202): einziger Ort, der `Index(...)`/`Index.open(...)` ruft, registriert alle Tokenizer:
```python
path.mkdir(parents=True, exist_ok=True)
index = Index.open(str(path)) if Index.exists(str(path)) else Index(build_schema(), path=str(path))
index.register_tokenizer(TOKENIZER_DE, cached_german_analyzer(wordlist_hash(constituents), constituents))
index.register_tokenizer(TOKENIZER_EN, english_analyzer())
...
return index
```
Französisch: Findling hat **keine** eigene FR-Kette für Dokumenttext (Findling info.xml "French has no full text analysis chain"); hier `snowball_analyzer("french")` (`analyzer.py` Z. 341) registrieren. Nur DE/EN/FR übernehmen; NL/ES/IT/PT/CS weglassen.
`open_reader()` (Z. 205-220): `index.config_reader(reload_policy="commit")`, Tests rufen `index.reload()`.
`schema.py` (Z. 137-195): `SchemaBuilder`, Schlüsselfeld `add_unsigned_field(..., stored=True, indexed=True, fast=True)`; neu: `media_id`, `index_rev`, `seg_idx`, `start_ms` als unsigned fast fields, `body_de` stored, `body_en`/`body_fr` nicht stored.
`publish.py` nach `writer.py`: Writer `index.writer(heap_size=heap, num_threads=1)` (Z. 205), Löschen per `writer.delete_documents_by_query(Query.term_query(self._schema, FIELD_FILE_ID, ...))` (Z. 330, Begründung I64-Falle Z. 34), `writer.commit()` (Z. 486), `wait_merging_threads()` beim Schließen (Z. 538). Reihenfolge nach RESEARCH Pattern 3.

### `backend/tests/test_lockstep_versions.py` (test)

**Analog:** `C:/Users/Student/nextcloud-search/backend/tests/test_lockstep_versions.py`, Kopie. Pfade (Z. 43-46) passen schon (`php/appinfo/info.xml`, `backend/appinfo/info.xml`). Kern Z. 98-122 (`_findings`), Fenster-gegen-Matrix-Teil Z. 251-345 (`_MATRIX_ENTRY` liest `server-version: stableNN` aus `deploy-harp.yml`). Wenn die Matrix ein `runner`-Feld bekommt, bleibt der Regex gültig.

### `backend/tests/test_index_open.py` u. a.

**Analog:** `C:/Users/Student/nextcloud-search/backend/tests/test_index_open.py` Z. 582-600 (AST-Gang über das Paket, nur `open.py` darf öffnen) und Z. 390-397 (Kompositum-Beweis "frist" findet "Kündigungsfrist"). Für `test_provenance.py`, `test_corrections.py`, `test_store_schema.py`, `test_handshake.py` gibt es kein Analog; Testfälle stehen in RESEARCH Entscheid 4 und 5. Selbsttest-Muster jedes Gates ("jede Regel muss feuern können") wie `R:/tests/test_trilingual.py` Z. 107-135.

### `backend/tests/test_trilingual.py` (erweitern)

**Analog:** `C:/Users/Student/nextcloud-audio-video-search/tests/test_trilingual.py`. Erweitern um zweite Katalog-Wurzel `php/l10n` (inkl. `de_DE`), zweite `info.xml` (`store_languages_missing` Z. 45-52 je Datei), FR-Leerzeichenregel U+00A0 vor `: ; ? !` und Verbot U+2013/U+2014/Emoji, jeweils mit Selbsttest wie Z. 110-135.

### `.github/workflows/php.yml` (neu)

**Analog:** `C:/Users/Student/nextcloud-search/.github/workflows/php.yml` Z. 268-402 (Job `phpunit`): Server `stable34` an Wurzel, App nach `apps/audio_video_search` verschieben, Wegwerf-Installation, `composer install --no-scripts`, Negativprobe des Bootstraps, `vendor/bin/phpunit --log-junit junit.xml`, `MINIMUM_TESTS`-Boden aus JUnit-Log. Zusätzlich Jobs `lint` (Z. 83) und `composer-hygiene` (Z. 228-266) übernehmen. Actions per SHA gepinnt wie dort.

### `.github/workflows/deploy-harp.yml` (erweitern)

**Basis:** `C:/Users/Student/nextcloud-audio-video-search/.github/workflows/deploy-harp.yml` (207 Zeilen). Ergänzungen aus Findling:
- Matrix mit `runner` (Findling Z. 290-336), zusätzlich `ubuntu-24.04-arm`; Ziel laut RESEARCH 33/34/35 x amd64/arm64.
- `APP_ID` aufteilen in PHP-ID und `BACKEND_APP_ID`; Image-Build aus `./app-src/backend`; `sed` auf `app-src/backend/appinfo/info.xml` (R: Z. 147-153).
- PHP-App installieren: `mv app-src/php apps/audio_video_search` und `./occ app:enable audio_video_search` (Findling Z. 2453).
- Drift-Helfer (Findling Z. 2003-2066: Versionen ableiten, `redeploy.sh` mit unregister/register und `APP_VERSION`-Prüfung) und Drift-Schritte (Z. 2169-2205: Suche HTTP 200, OCS ok, `entries | length == 0`).
- Upgrade-Beweis: synthetische `0.0.1` nach RESEARCH Entscheid 6; `occ upgrade` mit Exit 0 oder 3 (Findling Z. 5785-5795), ExApp per `app_api:app:update --info-xml ... --wait-finish`.
- Logs sammeln wie R: Z. 192-207.

### `.github/workflows/{python,docker,release}.yml`, `scripts/release/store-archive.sh`

**Basis:** gleichnamige Dateien in `R:`. Pfade auf `backend/` umstellen (Build-Kontext, `pyproject.toml`, Tests), Image `ghcr.io/street1983nk/audio_video_search_backend` (`docker.yml` Z. 30, 92-94).
**Archiv-Analog:** `C:/Users/Student/nextcloud-search/scripts/release/store-archive.sh` Z. 72-117: `stage_companion` (Einschlussliste `appinfo lib templates js css img l10n`, `LICENSE`, `CHANGELOG.md`, `.gitkeep` löschen) und `stage_backend` (nur `backend/appinfo/info.xml`, byte-gleich per `cmp`). `release.yml` braucht zweite Zertifikats-Pin und Secret `BACKEND_PRIVATE_KEY` (RESEARCH Entscheid 6, `R:/.github/workflows/release.yml` Z. 42, 97-143 als Vorlage je Archiv).

---

## Shared Patterns

### Rechteprüfung je file_id
**Quelle:** `C:/Users/Student/nextcloud-search/php/lib/Service/SearchService.php` Z. 723-742 + `ReaderContext::actAs`
**Gilt für:** Provider, PageController, GatewayController
```php
$file = $this->readerContext->actAs(
	$userId,
	fn (): ?File => SearchService::readableFile($this->rootFolder->getUserFolder($userId), $fileId),
);
if ($file === null) { /* 404, wortgleich für alle Ablehnungsgründe */ }
```

### Vertrauensgrenze Container nach PHP
**Quelle:** `C:/Users/Student/nextcloud-search/php/lib/Controller/GatewayController.php` Z. 61-63, 170-182
**Gilt für:** GatewayController, HandshakeController
Attribute voll qualifiziert ausschreiben (`#[\OCP\AppFramework\Http\Attribute\ExAppRequired]`), erste Anweisung `rejectForeignCaller()`.

### Aufruf PHP nach Container
**Quelle:** `C:/Users/Student/nextcloud-search/php/lib/Service/ExAppService.php` Z. 882-929, 954-1047
**Gilt für:** Provider (Suche), PageController (Ausschnitt), SettingsController (Status), SampleCommand
Einziger Ort mit `exAppRequest`; jeder Fehler endet in `null`, nie in einer Exception; Timeout 1,5 s, Mindestzeit 0,3 s.

### Logs ohne Pfade und Inhalte
**Quelle:** PHP: `GatewayController.php` Z. 108, 143 (statischer Satz, nur `fileId` oder `['exception' => $e]`); Python: `R:/src/audio_video_search/logs.py` Z. 1-11
**Gilt für:** alle neuen Dateien. Owner-Regel: keine Dateinamen in Logs, Status und Fehlermeldungen.

### Fallback ohne Fehlermeldung bei ungültiger Eingabe
**Quelle:** `C:/Users/Student/nextcloud-search/php/lib/Controller/PageController.php` Z. 204-215; `SettingsController.php` Z. 502-521 für schreibende Routen (dort 400)
**Gilt für:** `play` (`t` ungültig = 0:00), Admin-Schalter (nur echter Boolean).

### Templates ohne JS lesbar
**Quelle:** `C:/Users/Student/nextcloud-search/php/templates/admin.php` Z. 5-28, 341-344
**Gilt für:** `play.php`, `admin.php`. Alle Zustände serverseitig gerendert, JS schaltet `hidden` und Textknoten, `addScript`/`addStyle` im Template, `p()` für Fremdwerte, `$l->t()` für jeden Text.

### Selbsttestende Gates
**Quelle:** `C:/Users/Student/nextcloud-search/backend/tests/test_lockstep_versions.py` Z. 140-166 (Anti-Vakuum-Klauseln) und `R:/tests/test_trilingual.py` Z. 107-135
**Gilt für:** alle neuen Python-Gates (Lockstep, Dreisprachigkeit, Workflow-Matrix, Index-Öffner).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `backend/src/.../model/provenance.py` | model | transform | Ordnung `(epoch, level, config_version)` ist neu; Code und SQL in RESEARCH Entscheid 5 / Pattern 2 |
| `backend/src/.../model/overlay.py` | model | transform | Korrektur-Überlagerung neu; Code in RESEARCH "Korrektur-Überlagerung" |
| `backend/tests/test_provenance.py`, `test_corrections.py` | test | n. a. | Testfälle in RESEARCH Entscheid 4 (Haushaltsplan-Fall + 5 Randfälle) und 5 |
| `backend/src/.../api/sample.py` | controller | file-I/O | Nur Teilmuster (Gateway-Stream); Ablauf in RESEARCH Architekturdiagramm "Dummy-Saat" |
| `ci/playwright/play.spec.ts` + `package.json` | test (e2e) | n. a. | Weder Findling noch Skeleton haben Playwright im CI; Prüfvertrag in UI-SPEC "Prüfvertrag für die Abnahme" |
| `testdata/tone-90s.webm`, `tone-90s.ogg` | fixture | n. a. | Lokal kein ffmpeg; in CI erzeugen oder einchecken (RESEARCH Pitfall 7) |

## Metadata

**Analog search scope:** `C:/Users/Student/nextcloud-search/php/{appinfo,lib,templates,js,css,l10n,tests}`, `C:/Users/Student/nextcloud-search/backend/{src/findling/{store,index,api,nc,config.py},tests}`, `C:/Users/Student/nextcloud-search/.github/workflows/{php,deploy-harp}.yml`, `C:/Users/Student/nextcloud-search/scripts/release/store-archive.sh`, `C:/Users/Student/nextcloud-audio-video-search` (gesamt außer `.planning`). Das ExApp-Skeleton selbst wurde nicht separat gelesen, weil dieses Repo der unveränderte Skeleton-Stand ist.
**Files scanned:** ca. 45 (davon 30 gezielt gelesen)
**Pattern extraction date:** 2026-11-06
