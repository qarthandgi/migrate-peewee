

import glob
import logging
import os
import sys
from datetime import datetime
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from os.path import basename, dirname, isfile, join

import click

from peewee import SQL, Model
from playhouse.migrate import PostgresqlMigrator
from playhouse.migrate import migrate as migrate_
from playhouse.migrate import operation
from playhouse.reflection import Introspector

from migrate_peewee.db import db, DatabaseMigration

class MigrationError(BaseException):
	pass


def load_migrations(migration_dir):
	module_name = 'Migration'
	cwd = os.getcwd()
	files = glob.glob(join(cwd, migration_dir, '*.py'))
	migrations = []
	for f in files:
		if isfile(f) and not f.endswith('__init__.py'):
			name = os.path.splitext(os.path.basename(f))[0]
			loader = SourceFileLoader(module_name, f)
			module = module_from_spec(spec_from_loader(module_name, loader, origin=f))
			loader.exec_module(module)
			migrations.append(module.Migration(name))
	return migrations

def validate_refs(migrations):
	refs = {}
	for m in migrations:
		refs[m.name] = m

	# Validate Dependencies
	for m in migrations:
		if not (m.dependencies or m.initial):
			raise MigrationError(f'Migration "{m.name}" has no depedencies is not initial')
		for d in m.dependencies:
			if d not in refs:
				raise MigrationError(f'Dependency "{d}" for {m.name} not found')


class LazyModelIntrospector(object):
	def __init__(self, db):
		self.db = db
		self.generated = False
		self.models = {}

	def __getattr__(self, name):
		if not getattr(self, 'generated'):
			self.models = self.generate_models()
			self.generated = True
		return getattr(self, 'models')[name]

	def preload(self, table_names):
		self.models = self.generate_models(table_names=table_names)
		self.generated = True

	def generate_models(self, *args, **kwargs):
		return Introspector.from_database(self.db).generate_models(*args, **kwargs)



class SFMigrator(PostgresqlMigrator):
	@operation
	def raw(self, sql):
		return SQL(sql)

	@operation
	def python(self, forwards_func, inject_models=False):
		if inject_models:
			models = Introspector.from_database(self.database).generate_models()
			forwards_func(models)
		else:
			forwards_func()

	@operation
	def create_model_tables(self, *models):
		db.create_tables(models)

	@operation
	def drop_model_tables(self, *models):
		db.drop_tables(models)


def get_migrator():
	migrator = SFMigrator(db)
	return migrator

def get_applied():
	DatabaseMigration.bind(db)
	if DatabaseMigration.table_exists():
		return [m.name for m in DatabaseMigration.select(DatabaseMigration.name)]
	else:
		DatabaseMigration.create_table()
		return []

def apply_migrations(migrations, applied, migrator):
	def is_ready(migration):
		return set(migration.dependencies).issubset(applied) or migration.initial
	completed = set()
	for m in migrations:
		if is_ready(m):
			sys.stdout.write('Running %s...' %m.name)
			sys.stdout.flush()

			with db.atomic():
				models = LazyModelIntrospector(db) #Introspector.from_database(db).generate_models()
				operations = m.migrate(migrator, models)
				if operations:
					migrate_(*operations)
				DatabaseMigration.create(name=m.name, applied=datetime.now())
				completed.add(m)

			sys.stdout.write('Success\n')
	remaining = migrations - completed
	now_applied = applied | set(c.name for c in completed)
	if len(remaining):
		apply_migrations(remaining, now_applied, migrator)



@click.command()
@click.option('-d', '--database', envvar='DATABASE_NAME', help='Database name')
@click.option('-h', '--host', envvar='DATABASE_HOST', help='Database host')
@click.option('-p', '--port', envvar='DATABASE_PORT', help='Database port')
@click.option('-u', '--user', envvar='DATABASE_USER', help='Database user')
@click.option('--password', envvar='DATABASE_PASSWORD', help='Database password', prompt=True, hide_input=True)
@click.option('--migrations-dir', 'migrations_dir', default='migrations', help='Migrations base directory')
def migrate(database, host, port, user, password, migrations_dir):
	db.init(
		database,
		host=host,
		port=port,
		user=user,
		password=password
	)

	migrations = load_migrations(migrations_dir)
	validate_refs(migrations)
	applied = get_applied()
	to_apply = set()
	for m in migrations:
		if m.name not in applied:
			to_apply.add(m)
	to_apply_count = len(to_apply)

	if to_apply_count:
		print('Appling %s migration(s)' % to_apply_count)
	else:
		print('No migrations to apply')
	migrator = get_migrator()
	apply_migrations(to_apply, set(applied), migrator)


if __name__ == '__main__':
	migrate()