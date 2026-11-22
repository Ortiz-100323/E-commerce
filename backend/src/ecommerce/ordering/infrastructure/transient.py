from psycopg import errors
from sqlalchemy.exc import DBAPIError


class DatabaseTransientErrors:
    def is_transient(self, error: Exception) -> bool:
        return isinstance(error, DBAPIError) and isinstance(error.orig, errors.DeadlockDetected)
