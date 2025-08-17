from flask import Flask
from db import db   # import shared db instance
import os, importlib

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # Register blueprints dynamically
    routes_folder = os.path.join(os.path.dirname(__file__), "routes")
    for filename in os.listdir(routes_folder):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = f"routes.{filename[:-3]}"
            module = importlib.import_module(module_name)
            if hasattr(module, "bp"):
                app.register_blueprint(module.bp)

    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)
