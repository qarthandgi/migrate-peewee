from setuptools import setup

setup(
	name="migrate-peewee",
	version="0.0.1",
	description="Database Migrator for Peewee",
	url="https://github.com/ServiceF/migrate-peewee.git",
	py_modules=["migrate_peewee"],
	install_requires=["click", "peewee", "psycopg2-binary"],
	entry_points="""
		[console_scripts]
		migrate=migrate_peewee.scripts.migrate:migrate
	"""
)