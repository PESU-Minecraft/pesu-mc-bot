from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "[HOST] Bot is online"


def run_webserver():
    app.run(host="0.0.0.0", port=7860)
