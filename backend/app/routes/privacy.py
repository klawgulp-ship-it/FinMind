import io
import json
import zipfile
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models.audit_log import log_privacy_action
from app.models.user import User

privacy_bp = Blueprint("privacy", __name__, url_prefix="/api/privacy")


def _collect_user_data(user):
    """Collect all personal data associated with a user into a dict."""
    data = {
        "account": {
            "id": user.id,
            "email": user.email,
            "username": getattr(user, "username", None),
            "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        },
    }

    # Extend here with additional related models (posts, comments, etc.)
    # Example:
    # data["posts"] = [p.to_dict() for p in user.posts]

    return data


@privacy_bp.route("/export", methods=["GET"])
@jwt_required()
def export_data():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)

    user_data = _collect_user_data(user)
    json_bytes = json.dumps(user_data, indent=2, default=str).encode("utf-8")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("user_data.json", json_bytes)
    zip_buffer.seek(0)

    log_privacy_action(
        db,
        user_id=user_id,
        action="PII_EXPORT",
        detail="User requested PII data export.",
        ip_address=request.remote_addr,
    )

    filename = f"user_{user_id}_export_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.zip"
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@privacy_bp.route("/delete", methods=["DELETE"])
@jwt_required()
def delete_account():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)

    body = request.get_json(silent=True) or {}
    confirm = body.get("confirm")
    if confirm != "DELETE MY ACCOUNT":
        return jsonify({"error": "Confirmation phrase required: 'DELETE MY ACCOUNT'"}), 400

    # Log before deletion so user_id is still meaningful
    log_privacy_action(
        db,
        user_id=user_id,
        action="PII_DELETE",
        detail="User confirmed irreversible account and data deletion.",
        ip_address=request.remote_addr,
    )

    # Cascading deletion relies on DB-level ON DELETE CASCADE constraints
    # or ORM relationships with cascade="all, delete-orphan".
    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "Account and all associated data have been permanently deleted."}), 200
