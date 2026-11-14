<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\DB\Types;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

/**
 * The origin of a row of the work stock (phase 3, plan 03-04).
 *
 * Event and crawl both write rows of the kind content; only the PHP app knows
 * which of the two wrote one. The container takes new and changed files first
 * and the stock after them (D-03-05), so the origin travels with the claim
 * (03-RESEARCH.md, Pitfall 6). One of QueueMapper::ORIGINS, never free text.
 *
 * Rows that are already queued when this step runs get crawl: nobody knows any
 * more whether an event wrote them, and crawl never pushes a file forward.
 *
 * The column is guarded by hasColumn(), so a replay is a no-op. The class name
 * and the file name are identical to the character: Nextcloud loads
 * migrations by file name.
 */
class Version000300Date20261114000000 extends SimpleMigrationStep {
	public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper {
		/** @var ISchemaWrapper $schema */
		$schema = $schemaClosure();
		$changed = false;

		if ($schema->hasTable('avs_queue')) {
			$table = $schema->getTable('avs_queue');
			if (!$table->hasColumn('origin')) {
				$table->addColumn('origin', Types::STRING, ['notnull' => true, 'length' => 8, 'default' => 'crawl']);
				$changed = true;
			}
		}

		return $changed ? $schema : null;
	}
}
