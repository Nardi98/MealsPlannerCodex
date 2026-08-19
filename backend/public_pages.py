"""The unauthenticated share page at ``/s/{token}`` (§3, §6).

Phase 0 ships this module empty and pre-wired into ``main`` (D-6); the Phase 2B
agent owns its contents.

This is the product's *only* unauthenticated surface, so the requirements it
carries are disproportionate to its size: server-rendered complete HTML that is
fully readable with JavaScript disabled (RA-1/RA-2), a byte-identical neutral
404 for revoked, expired, and nonexistent tokens alike (SH-22), no
``Set-Cookie`` of any kind (PRV-6), ``noindex`` plus ``Referrer-Policy:
no-referrer`` (RA-8, SH-28), and output serialised through the PRV-1 allowlist
rather than the ORM model.
"""

from fastapi import APIRouter

router = APIRouter(tags=["public"])
