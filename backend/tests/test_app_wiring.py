"""D-6 / D-4 / Q-1: the structural wiring Phase 0 puts in place.

Later phases fill the three routers and the template/static tree; Phase 0 only
guarantees they are mounted, so no later agent has to edit ``main.py``.
"""

import main


def test_the_three_domain_routers_are_included():
    import public_pages
    import share_routes
    import username_routes

    for module in (username_routes, share_routes, public_pages):
        assert module.router is not None

    # Each router's own route set is asserted in that router's test module
    # (``test_username_routes.py``, ``test_share_routes.py``,
    # ``test_share_page.py``). Asserting the contents here too would make this
    # file contended by every phase that adds a route -- which is exactly what
    # D-6 exists to avoid -- so this test asserts only that the wiring holds.

    # Including an empty router is a no-op at the route table, so assert the
    # modules are the ones ``main`` imported rather than counting routes.
    assert main.username_routes is username_routes
    assert main.share_routes is share_routes
    assert main.public_pages is public_pages


def test_the_catalog_router_is_included():
    """TST-10: ``/catalog/*`` is served by ``catalog_routes``, mounted by ``main``."""
    import catalog_routes

    assert main.catalog_routes is catalog_routes
    catalog_paths = {route.path for route in catalog_routes.router.routes}
    served = {getattr(route, "path", None) for route in main.app.routes}
    assert catalog_paths and catalog_paths <= served


def test_the_catalog_admin_router_is_included():
    """TST-10: ``/admin/catalog/*`` is served by ``catalog_admin_routes``, mounted by ``main``."""
    import catalog_admin_routes

    assert main.catalog_admin_routes is catalog_admin_routes
    admin_paths = {route.path for route in catalog_admin_routes.router.routes}
    served = {getattr(route, "path", None) for route in main.app.routes}
    assert admin_paths and admin_paths <= served


def test_static_is_mounted_for_the_public_stylesheet():
    """D-4: ``/static`` serves ``backend/static/public.css`` in Phase 1B."""
    assert any(
        getattr(route, "path", None) == "/static" for route in main.app.routes
    )


def test_public_base_url_is_configurable():
    """Q-1: share URLs are absolutised against this, or the request in dev."""
    assert hasattr(main, "PUBLIC_BASE_URL")


def test_startup_seeds_the_reserved_username_list(db_session):
    """UN-4: the list is in the table before the first registration.

    ``main`` runs :func:`main._bootstrap` at import; the suite resets the schema
    around it, so the behaviour is asserted by calling it rather than by reading
    whatever happens to survive.
    """
    from sqlalchemy import select

    from models import RESERVED_USERNAMES, ReservedUsername

    main._bootstrap(db_session)

    stored = {
        row.username
        for row in db_session.execute(select(ReservedUsername)).scalars()
    }
    assert set(RESERVED_USERNAMES) <= stored


def test_startup_bootstrap_is_idempotent(db_session):
    from sqlalchemy import select

    from models import ReservedUsername

    main._bootstrap(db_session)
    before = len(db_session.execute(select(ReservedUsername)).scalars().all())
    main._bootstrap(db_session)
    after = len(db_session.execute(select(ReservedUsername)).scalars().all())
    assert before == after
