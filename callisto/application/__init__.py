"""callisto/application/__init__.py

Application services and use cases for the Callisto daemon.

Copyright BINGO Collaboration
Last modified: 2026-02-24
"""

from .control import process_client_command

__all__ = ["process_client_command"]
