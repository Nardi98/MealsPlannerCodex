"""The unit system is a display preference, and the bulk switch writes only that.

Switching between metric and US changes how amounts are *rendered*, never what
is stored. The one bulk operation this feature offers -- flipping ingredients
from weighing to measuring -- writes a display preference too, which is why it
is safe to offer as a single click: a wrong answer costs one click to reverse
and cannot corrupt a quantity.
"""

from models import DimensionEnum, Ingredient


def _ingredient(session, name, user, **factors):
    ing = Ingredient(name=name, user_id=user.id, **factors)
    session.add(ing)
    session.flush()
    return ing


class TestTheSetting:
    def test_an_account_starts_reading_in_metric(self, auth_client):
        assert auth_client.get("/auth/me").json()["unit_system"] == "metric"

    def test_the_account_can_switch_to_us(self, auth_client):
        res = auth_client.put("/auth/me/unit-system", json={"unit_system": "us"})

        assert res.status_code == 200
        assert res.json()["unit_system"] == "us"
        assert auth_client.get("/auth/me").json()["unit_system"] == "us"

    def test_a_system_nobody_reads_in_is_refused(self, auth_client):
        res = auth_client.put(
            "/auth/me/unit-system", json={"unit_system": "cubits"}
        )
        assert res.status_code == 422


class TestTheBulkSwitch:
    def _switch(self, client, dimension):
        return client.post(
            "/ingredients/preferred-dimension",
            json={"preferred_dimension": dimension},
        )

    def test_it_flips_every_ingredient_the_factors_allow(
        self, auth_client, db_session, user
    ):
        _ingredient(
            db_session, "Flour", user, grams_per_ml=0.53,
            preferred_dimension=DimensionEnum.MASS,
        )
        db_session.flush()

        res = self._switch(auth_client, "volume")

        assert res.status_code == 200
        assert res.json()["switched"] == ["Flour"]

    def test_it_names_what_it_could_not_switch_and_why(
        self, auth_client, db_session, user
    ):
        # Eggs have no useful density, so there is nothing to switch them to.
        _ingredient(
            db_session, "Egg", user, grams_per_piece=50,
            preferred_dimension=DimensionEnum.PIECE,
        )
        _ingredient(
            db_session, "Salt", user, preferred_dimension=DimensionEnum.MASS,
        )
        db_session.flush()

        body = self._switch(auth_client, "volume").json()

        assert body["switched"] == []
        assert "Salt" in body["skipped"]

    def test_it_never_touches_a_counted_ingredient(
        self, auth_client, db_session, user
    ):
        # Counting is not a measuring system's business. An ingredient the user
        # counts stays counted whichever way they read amounts.
        egg = _ingredient(
            db_session, "Egg", user, grams_per_piece=50, grams_per_ml=1.0,
            preferred_dimension=DimensionEnum.PIECE,
        )
        db_session.flush()

        self._switch(auth_client, "volume")
        db_session.refresh(egg)

        assert egg.preferred_dimension is DimensionEnum.PIECE
        assert "Egg" not in self._switch(auth_client, "volume").json()["skipped"]

    def test_it_never_rewrites_a_stored_quantity(
        self, auth_client, db_session, user
    ):
        flour = _ingredient(
            db_session, "Flour", user, grams_per_ml=0.53,
            preferred_dimension=DimensionEnum.MASS,
        )
        db_session.flush()

        self._switch(auth_client, "volume")
        db_session.refresh(flour)

        assert flour.grams_per_ml == 0.53
