import os

from mixtum_core.settings import *


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ["MIXTUM_SQLITE_TEST_DB"],
    }
}
