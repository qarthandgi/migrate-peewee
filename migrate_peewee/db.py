import os
from peewee import Model, CharField, DateTimeField
from playhouse.pool import PooledPostgresqlExtDatabase

def spawn_deferred_db(field_types=dict()):
	return PooledPostgresqlExtDatabase(
		None,
		max_connections=8,
		stale_timeout=600,
		register_hstore=False,
		autorollback=True,
		field_types=field_types
	)

db = spawn_deferred_db()

class MigrationModel(Model):
	class Meta:
		database = db
		table_function = lambda model: model.__name__

class DatabaseMigration(Model):
	class Meta:
		table_name = os.getenv('DATABASE_MIGRATION_TABLE_NAME', 'databasemigration')

	name = CharField()
	applied = DateTimeField()
