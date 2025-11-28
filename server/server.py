import os
from flask import Flask, send_from_directory, abort
from globals.globalvariables import MUSIC_SHARE

app = Flask(__name__)

def get_mp3_files():
    return [
        f for f in os.listdir(MUSIC_SHARE)
        if f.lower().endswith(".mp3") and os.path.isfile(os.path.join(MUSIC_SHARE, f))
    ]

@app.route("/")
def index():
    files = get_mp3_files()
    html = "<h2>Dostępne pliki MP3</h2><ul>"
    for f in files:
        html += f'<li><a href="/track/{f}">{f}</a></li>'
    html += "</ul>"
    return html

@app.route("/track/<path:filename>")
def serve_mp3(filename):
    if filename not in get_mp3_files():
        return abort(404)
    return send_from_directory(MUSIC_SHARE, filename, mimetype="audio/mpeg")

@app.route("/<path:filename>")
def serve_mp3_root(filename):
    if filename not in get_mp3_files():
        return abort(404)
    return send_from_directory(MUSIC_SHARE, filename, mimetype="audio/mpeg")

def run_server():
    app.run(host="0.0.0.0", port=8080)