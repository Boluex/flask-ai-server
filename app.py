from flask import Flask, request, jsonify
import requests
import uuid
import subprocess
import os
import json as json_lib
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# === 🔐 CONFIGURATION ===
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Paths
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SERVER_DIR)
AI_BRAIN_SCRIPT = os.path.join(PROJECT_ROOT, "ai_repair_brain.py")
ACTION_PLAN_FILE = os.path.join(PROJECT_ROOT, "action_plan.json")


def supabase_get_token(token: str):
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
            headers=HEADERS,
            params={"select": "token,email,issue,active,expires_at,plan"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            return data[0] if data else None
        return None
    except Exception as e:
        print(f"Supabase GET error: {e}")
        return None


def supabase_update_session(token: str, data: dict):
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
            headers=HEADERS,
            json=data,
            timeout=10
        )
        return r.status_code in [200, 204]
    except Exception as e:
        print(f"Supabase UPDATE error: {e}")
        return False


def supabase_insert_session(data: dict):
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/sessions",
            headers=HEADERS,
            json=data,
            timeout=10
        )
        return r.status_code == 201
    except Exception as e:
        print(f"Supabase INSERT error: {e}")
        return False


@app.route('/generate-token', methods=['POST'])
def generate_token():
    email = request.json.get('email')
    issue = request.json.get('issue', 'Unknown issue')
    duration = int(request.json.get('minutes', 30))

    if not email or '@' not in email:
        return jsonify({"error": "Valid email required"}), 400

    raw_token = str(uuid.uuid4())[:8].upper()
    token = f"{raw_token[:4]}-{raw_token[4:]}"

    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=duration)).isoformat()

    payload = {
        "token": token,
        "email": email,
        "issue": issue,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
        "active": True,
        "plan": None
    }

    if supabase_insert_session(payload):
        return jsonify({
            "token": token,
            "expires_in": duration,
            "expires_at": expires_at
        })
    else:
        return jsonify({"error": "Failed to create session"}), 500


@app.route('/validate-token/<token>', methods=['GET'])
def validate_token(token):
    sess = supabase_get_token(token)
    if not sess:
        return jsonify({"valid": False, "error": "Invalid token"}), 404

    if not sess["active"]:
        return jsonify({"valid": False, "error": "Session inactive"}), 403

    try:
        exp_str = sess["expires_at"].strip()
        if exp_str.endswith('Z'):
            exp_str = exp_str[:-1] + '+00:00'
        exp = datetime.fromisoformat(exp_str)
        now_utc = datetime.now(timezone.utc)

        if now_utc > exp:
            supabase_update_session(token, {"active": False})
            return jsonify({"valid": False, "error": "Session expired"}), 403

        return jsonify({
            "valid": True,
            "email": sess["email"],
            "issue": sess["issue"],
            "expires_at": sess["expires_at"]
        })

    except Exception as e:
        print(f"Validation error: {e}")
        return jsonify({"valid": False, "error": "Invalid timestamp"}), 500


@app.route('/get-plan', methods=['GET'])
def get_plan():
    token = request.args.get('token')
    sess = supabase_get_token(token)
    if sess and sess["active"] and sess["plan"]:
        return jsonify(sess["plan"])
    return jsonify({}), 204


@app.route('/submit-issue', methods=['POST'])
def submit_issue():
    token = request.json.get('token')
    software = request.json.get('software', 'Unknown Software')
    issue = request.json.get('issue', '')
    ocr_text = request.json.get('ocr_text', '')

    sess = supabase_get_token(token)
    if not sess or not sess["active"]:
        return jsonify({"error": "Invalid or inactive session"}), 400

    input_text = ocr_text or issue
    if not input_text.strip():
        return jsonify({"error": "No issue description provided"}), 400

    try:
        result = subprocess.run(
            ["python", AI_BRAIN_SCRIPT, software, input_text],
            text=True,
            capture_output=True,
            timeout=30
        )

        if result.returncode != 0:
            print("AI script failed:", result.stderr)
            return jsonify({"error": "AI processing failed", "details": result.stderr}), 500

        if not os.path.exists(ACTION_PLAN_FILE):
            return jsonify({"error": "No repair plan generated by AI"}), 500

        with open(ACTION_PLAN_FILE, "r") as f:
            plan = json_lib.load(f)

        if supabase_update_session(token, {"plan": plan}):
            return jsonify({"status": "plan_generated", "plan": plan})
        else:
            return jsonify({"error": "Could not save plan to database"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))
