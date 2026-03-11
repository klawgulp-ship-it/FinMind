import io
import json
import zipfile
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models.user import User
from app.services import audit_logger

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

DELETION_CONFIRMATION_PHRASE = "DELETE MY ACCOUNT"


@auth_bp.route("/export-data", methods=["GET"])
@jwt_required()
def export_data():
    current_user_id = get_jwt_identity()
    user = User.query.filter_by(id=current_user_id, deleted_at=None).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    pii_data = user.to_pii_dict()

    audit_logs = [
        {
            "action": log.action,
            "performed_at": log.performed_at.isoformat() if log.performed_at else None,
            "metadata": log.metadata,
        }
        for log in user.audit_logs
    ]

    export_payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "profile": pii_data,
        "audit_logs": audit_logs,
    }

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("user_data.json", json.dumps(export_payload, indent=2))
    zip_buffer.seek(0)

    audit_logger.log_action(
        action="PII_EXPORT",
        performed_by_user_id=current_user_id,
        target_user_id=current_user_id,
        metadata={"format": "zip"},
        ip_address=request.remote_addr,
    )

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"user_{current_user_id}_data.zip",
    )


@auth_bp.route("/delete-account", methods=["DELETE"])
@jwt_required()
def delete_account():
    current_user_id = get_jwt_identity()
    user = User.query.filter_by(id=current_user_id, deleted_at=None).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    body = request.get_json(force=True, silent=True) or {}
    confirmation = body.get("confirmation", "")

    if confirmation != DELETION_CONFIRMATION_PHRASE:
        return jsonify(
            {
                "error": "Confirmation phrase required",
                "hint": f'Send {{"confirmation": "{DELETION_CONFIRMATION_PHRASE}"}} to confirm.',
            }
        ), 400

    user.email = f"deleted_{user.id}@deleted.invalid"
    user.username = f"deleted_{user.id}"
    user.full_name = None
    user.phone = None
    user.password_hash = ""
    user.deleted_at = datetime.utcnow()

    db.session.commit()

    audit_logger.log_action(
        action="ACCOUNT_DELETED",
        performed_by_user_id=current_user_id,
        target_user_id=current_user_id,
        metadata={"method": "self-service", "irreversible": True},
        ip_address=request.remote_addr,
    )

    return jsonify({"message": "Account permanently deleted."}), 200
