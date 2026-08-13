from flask import Flask


def register_blueprints(app: Flask) -> None:
    from . import (
        clients,
        documents,
        followups,
        main,
        notifications,
        opportunities,
        policies,
        settings,
    )

    app.register_blueprint(main.bp)
    app.register_blueprint(clients.bp)
    app.register_blueprint(policies.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(followups.bp)
    app.register_blueprint(notifications.bp)
    app.register_blueprint(opportunities.bp)
    app.register_blueprint(settings.bp)
