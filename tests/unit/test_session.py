from sqlalchemy.orm import Session

from app.db.session import get_db


def test_get_db_yields_a_session_and_closes_it() -> None:
    """The dependency hands out a session and releases it when the generator ends."""
    generator = get_db()
    session = next(generator)

    assert isinstance(session, Session)

    generator.close()

    assert session.get_transaction() is None
