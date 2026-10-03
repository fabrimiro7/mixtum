#!/usr/bin/env python3
import os
import sys


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mixtum_core.settings")
    os.environ.setdefault("MIXTUM_COMPOSITION_MODULE", "mixtum_instance.composition")
    os.environ.setdefault("MIXTUM_INSTANCE_ROOT", os.path.dirname(os.path.abspath(__file__)))
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
