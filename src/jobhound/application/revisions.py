"""Opaque content-identity for files inside an opportunity directory.

`Revision` is a NewType over `str`. Callers MUST NOT inspect its
structure — they only compare two revisions for equality. The concrete
representation depends on the FileStore adapter:

  - GitLocalFileStore: git blob SHA (`git hash-object`)
  - S3FileStore (future): S3 ETag
  - InMemoryFileStore (tests): sha1 of content

Adapters compute revisions via `FileStore.compute_revision`. The
application layer never computes a revision itself — that decision is
deliberately the adapter's.
"""

from __future__ import annotations

from typing import NewType

Revision = NewType("Revision", str)
