# scripts/app.py
from flask import Flask, request
from flask_cors import CORS
import time
from routes import bp as api_bp
from utils.logging import redact_pii

def create_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="change-me")
    CORS(app, resources={r"/*": {"origins": "*"}})

    @app.before_request
    def _start_timer():
        request._t0 = time.time()

    @app.after_request
    def _after(resp):
        try:
            dt = (time.time() - getattr(request, "_t0", time.time())) * 1000
            app.logger.info(redact_pii(f"{request.method} {request.path} {int(dt)}ms"))
        except Exception:
            pass
        return resp

    app.register_blueprint(api_bp, url_prefix="/api")
    return app

app = create_app()

if __name__ == "__main__":
    # 개발용 서버
    app.run(host="0.0.0.0", port=7860, debug=True)
