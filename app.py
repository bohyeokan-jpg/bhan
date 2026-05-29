from flask import Flask, render_template, request, jsonify, session
import json
import os

app = Flask(__name__)
app.secret_key = "schedule-secret-key-2024"

BASE_DIR = os.environ.get("DATA_DIR", ".")


def data_file(user):
    return os.path.join(BASE_DIR, f"schedules_{user}.json")


def load(user):
    f = data_file(user)
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return []


def save(user, data):
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(data_file(user), "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/login", methods=["POST"])
def login():
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "이름을 입력하세요."})
    session["user"] = name
    return jsonify({"ok": True, "user": name})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def me():
    return jsonify({"user": session.get("user")})


def settings_file(user):
    return os.path.join(BASE_DIR, f"settings_{user}.json")


def load_settings(user):
    f = settings_file(user)
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return {"theme": "blue"}


def save_settings(user, data):
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(settings_file(user), "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False)


@app.route("/api/settings")
def get_settings():
    user = session.get("user")
    if not user:
        return jsonify({"theme": "blue"})
    return jsonify(load_settings(user))


@app.route("/api/settings", methods=["POST"])
def update_settings():
    user = session.get("user")
    if not user:
        return jsonify({"error": "로그인 필요"}), 401
    s = load_settings(user)
    s.update(request.json)
    save_settings(user, s)
    return jsonify({"ok": True})


@app.route("/api/schedules")
def get_schedules():
    user = session.get("user")
    if not user:
        return jsonify([])
    return jsonify(load(user))


@app.route("/api/schedules", methods=["POST"])
def add_schedule():
    user = session.get("user")
    if not user:
        return jsonify({"error": "로그인 필요"}), 401
    data = load(user)
    item = request.json
    item["id"] = f"{item['date']}_{item['time']}_{len(data)}"
    item["notified"] = False
    data.append(item)
    save(user, data)
    return jsonify(item)


@app.route("/api/schedules/<sid>", methods=["DELETE"])
def delete_schedule(sid):
    user = session.get("user")
    if not user:
        return jsonify({"error": "로그인 필요"}), 401
    data = [s for s in load(user) if s["id"] != sid]
    save(user, data)
    return jsonify({"ok": True})


@app.route("/api/backup/export")
def export_backup():
    from flask import Response
    user = session.get("user")
    if not user:
        return jsonify({"error": "로그인 필요"}), 401
    data = load(user)
    filename = f"schedule_backup_{user}_{__import__('datetime').date.today()}.json"
    return Response(
        json.dumps({"user": user, "schedules": data}, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{__import__('urllib.parse', fromlist=['quote']).parse.quote(filename)}"}
    )


@app.route("/api/backup/import", methods=["POST"])
def import_backup():
    user = session.get("user")
    if not user:
        return jsonify({"error": "로그인 필요"}), 401
    try:
        backup = request.json
        imported = backup.get("schedules", [])
        existing = load(user)
        existing_ids = {s["id"] for s in existing}
        added = 0
        for s in imported:
            if s.get("id") not in existing_ids:
                existing.append(s)
                added += 1
        save(user, existing)
        return jsonify({"ok": True, "added": added, "total": len(existing)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
