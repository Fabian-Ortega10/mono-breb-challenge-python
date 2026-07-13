import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from .config import config
from .routes.collections import bp as collections_bp
from .routes.transfers import bp as transfers_bp
from .routes.webhooks import bp as webhooks_bp

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")


def create_app() -> Flask:
    app = Flask(__name__, static_folder=PUBLIC_DIR, static_url_path="")
    CORS(app)

    app.register_blueprint(collections_bp)
    app.register_blueprint(transfers_bp)
    app.register_blueprint(webhooks_bp)

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "ok": True,
                "tenant_account_configured": bool(config.TENANT_ACCOUNT_ID),
                "base_url": config.BASE_URL,
            }
        )

    @app.get("/")
    def index():
        return send_from_directory(PUBLIC_DIR, "index.html")

    @app.errorhandler(Exception)
    def handle_unexpected_error(err):
        if isinstance(err, HTTPException):
            # Deja pasar 404/405/etc. con su comportamiento normal.
            return err
        app.logger.exception("Unhandled error")
        return jsonify({"error": {"message": "Error interno del servidor"}}), 500

    return app


app = create_app()

if __name__ == "__main__":
    if not config.CLIENT_ID or not config.CLIENT_SECRET:
        print(
            "AVISO: MONO_CLIENT_ID / MONO_CLIENT_SECRET no estan configurados. "
            "Copia .env.example a .env y completa las credenciales del Sandbox."
        )
    print(f"Mono Bre-B challenge server escuchando en http://localhost:{config.PORT}")
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
