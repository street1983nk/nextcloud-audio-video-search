<?php

declare(strict_types=1);

namespace OCA\AudioVideoSearch\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\DB\Types;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

/**
 * The three tables of the discovery (phase 2, plan 02-03).
 *
 * avs_queue is the work stock up to the hand over, and only that: the container
 * claims rows, writes the file reference into its own state.db and acknowledges
 * within seconds. Downloading, hashing and transcribing run in the stages of the
 * container, so the lock of a row never has to outlast a three hour recording
 * (02-RESEARCH.md, Pattern 1).
 *
 * avs_crawl is the first crawl per mount: a cursor over the file ids of the
 * mount root and the time it finished. The reconcile of the container walks a
 * mount only once its first crawl has finished (Pattern 2).
 *
 * avs_storage is the classification of a storage: provider, share key, auth
 * kind and whether it can be captured in the background (D-02-03). capturable
 * defaults to 0, so a storage nobody has classified yet is never admissible
 * (T-02-12); plan 02-12 fills it.
 *
 * Every table is guarded by hasTable(), so a replay after a failed upgrade is
 * a no-op. The class name and the file name are identical to the character:
 * Nextcloud loads migrations by file name.
 */
class Version000200Date20261107000000 extends SimpleMigrationStep {
	public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper {
		/** @var ISchemaWrapper $schema */
		$schema = $schemaClosure();
		$changed = false;

		if (!$schema->hasTable('avs_queue')) {
			$table = $schema->createTable('avs_queue');
			$table->addColumn('id', Types::BIGINT, ['autoincrement' => true, 'notnull' => true, 'length' => 64]);
			// One of QueueMapper::KINDS, never free text.
			$table->addColumn('kind', Types::STRING, ['notnull' => true, 'length' => 16]);
			// NULL for a job about a whole storage (exclude_storage).
			$table->addColumn('file_id', Types::BIGINT, ['notnull' => false, 'length' => 64]);
			$table->addColumn('storage_id', Types::BIGINT, ['notnull' => true, 'length' => 64]);
			// Unix seconds. NULL in locked_at means free; a claim older than
			// QueueMapper::LOCK_TIMEOUT is free again.
			$table->addColumn('enqueued_at', Types::INTEGER, ['notnull' => true, 'default' => 0]);
			$table->addColumn('locked_at', Types::INTEGER, ['notnull' => false]);
			$table->addColumn('lock_token', Types::STRING, ['notnull' => false, 'length' => 32]);
			// Set when the file changed while its row was claimed: the
			// acknowledgement then frees the row instead of deleting it.
			$table->addColumn('dirty', Types::SMALLINT, ['notnull' => true, 'default' => 0]);
			$table->addColumn('attempts', Types::INTEGER, ['notnull' => true, 'default' => 0]);
			$table->setPrimaryKey(['id'], 'avs_q_id');
			// The deduplication: a second event for the same file is not a second job.
			$table->addUniqueIndex(['kind', 'file_id', 'storage_id'], 'avs_q_uniq');
			// The claim asks per kind for the free rows, oldest first.
			$table->addIndex(['kind', 'locked_at', 'id'], 'avs_q_claim');
			// A delete replaces a content row of the same file and the other way round.
			$table->addIndex(['file_id'], 'avs_q_file');
			$table->addIndex(['lock_token'], 'avs_q_token');
			$changed = true;
		}

		if (!$schema->hasTable('avs_crawl')) {
			$table = $schema->createTable('avs_crawl');
			$table->addColumn('storage_id', Types::BIGINT, ['notnull' => true, 'length' => 64]);
			// The folder the crawl walks: the overridden root of the mount
			// (the files folder of a home), see StorageService::getMounts().
			$table->addColumn('root_id', Types::BIGINT, ['notnull' => true, 'length' => 64]);
			// The last file id the crawl handed over. Not called cursor: that
			// word is reserved in MySQL and MariaDB.
			$table->addColumn('last_file_id', Types::BIGINT, ['notnull' => true, 'default' => 0, 'length' => 64]);
			$table->addColumn('generation', Types::INTEGER, ['notnull' => true, 'default' => 0]);
			$table->addColumn('started_at', Types::INTEGER, ['notnull' => false]);
			$table->addColumn('finished_at', Types::INTEGER, ['notnull' => false]);
			$table->setPrimaryKey(['storage_id', 'root_id'], 'avs_c_pk');
			$changed = true;
		}

		if (!$schema->hasTable('avs_storage')) {
			$table = $schema->createTable('avs_storage');
			$table->addColumn('storage_id', Types::BIGINT, ['notnull' => true, 'length' => 64]);
			// The external storage configuration, NULL for homes and team folders.
			$table->addColumn('mount_id', Types::BIGINT, ['notnull' => false, 'length' => 64]);
			$table->addColumn('provider', Types::STRING, ['notnull' => true, 'length' => 64, 'default' => '']);
			// sha256 of the normalised share key, never the key itself (it names a host).
			$table->addColumn('share_key_hash', Types::STRING, ['notnull' => false, 'length' => 64]);
			$table->addColumn('root_prefix', Types::STRING, ['notnull' => false, 'length' => 4000]);
			$table->addColumn('auth_kind', Types::STRING, ['notnull' => false, 'length' => 64]);
			$table->addColumn('capturable', Types::SMALLINT, ['notnull' => true, 'default' => 0]);
			// A code from a closed list (plan 02-12), never free text.
			$table->addColumn('reason', Types::STRING, ['notnull' => false, 'length' => 32]);
			$table->addColumn('users', Types::INTEGER, ['notnull' => true, 'default' => 0]);
			$table->addColumn('checked_at', Types::INTEGER, ['notnull' => false]);
			$table->addColumn('rescanned_at', Types::INTEGER, ['notnull' => false]);
			$table->setPrimaryKey(['storage_id'], 'avs_s_pk');
			$table->addIndex(['mount_id'], 'avs_s_mount');
			$changed = true;
		}

		return $changed ? $schema : null;
	}
}
