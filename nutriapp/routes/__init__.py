from flask import Flask


def register_blueprints(app: Flask) -> None:
    from . import auth, blog, clients, foods, main, plans, portal, recipes, settings, shopping

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(clients.bp)
    app.register_blueprint(plans.bp)
    app.register_blueprint(shopping.bp)
    app.register_blueprint(foods.bp)
    app.register_blueprint(recipes.bp)
    app.register_blueprint(blog.bp)
    app.register_blueprint(portal.bp)
    app.register_blueprint(settings.bp)
