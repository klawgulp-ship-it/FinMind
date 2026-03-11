from datetime import date

from flask import Blueprint, jsonify, request

from app.services.insights import generate_weekly_digest, get_digest_history

bp = Blueprint("insights", __name__, url_prefix="/api/insights")


@bp.route("/weekly-digest", methods=["POST"])
def weekly_digest():
    """
    Generate (or refresh) the weekly financial digest for a user.

    Request JSON body:
        user_id (int, required): The user to generate the digest for.
        ref_date (str, optional): ISO date (YYYY-MM-DD) used as the reference
            point for the week. Defaults to today.

    Returns:
        200 JSON digest object on success.
        400 JSON error if user_id is missing or inputs are invalid.
    """
    body = request.get_json(silent=True) or {}

    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    ref_date_str = body.get("ref_date")
    ref_date = None
    if ref_date_str:
        try:
            ref_date = date.fromisoformat(ref_date_str)
        except ValueError:
            return jsonify({"error": "ref_date must be ISO format YYYY-MM-DD"}), 400

    try:
        digest = generate_weekly_digest(int(user_id), ref_date)
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": str(exc)}), 500

    return jsonify(digest), 200


@bp.route("/weekly-digest/history", methods=["GET"])
def weekly_digest_history():
    """
    Retrieve stored weekly digest history for a user.

    Query parameters:
        user_id (int, required): The user whose history to fetch.
        limit   (int, optional): Maximum number of records to return (default 10).

    Returns:
        200 JSON list of digest objects on success.
        400 JSON error if user_id is missing or inputs are invalid.
    """
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    limit_str = request.args.get("limit", "10")
    try:
        limit = int(limit_str)
        if limit < 1:
            raise ValueError
    except ValueError:
        return jsonify({"error": "limit must be a positive integer"}), 400

    try:
        history = get_digest_history(int(user_id), limit)
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": str(exc)}), 500

    return jsonify(history), 200
