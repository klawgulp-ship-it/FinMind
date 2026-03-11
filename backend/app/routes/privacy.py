import csv
import io
import json
import zipfile
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user, login_required

from app import db
from app.models.audit_log import AuditLog
from app.models.user import User

privacy_bp = Blueprint("privacy", __name__, url_prefix="/api/privacy")


def _log_action(user_id, action, detail=None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        detail=detail,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    db.session.commit()


@privacy_bp.route("/export", methods=["GET"])
@login_required
def export_data():
    """Generate a ZIP archive containing the user's personal data as JSON and CSV."""
    user = User.query.get_or_404(current_user.id)

    user_data = {
        "id": user.id,
        "email": user.email,
        "username": getattr(user, "username", None),
        "created_at": user.created_at.isoformat() if hasattr(user, "created_at") and user.created_at else None,
    }

    audit_logs = AuditLog.query.filter_by(user_id=user.id).all()
    audit_data = [log.to_dict() for log in audit_logs]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("user_profile.json", json.dumps(user_data, indent=2))

        csv_buffer = io.StringIO()
        if user_data:
            writer = csv.DictWriter(csv_buffer, fieldnames=user_data.keys())
            writer.writeheader()
            writer.writerow(user_data)
        zf.writestr("user_profile.csv", csv_buffer.getvalue())

        zf.writestr("audit_logs.json", json.dumps(audit_data, indent=2))

        if audit_data:
            audit_csv_buffer = io.StringIO()
            audit_writer = csv.DictWriter(audit_csv_buffer, fieldnames=audit_data[0].keys())
            audit_writer.writeheader()
            audit_writer.writerows(audit_data)
            zf.writestr("audit_logs.csv", audit_csv_buffer.getvalue())

    zip_buffer.seek(0)

    _log_action(user.id, "PII_EXPORT", detail="User requested PII export package.")

    filename = f"pii_export_{user.id}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.zip"
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@privacy_bp.route("/delete", methods=["DELETE"])
@login_required
def delete_account():
    """Irreversibly delete the current user's account and all associated data."""
    user = User.query.get_or_404(current_user.id)
    user_id = user.id

    body = request.get_json(silent=True) or {}
    confirmation = body.get("confirm")
    if confirmation != "DELETE_MY_ACCOUNT":
        return jsonify({"error": "Confirmation phrase required: DELETE_MY_ACCOUNT"}), 400

    _log_action(
        user_id,
        "PII_DELETE_REQUESTED",
        detail="User initiated irreversible account deletion.",
    )

    AuditLog.query.filter_by(user_id=user_id).delete()

    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "Account and all associated data have been permanently deleted."}), 200
