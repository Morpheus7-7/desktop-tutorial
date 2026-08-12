"""Centro notifiche."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models import Notification, db

bp = Blueprint("notifications", __name__, url_prefix="/notifiche")


@bp.route("/")
def list_notifications():
    solo_non_lette = request.args.get("filtro", "non_lette") == "non_lette"
    query = Notification.query
    if solo_non_lette:
        query = query.filter_by(letta=False)
    notifiche = query.order_by(Notification.created_at.desc()).limit(200).all()
    return render_template(
        "notifications/list.html",
        notifiche=notifiche,
        solo_non_lette=solo_non_lette,
    )


@bp.route("/<int:notification_id>/letta", methods=["POST"])
def mark_read(notification_id):
    n = db.get_or_404(Notification, notification_id)
    n.letta = True
    db.session.commit()
    return redirect(request.form.get("next") or url_for("notifications.list_notifications"))


@bp.route("/segna-tutte-lette", methods=["POST"])
def mark_all_read():
    Notification.query.filter_by(letta=False).update({"letta": True})
    db.session.commit()
    flash("Tutte le notifiche sono state segnate come lette.", "success")
    return redirect(url_for("notifications.list_notifications"))
