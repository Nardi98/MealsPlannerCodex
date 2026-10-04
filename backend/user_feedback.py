"""Domain logic of the user feedback system: filing, listing and triaging items.

A pure domain module, called by ``user_feedback_routes`` (a user's one
submission route) and ``user_feedback_admin_routes`` (admin triage). It imports
nothing of ours but ``models`` and ``storage`` -- never ``main``, a router,
``crud`` or ``scoping`` (guarded by ``tests/test_architecture_guards.py``).

Feedback is **not owner-scoped, by design**: ``FeedbackItem.user_id`` records
who filed an item (provenance), not who owns it, and the only reader is an admin
who must see every row. Queries here are therefore deliberately not passed
through ``scoping.scope()``.

Named ``user_feedback`` because "feedback" already means the meal-plan
accept/reject signal. Empty until the service is written.
"""
