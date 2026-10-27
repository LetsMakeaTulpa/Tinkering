import os

from flask import Flask, jsonify, render_template

from chat_app import db
from chat_app.api import api


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    db.init_db()
    app.register_blueprint(api)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/share/<share_id>")
    def share_view(share_id):
        chat = db.get_chat_by_share(share_id)
        if not chat:
            return jsonify({"error": "not_found"}), 404
        chat["messages"] = db.list_messages(chat["id"])
        return render_template("share.html", chat_json=chat)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port)
