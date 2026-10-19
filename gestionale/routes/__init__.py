from flask import Flask


def register_blueprints(app: Flask) -> None:
    from . import (
        audit,
        auth,
        claims,
        clients,
        documents,
        followups,
        main,
        notifications,
        opportunities,
        policies,
        settings,
        sincronizzazione,
        titles,
        users,
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(clients.bp)
    app.register_blueprint(policies.bp)
    app.register_blueprint(titles.bp)
    app.register_blueprint(claims.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(followups.bp)
    app.register_blueprint(notifications.bp)
    app.register_blueprint(opportunities.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(audit.bp)
    app.register_blueprint(sincronizzazione.bp)
