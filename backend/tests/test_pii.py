import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.user import User
from app.services import audit_logger, pii_service

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture()
def db():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def sample_user(db):
    user = User(
        email="alice@example.com",
        username="alice",
        hashed_password="hashed",
        full_name="Alice Example",
        phone="555-1234",
        address="123 Main St",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_export_json(db, sample_user):
    json_str = pii_service.export_as_json(db, sample_user.id)
    assert json_str is not None
    data = json.loads(json_str)
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["username"] == "alice"
    assert "exported_at" in data


def test_export_csv(db, sample_user):
    csv_str = pii_service.export_as_csv(db, sample_user.id)
    assert csv_str is not None
    assert "alice@example.com" in csv_str
    assert "USER DATA" in csv_str


def test_export_nonexistent_user(db):
    result = pii_service.export_as_json(db, 99999)
    assert result is None


def test_irreversible_deletion(db, sample_user):
    user_id = sample_user.id
    result = pii_service.irreversibly_delete_user(db, user_id, actor_id=user_id)
    assert result is True

    db.expire_all()
    deleted_user = db.query(User).filter(User.id == user_id).first()
    assert deleted_user.is_deleted is True
    assert deleted_user.is_active is False
    assert "deleted" in deleted_user.email
    assert deleted_user.full_name is None
    assert deleted_user.phone is None
    assert deleted_user.address is None
    assert deleted_user.hashed_password == ""


def test_deletion_creates_audit_logs(db, sample_user):
    from app.models.user import AuditLog
    user_id = sample_user.id
    pii_service.irreversibly_delete_user(db, user_id, actor_id=user_id)

    logs = db.query(AuditLog).filter(AuditLog.event_type.in_([
        audit_logger.EVENT_DATA_DELETE_INITIATED,
        audit_logger.EVENT_DATA_DELETE_COMPLETED,
    ])).all()
    assert len(logs) == 2


def test_export_creates_audit_log(db, sample_user):
    from app.models.user import AuditLog
    audit_logger.log_event(
        db=db,
        event_type=audit_logger.EVENT_DATA_EXPORT,
        user_id=sample_user.id,
        actor_id=sample_user.id,
        description="Test export",
    )
    logs = db.query(AuditLog).filter(
        AuditLog.event_type == audit_logger.EVENT_DATA_EXPORT
    ).all()
    assert len(logs) == 1


def test_delete_already_deleted_user(db, sample_user):
    user_id = sample_user.id
    pii_service.irreversibly_delete_user(db, user_id, actor_id=user_id)
    result = pii_service.irreversibly_delete_user(db, user_id, actor_id=user_id)
    assert result is False
