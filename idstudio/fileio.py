"""Replace exports only after a complete write on the destination filesystem."""
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_output(destination):
    destination = Path(destination)
    descriptor, name = tempfile.mkstemp(prefix=".credential-", suffix=".tmp", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        with temporary.open("rb+") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
