"""
Fake Message Board — minimal demo app for crawler testing.

Endpoints:
  POST /messages   -> post a new message   (JSON body: {"sender": "...", "msg": "..."})
  GET  /messages    -> get all messages     (returns JSON array)

Extra (not required, but gives the crawler an actual page to walk, and
gives a human a basic frontend to look at):
  GET  /            -> HTML page listing all messages, newest first,
                       rendered server-side (so it's visible to a crawler
                       that just fetches HTML, no JS execution needed)

Storage is in-memory only (a Python list), preseeded with a handful of
hardcoded fake messages from made-up accounts so there's content to
crawl immediately on startup. Restarting the app resets to just the
seed data.

Message format is simple and literal, as requested:
    sender : <name>
    msg    : <text>
"""

from flask import Flask, request, jsonify, render_template_string, redirect
from datetime import datetime, timezone
from itertools import count

app = Flask(__name__)

# --- storage -----------------------------------------------------------
_id_counter = count(1)


def _seed_message(sender, msg):
    return {
        "id": next(_id_counter),
        "sender": sender,
        "msg": msg,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# Hardcoded preseeded messages from random fake accounts, so the board
# isn't empty and the crawler has something to find right away.
messages = [
    _seed_message("random_wanderer_92", "just testing this thing out, ignore me"),
    _seed_message("night_owl_47", "does anyone actually read this board lol"),
    _seed_message("papercut_dev", "shipped a small fix today, feels good"),
    _seed_message("ghost_of_ct", "coffee > tea, fight me"),
    _seed_message("quiet_signal", "first post, be nice"),
]

# --- HTML page (for the crawler + humans to look at) --------------------
PAGE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Fake Message Board</title>
  <style>
    body { font-family: sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; color: #222; }
    h1 { margin-bottom: 4px; }
    .count { color: #666; margin-top: 0; }
    .message { border: 1px solid #ddd; border-radius: 6px; padding: 10px 14px; margin-bottom: 10px; }
    .message .line { margin: 2px 0; }
    .label { color: #888; }
    form { margin-top: 24px; border-top: 1px solid #ddd; padding-top: 16px; }
    input, textarea { width: 100%; padding: 8px; margin: 4px 0 12px; box-sizing: border-box; }
    button { padding: 8px 16px; cursor: pointer; }
  </style>
</head>
<body>
  <h1>Fake Message Board</h1>
  <p class="count">{{ count }} message(s)</p>

  <div id="messages">
    {% for m in messages %}
    <div class="message" id="message-{{ m.id }}">
      <div class="line"><span class="label">sender :</span> {{ m.sender }}</div>
      <div class="line"><span class="label">msg :</span> {{ m.msg }}</div>
    </div>
    {% endfor %}
  </div>

  <form method="post" action="/messages" enctype="application/x-www-form-urlencoded">
    <label>sender</label>
    <input type="text" name="sender" placeholder="your name" required>
    <label>msg</label>
    <textarea name="msg" placeholder="your message" required></textarea>
    <button type="submit">Post</button>
  </form>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(
        PAGE_TEMPLATE,
        messages=list(reversed(messages)),
        count=len(messages),
    )


@app.route("/messages", methods=["POST"])
def post_message():
    # Accept either JSON body or form-encoded body (so the HTML form works too)
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    sender = (data.get("sender") or "anonymous").strip()
    msg = (data.get("msg") or "").strip()

    if not msg:
        return jsonify({"error": "msg is required"}), 400

    message = _seed_message(sender, msg)
    messages.append(message)

    if not request.is_json:
        return redirect("/", code=303)

    return jsonify(message), 201


@app.route("/messages", methods=["GET"])
def get_messages():
    return jsonify(messages)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)