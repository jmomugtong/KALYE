import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.workers.celery_app import celery_app as _celery_app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def celery_eager_mode():
    """Run all Celery tasks synchronously in-process during tests."""
    _celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield
    _celery_app.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
    )
