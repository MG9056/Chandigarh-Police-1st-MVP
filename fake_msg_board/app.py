"""
Fake Message Board — minimal demo app for crawler testing.

Endpoints:
  POST /messages   -> post a new message   (JSON body: {"sender": "...", "msg": "..."})
  GET  /messages    -> get all messages     (returns JSON array)
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
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Signal Board</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07111d;
      --panel: rgba(13, 29, 47, .88);
      --panel-soft: rgba(17, 39, 62, .76);
      --border: rgba(121, 191, 255, .18);
      --text: #e7f1ff;
      --muted: #91a8c1;
      --accent: #37b5ff;
      --accent-strong: #087fc5;
      --glow: rgba(55, 181, 255, .28);
    }

    * { box-sizing: border-box; }
    body {
      min-height: 100vh;
      margin: 0;
      padding: 44px 20px;
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 15% 0%, rgba(19, 104, 173, .25), transparent 32rem),
        radial-gradient(circle at 90% 15%, rgba(35, 161, 223, .12), transparent 25rem),
        var(--bg);
    }
    .shell { width: min(780px, 100%); margin: 0 auto; }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 22px;
    }
    .brand { display: flex; align-items: center; gap: 13px; }
    .mark {
      display: grid;
      width: 43px;
      height: 43px;
      place-items: center;
      border: 1px solid rgba(80, 195, 255, .5);
      border-radius: 13px;
      color: #bde9ff;
      background: linear-gradient(145deg, #144d79, #0b2036);
      box-shadow: 0 0 24px var(--glow);
      font-size: 19px;
    }
    h1 { margin: 0; font-size: clamp(1.5rem, 4vw, 2.05rem); letter-spacing: -.035em; }
    .subtitle { margin: 3px 0 0; color: var(--muted); font-size: .88rem; }
    .count {
      margin: 0;
      padding: 8px 11px;
      border: 1px solid var(--border);
      border-radius: 999px;
      color: #b7d4ee;
      background: rgba(13, 38, 61, .7);
      font-size: .78rem;
      font-weight: 700;
      white-space: nowrap;
    }
    .board {
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: var(--panel);
      box-shadow: 0 22px 70px rgba(0, 0, 0, .24);
      backdrop-filter: blur(12px);
    }
    .board-label {
      display: flex;
      align-items: center;
      gap: 9px;
      padding: 15px 20px;
      border-bottom: 1px solid var(--border);
      color: #aac7e1;
      font-size: .7rem;
      font-weight: 800;
      letter-spacing: .13em;
      text-transform: uppercase;
    }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: #39da9e; box-shadow: 0 0 10px #39da9e; }
    #messages { padding: 10px; }
    .message {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 12px;
      padding: 14px;
      border: 1px solid transparent;
      border-radius: 12px;
      transition: background .18s ease, border-color .18s ease, transform .18s ease;
    }
    .message:hover { border-color: var(--border); background: var(--panel-soft); transform: translateX(2px); }
    .avatar {
      display: grid;
      width: 34px;
      height: 34px;
      place-items: center;
      border-radius: 10px;
      color: #a9e1ff;
      background: #123957;
      font-size: .78rem;
      font-weight: 800;
    }
    .sender { color: #b8dbf7; font-size: .83rem; font-weight: 750; }
    .message-text { margin: 5px 0 0; color: #eef6ff; line-height: 1.5; overflow-wrap: anywhere; }
    .composer {
      margin-top: 18px;
      padding: 20px;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: var(--panel);
      box-shadow: 0 14px 45px rgba(0, 0, 0, .16);
    }
    .composer-title { margin: 0 0 16px; color: #cbe7fb; font-size: .82rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
    label { display: block; margin: 0 0 6px; color: var(--muted); font-size: .76rem; font-weight: 700; }
    input, textarea {
      width: 100%;
      margin: 0 0 14px;
      padding: 11px 12px;
      border: 1px solid rgba(133, 190, 235, .18);
      border-radius: 10px;
      outline: none;
      resize: vertical;
      color: var(--text);
      background: rgba(4, 18, 31, .65);
      font: inherit;
      transition: border-color .18s ease, box-shadow .18s ease;
    }
    textarea { min-height: 92px; }
    input::placeholder, textarea::placeholder { color: #66819d; }
    input:focus, textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--glow); }
    button {
      padding: 10px 15px;
      border: 1px solid #48c0ff;
      border-radius: 10px;
      color: #effaff;
      cursor: pointer;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      box-shadow: 0 7px 19px rgba(8, 127, 197, .28);
      font: inherit;
      font-size: .87rem;
      font-weight: 800;
      transition: filter .18s ease, transform .18s ease;
    }
    button:hover { filter: brightness(1.1); transform: translateY(-1px); }
    @media (max-width: 520px) { body { padding: 24px 14px; } .topbar { align-items: flex-start; } .count { margin-top: 5px; } }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark">✦</div>
        <div><h1>Signal Board</h1><p class="subtitle">A simple public message stream</p></div>
      </div>
      <p class="count">{{ count }} message{{ '' if count == 1 else 's' }}</p>
    </header>

    <section class="board">
      <div class="board-label"><span class="status-dot"></span> Live feed · newest first</div>
      <div id="messages">
        {% for m in messages %}
        <article class="message" id="message-{{ m.id }}">
          <div class="avatar">{{ m.sender[:1]|upper }}</div>
          <div><div class="sender">{{ m.sender }}</div><p class="message-text">{{ m.msg }}</p></div>
        </article>
        {% endfor %}
      </div>
    </section>

    <form class="composer" method="post" action="/messages" enctype="application/x-www-form-urlencoded">
      <p class="composer-title">Add a message</p>
      <label for="sender">Sender</label>
      <input id="sender" type="text" name="sender" placeholder="your name" required>
      <label for="msg">Message</label>
      <textarea id="msg" name="msg" placeholder="share something with the board" required></textarea>
      <button type="submit">Post message</button>
    </form>
  </main>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE_TEMPLATE, messages=list(reversed(messages)), count=len(messages))


@app.route("/messages", methods=["POST"])
def post_message():
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
