"""Share, Shared-with-me, and Copy endpoints (§5.1, §5.2, §5.3, §7).

Phase 0 ships this module empty and pre-wired into ``main`` (D-6); the Phase 2A
agent owns its contents and defines its request/response models locally.

To be built here:

* ``POST /recipes/{id}/shares`` -- SH-1/4/5/9, rate-limited per user (SH-11 via
  ``ratelimit.SHARE_RATE_LIMIT``), promoting a private recipe to ``unlisted``
  (VIS-6).
* ``GET /recipes/{id}/shares`` (SH-20, owner only) and
  ``DELETE /shares/{share_id}`` (revoke, then demote per VIS-7).
* ``GET /shared-with-me`` (SWM-1/2/4/5) and the dismiss endpoint (SWM-3).
* ``POST /s/{token}/copy`` -- CP-1..CP-11 plus the AT-1 attribution snapshot.

The sharpest trap waiting here is CP-3: ``crud.get_or_create_ingredient``
resolves by id *before* name, so the copy path must pass ``ingredient_id=None``
or it will bind the copy to the source owner's ingredient rows.
"""

from fastapi import APIRouter

router = APIRouter(tags=["shares"])
