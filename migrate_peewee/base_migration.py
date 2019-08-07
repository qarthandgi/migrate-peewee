from peewee import Model

class BaseMigration(object):
	def migrate(self, migrator):
		raise NotImplementedError()
	"""
	The base class for all migrations.
	Migration files will import this from django.db.migrations.Migration
	and subclass it as a class called Migration. It will have one or more
	of the following attributes:
	 - operations: A list of Operation instances, probably from django.db.migrations.operations
	 - dependencies: A list of tuples of (app_path, migration_name)
	 - run_before: A list of tuples of (app_path, migration_name)
	 - replaces: A list of migration_names
	Note that all migrations come out of migrations and into the Loader or
	Graph as instances, having been initialized with their app label and name.
	"""

	# Operations to apply during this migration, in order.
	operations = []

	# Other migrations that should be run before this migration.
	# Should be a list of (app, migration_name).
	dependencies = []

	# Other migrations that should be run after this one (i.e. have
	# this migration added to their dependencies). Useful to make third-party
	# apps' migrations run after your AUTH_USER replacement, for example.
	run_before = []

	# Migration names in this app that this migration replaces. If this is
	# non-empty, this migration will only be applied if all these migrations
	# are not applied.
	replaces = []

	# Is this an initial migration? Initial migrations are skipped on
	# --fake-initial if the table or fields already exist. If None, check if
	# the migration has any dependencies to determine if there are dependencies
	# to tell if db introspection needs to be done. If True, always perform
	# introspection. If False, never perform introspection.
	initial = None

	# Whether to wrap the whole migration in a transaction. Only has an effect
	# on database backends which support transactional DDL.
	atomic = True

	def __init__(self, name):
		self.name = name
		# Copy dependencies & other attrs as we might mutate them at runtime
		self.operations = list(self.__class__.operations)
		self.dependencies = list(self.__class__.dependencies)
		self.run_before = list(self.__class__.run_before)
		self.replaces = list(self.__class__.replaces)

	def __eq__(self, other):
		return (
			isinstance(other, Migration) and
			self.name == other.name
		)

	def __repr__(self):
		return "<Migration %s>" % self.name

	def __str__(self):
		return "%s" % self.name

	def __hash__(self):
		return hash("%s" % self.name)

	def apply(self, project_state, schema_editor):
		"""
		Take a project_state representing all migrations prior to this one
		and a schema_editor for a live database and apply the migration
		in a forwards order.
		Return the resulting project state for efficient reuse by following
		Migrations.
		"""
		for operation in self.operations:
			# Save the state before the operation has run
			old_state = project_state.clone()
			operation.state_forwards(project_state)
			# Run the operation
			atomic_operation = operation.atomic or (self.atomic and operation.atomic is not False)
			if not schema_editor.atomic_migration and atomic_operation:
				# Force a transaction on a non-transactional-DDL backend or an
				# atomic operation inside a non-atomic migration.
				with atomic(schema_editor.connection.alias):
					operation.database_forwards(self.app_label, schema_editor, old_state, project_state)
			else:
				# Normal behaviour
				operation.database_forwards(self.app_label, schema_editor, old_state, project_state)
		return project_state