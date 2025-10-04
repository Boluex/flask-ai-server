#!/usr/bin/env python3
"""
AI Tech Repairer - Flask Backend Server
Handles token validation, AI repair plan generation, and session management
"""

from flask import Flask, request, jsonify
import requests
import uuid
import os
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")  
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL", "oladejiolaoluwa46@gmail.com")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Helper Functions
def supabase_get_token(token: str):
    """Fetch session data from Supabase"""
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
    """Update session in Supabase"""
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
    """Create new session in Supabase"""
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


def call_mistral_ai(prompt: str) -> dict:
    """Call Mistral AI API with server-side key"""
    try:
        resp = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1500
            },
            timeout=30
        )
        
        if resp.status_code != 200:
            return {"error": f"Mistral API error: {resp.status_code}"}
        
        response_data = resp.json()
        if "choices" not in response_data or len(response_data["choices"]) == 0:
            return {"error": "Invalid Mistral response"}
        
        text = response_data["choices"][0]["message"]["content"].strip()
        
        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            plan = json.loads(text)
            return plan
        except json.JSONDecodeError:
            return {"error": "Failed to parse AI response"}
            
    except requests.exceptions.Timeout:
        return {"error": "Mistral API timeout"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def build_repair_prompt(issue: str, system_info: dict, search_results: list, file_info: dict = None) -> str:
    """Build the prompt for Mistral AI"""
    context = "\n".join([f"- {res}" for res in search_results if res and res.strip()])
    if not context:
        context = "No relevant online solutions found."
    
    file_context = ""
    if file_info and "error" not in file_info:
        file_context = f"""
Application File Information:
- File: {file_info.get('filename', 'Unknown')}
- Path: {file_info.get('path', 'Unknown')}
- Directory: {file_info.get('directory', 'Unknown')}
- Size: {file_info.get('size', 'Unknown')} bytes
- Modified: {file_info.get('modified', 'Unknown')}
"""
        if 'version' in file_info:
            file_context += f"- Version: {file_info['version']}\n"
    
    needs_reboot = any(kw in issue.lower() for kw in ['reboot', 'restart', 'shutdown', 'boot', 'startup'])
    
    prompt = f"""You are a senior tech support engineer.
Generate a safe, step-by-step repair plan for: "{issue}"

System Info: {system_info.get('os', 'Unknown')} ({system_info.get('platform', 'Unknown')})

{file_context}

Relevant fixes from online research:
{context}

CRITICAL: Return ONLY valid JSON in this EXACT format with NO extra text:
{{
  "software": "software name or Unknown",
  "issue": "{issue}",
  "summary": "One-line summary of the repair plan",
  "steps": [
    {{
      "description": "Clear description of what this step does",
      "command": "exact shell command to run OR empty string if manual step",
      "requires_sudo": true or false
    }}
  ],
  "critical": true or false,
  "estimated_time_minutes": number,
  "needs_reboot": {str(needs_reboot).lower()}
}}

IMPORTANT RULES:
1. Maximum 6 steps
2. Each step MUST have "description", "command", and "requires_sudo" fields
3. For commands that might fail safely (like pkill), add "|| true" at the end
4. Use SIMPLE commands - avoid complex shell pipelines with nested quotes
5. For checking missing libraries, use: ldd /path/to/binary 2>/dev/null || echo No issues found
6. If a step is manual (like "restart the application"), set command to empty string ""
7. Be concise but specific
8. Avoid destructive commands
9. Return ONLY the JSON object, no markdown formatting, no extra text"""
    
    return prompt


def sanitize_plan(plan: dict, issue: str) -> dict:
    """Validate and sanitize the AI-generated plan"""
    required_fields = ["summary", "steps", "estimated_time_minutes", "needs_reboot"]
    for field in required_fields:
        if field not in plan:
            return {
                "software": "Unknown",
                "issue": issue,
                "summary": "Incomplete AI response",
                "steps": [{"description": "AI response missing required information.", "command": "", "requires_sudo": False}],
                "estimated_time_minutes": 5,
                "needs_reboot": False
            }
    
    # Ensure required fields exist
    if "software" not in plan:
        plan["software"] = "Unknown"
    if "issue" not in plan:
        plan["issue"] = issue
    
    # Sanitize fields
    plan["software"] = str(plan["software"])[:100]
    plan["issue"] = str(plan["issue"])[:200]
    plan["summary"] = str(plan["summary"])[:200]
    
    # Validate steps
    if not isinstance(plan["steps"], list):
        plan["steps"] = [{"description": "Invalid step format", "command": "", "requires_sudo": False}]
    else:
        sanitized_steps = []
        for step in plan["steps"][:6]:
            if isinstance(step, dict):
                sanitized_step = {
                    "description": str(step.get("description", "No description"))[:300],
                    "command": str(step.get("command", ""))[:500],
                    "requires_sudo": bool(step.get("requires_sudo", False))
                }
                sanitized_steps.append(sanitized_step)
        
        if not sanitized_steps:
            sanitized_steps = [{"description": "No valid steps received", "command": "", "requires_sudo": False}]
        
        plan["steps"] = sanitized_steps
    
    # Validate numeric fields
    try:
        plan["estimated_time_minutes"] = max(1, min(120, int(plan["estimated_time_minutes"])))
    except (ValueError, TypeError):
        plan["estimated_time_minutes"] = 10
    
    plan["needs_reboot"] = bool(plan.get("needs_reboot", False))
    plan["critical"] = bool(plan.get("critical", False))
    
    return plan


# API Endpoints

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "service": "AI Tech Repairer Backend"
    })


@app.route('/generate-token', methods=['POST'])
def generate_token():
    """Generate a new service token"""
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
    """Validate a service token"""
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


@app.route('/generate-plan', methods=['POST'])
def generate_plan():
    """Generate repair plan using Mistral AI (server-side)"""
    token = request.json.get('token')
    issue = request.json.get('issue')
    system_info = request.json.get('system_info', {})
    search_results = request.json.get('search_results', [])
    file_info = request.json.get('file_info')
    
    if not token or not issue:
        return jsonify({"error": "Token and issue required"}), 400
    
    # Validate token
    sess = supabase_get_token(token)
    if not sess or not sess["active"]:
        return jsonify({"error": "Invalid or inactive session"}), 401
    
    # Check expiration
    try:
        exp_str = sess["expires_at"].strip()
        if exp_str.endswith('Z'):
            exp_str = exp_str[:-1] + '+00:00'
        exp = datetime.fromisoformat(exp_str)
        if datetime.now(timezone.utc) > exp:
            return jsonify({"error": "Session expired"}), 403
    except:
        return jsonify({"error": "Invalid session data"}), 500
    
    # Build prompt and call Mistral
    prompt = build_repair_prompt(issue, system_info, search_results, file_info)
    raw_plan = call_mistral_ai(prompt)
    
    if "error" in raw_plan:
        return jsonify({
            "software": "Unknown",
            "issue": issue,
            "summary": "AI service error",
            "steps": [{"description": raw_plan["error"], "command": "", "requires_sudo": False}],
            "estimated_time_minutes": 5,
            "needs_reboot": False
        })
    
    # Sanitize and validate plan
    plan = sanitize_plan(raw_plan, issue)
    
    # Save to database
    supabase_update_session(token, {"plan": plan})
    
    return jsonify(plan)


@app.route('/get-plan', methods=['GET'])
def get_plan():
    """Retrieve saved repair plan"""
    token = request.args.get('token')
    
    if not token:
        return jsonify({"error": "Token required"}), 400
    
    sess = supabase_get_token(token)
    if sess and sess["active"] and sess["plan"]:
        return jsonify(sess["plan"])
    
    return jsonify({}), 204


@app.route('/update-session', methods=['POST'])
def update_session():
    """Update session data"""
    token = request.json.get('token')
    updates = request.json.get('updates', {})
    
    if not token:
        return jsonify({"error": "Token required"}), 400
    
    sess = supabase_get_token(token)
    if not sess:
        return jsonify({"error": "Invalid token"}), 404
    
    if supabase_update_session(token, updates):
        return jsonify({"status": "updated"})
    else:
        return jsonify({"error": "Update failed"}), 500



@app.route('/request-human-help', methods=['POST'])
def request_human_help():
    """Send email alert to technician (server-side)"""
    token = request.json.get('token')
    email = request.json.get('email')
    issue = request.json.get('issue')
    rdp_code = request.json.get('rdp_code')
    
    # Validate token
    sess = supabase_get_token(token)
    if not sess or not sess["active"]:
        return jsonify({"error": "Invalid session"}), 401
    
    try:
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import smtplib
        
        GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
        GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
        TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL")
        
        msg = MIMEMultipart()
        msg["Subject"] = f"Human Help Requested - Token: {token}"
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = TECHNICIAN_EMAIL
        
        body = f"""
        A user has requested live support.

        Service Token: {token}
        User Email: {email}
        Issue: {issue}
        RDP Code: {rdp_code}

        Connect at: https://remotedesktop.google.com/access
        Session expires in 15 minutes.
        """
        
        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, TECHNICIAN_EMAIL, msg.as_string())
        server.quit()
        
        return jsonify({"status": "sent"})
        
    except Exception as e:
        print(f"Email error: {e}")
        return jsonify({"error": "Failed to send email"}), 500        
        


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug)
