#!/usr/bin/env python3
"""
AI Tech Repairer - Enhanced Backend with Analytics
Tracks: token generation, AI requests, errors, and agent downloads
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


# ============= ANALYTICS FUNCTIONS =============

def log_analytics_event(event_type: str, metadata: dict = None):
    """
    Log analytics events to Supabase
    
    Event types:
    - token_generated
    - ai_request_success
    - ai_request_error
    - agent_downloaded
    - session_expired
    - human_help_requested
    """
    try:
        payload = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "user_agent": request.headers.get('User-Agent', 'Unknown'),
            "ip_address": request.headers.get('X-Forwarded-For', request.remote_addr)
        }
        
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/analytics",
            headers=HEADERS,
            json=payload,
            timeout=5
        )
        
        if r.status_code == 201:
            print(f"✅ Analytics logged: {event_type}")
        else:
            print(f"⚠️ Analytics log failed: {r.status_code}")
            
    except Exception as e:
        print(f"❌ Analytics error: {e}")
        # Don't fail the main request if analytics fails


def get_analytics_summary(days: int = 7):
    """Get analytics summary for the last N days"""
    try:
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/analytics",
            headers=HEADERS,
            params={
                "timestamp": f"gte.{start_date}",
                "select": "event_type,timestamp,metadata",
                "order": "timestamp.desc",
                "limit": 1000
            },
            timeout=10
        )
        
        if r.status_code == 200:
            events = r.json()
            
            # Calculate metrics
            summary = {
                "total_events": len(events),
                "tokens_generated": len([e for e in events if e["event_type"] == "token_generated"]),
                "ai_requests": len([e for e in events if e["event_type"] in ["ai_request_success", "ai_request_error"]]),
                "ai_errors": len([e for e in events if e["event_type"] == "ai_request_error"]),
                "agent_downloads": len([e for e in events if e["event_type"] == "agent_downloaded"]),
                "human_help_requests": len([e for e in events if e["event_type"] == "human_help_requested"]),
                "error_rate": 0,
                "recent_errors": []
            }
            
            # Calculate error rate
            if summary["ai_requests"] > 0:
                summary["error_rate"] = round((summary["ai_errors"] / summary["ai_requests"]) * 100, 2)
            
            # Get recent error details
            error_events = [e for e in events if e["event_type"] == "ai_request_error"][:10]
            summary["recent_errors"] = [
                {
                    "timestamp": e["timestamp"],
                    "error": e["metadata"].get("error", "Unknown error"),
                    "issue": e["metadata"].get("issue", "N/A")
                }
                for e in error_events
            ]
            
            return summary
        
        return None
        
    except Exception as e:
        print(f"Error fetching analytics: {e}")
        return None


# ============= EXISTING HELPER FUNCTIONS =============

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
                "max_tokens": 2000,
                "response_format": {"type": "json_object"}
            },
            timeout=45
        )
        
        if resp.status_code != 200:
            print(f"❌ Mistral API error: {resp.status_code}")
            return {"error": f"Mistral API error: {resp.status_code}"}
        
        response_data = resp.json()
        text = response_data["choices"][0]["message"]["content"].strip()
        
        # Clean up response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        text = text.strip()
        
        try:
            plan = json.loads(text)
            return plan
        except json.JSONDecodeError:
            return {"error": "Failed to parse AI response"}
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {"error": f"Unexpected error: {str(e)}"}


def sanitize_plan(plan: dict, issue: str) -> dict:
    """Validate and sanitize the AI-generated plan"""
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except:
            return {
                "software": "Unknown",
                "issue": issue,
                "summary": "Failed to parse AI response",
                "steps": [{"description": "AI returned invalid format", "command": "echo Invalid response", "requires_sudo": False}],
                "estimated_time_minutes": 5,
                "needs_reboot": False
            }
    
    if "error" in plan:
        return {
            "software": "Unknown",
            "issue": issue,
            "summary": "AI service error",
            "steps": [{"description": plan["error"], "command": "echo AI error occurred", "requires_sudo": False}],
            "estimated_time_minutes": 5,
            "needs_reboot": False
        }
    
    sanitized = {
        "software": plan.get("software", "Unknown"),
        "issue": plan.get("issue", issue),
        "summary": plan.get("summary", "Repair steps"),
        "steps": [],
        "estimated_time_minutes": plan.get("estimated_time_minutes", 10),
        "needs_reboot": plan.get("needs_reboot", False)
    }
    
    raw_steps = plan.get("steps", [])
    if not raw_steps:
        sanitized["steps"] = [{
            "description": "No repair steps generated",
            "command": "echo No steps available",
            "requires_sudo": False
        }]
    else:
        for step in raw_steps[:6]:
            if isinstance(step, dict):
                command = str(step.get("command", "")).strip()
                if not command:
                    command = f"echo {step.get('description', 'Manual step')[:50]}"
                
                sanitized["steps"].append({
                    "description": str(step.get("description", "No description"))[:300],
                    "command": command[:500],
                    "requires_sudo": bool(step.get("requires_sudo", False))
                })
    
    return sanitized


def build_repair_prompt(issue: str, system_info: dict, search_results: list, file_info: dict = None) -> str:
    """Build the prompt for Mistral AI"""
    os_type = system_info.get('os', 'Windows')
    
    prompt = f"""
You are a computer repair technician AI. Generate a repair plan.

USER'S ISSUE: {issue}
SYSTEM: {os_type}

Output valid JSON:
{{
  "software": "name",
  "issue": "{issue}",
  "summary": "brief summary",
  "steps": [
    {{
      "description": "step description",
      "command": "actual command",
      "requires_sudo": true
    }}
  ],
  "estimated_time_minutes": 15,
  "needs_reboot": false
}}

Generate repair plan for: {issue}
"""
    return prompt


# ============= API ENDPOINTS =============

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
        # Log analytics event
        log_analytics_event("token_generated", {
            "token": token,
            "email": email,
            "duration_minutes": duration
        })
        
        return jsonify({
            "token": token,
            "expires_in": duration,
            "expires_at": expires_at
        })
    else:
        return jsonify({"error": "Failed to create session"}), 500


@app.route('/generate-plan', methods=['POST'])
def generate_plan():
    """Generate repair plan using Mistral AI"""
    token = request.json.get('token')
    issue = request.json.get('issue')
    system_info = request.json.get('system_info', {})
    search_results = request.json.get('search_results', [])
    file_info = request.json.get('file_info')
    
    if not token or not issue:
        return jsonify({"error": "Token and issue required"}), 400
    
    sess = supabase_get_token(token)
    if not sess or not sess["active"]:
        return jsonify({"error": "Invalid or inactive session"}), 401
    
    # Build and call AI
    prompt = build_repair_prompt(issue, system_info, search_results, file_info)
    raw_plan = call_mistral_ai(prompt)
    
    # Check for errors
    if "error" in raw_plan:
        # Log error analytics
        log_analytics_event("ai_request_error", {
            "token": token,
            "issue": issue,
            "error": raw_plan["error"],
            "os": system_info.get('os', 'Unknown')
        })
        
        return jsonify({
            "software": "Unknown",
            "issue": issue,
            "summary": "AI service error",
            "steps": [{"description": raw_plan["error"], "command": "echo Error occurred", "requires_sudo": False}],
            "estimated_time_minutes": 5,
            "needs_reboot": False
        })
    
    # Sanitize plan
    plan = sanitize_plan(raw_plan, issue)
    
    # Save to database
    supabase_update_session(token, {"plan": plan})
    
    # Log success analytics
    log_analytics_event("ai_request_success", {
        "token": token,
        "issue": issue,
        "software": plan.get("software", "Unknown"),
        "steps_count": len(plan.get("steps", [])),
        "os": system_info.get('os', 'Unknown')
    })
    
    return jsonify(plan)


@app.route('/track-download', methods=['POST'])
def track_download():
    """Track agent downloads"""
    download_type = request.json.get('type', 'unknown')  # 'windows', 'linux', 'macos'
    version = request.json.get('version', 'unknown')
    
    log_analytics_event("agent_downloaded", {
        "download_type": download_type,
        "version": version
    })
    
    return jsonify({"status": "tracked"})


@app.route('/analytics', methods=['GET'])
def get_analytics():
    """Get analytics dashboard data"""
    # Simple authentication (you should add proper auth)
    auth_key = request.args.get('key')
    if auth_key != os.getenv("ANALYTICS_KEY", "your-secret-key"):
        return jsonify({"error": "Unauthorized"}), 401
    
    days = int(request.args.get('days', 7))
    summary = get_analytics_summary(days)
    
    if summary:
        return jsonify(summary)
    else:
        return jsonify({"error": "Failed to fetch analytics"}), 500


@app.route('/request-human-help', methods=['POST'])
def request_human_help():
    """Send email alert to technician"""
    token = request.json.get('token')
    email = request.json.get('email')
    issue = request.json.get('issue')
    rdp_code = request.json.get('rdp_code')
    
    sess = supabase_get_token(token)
    if not sess or not sess["active"]:
        return jsonify({"error": "Invalid session"}), 401
    
    try:
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import smtplib
        
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
        """
        
        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, TECHNICIAN_EMAIL, msg.as_string())
        server.quit()
        
        # Log analytics
        log_analytics_event("human_help_requested", {
            "token": token,
            "email": email,
            "issue": issue
        })
        
        return jsonify({"status": "sent"})
        
    except Exception as e:
        print(f"Email error: {e}")
        return jsonify({"error": "Failed to send email"}), 500


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug)















































































# #!/usr/bin/env python3
# """
# AI Tech Repairer - Flask Backend Server
# Handles token validation, AI repair plan generation, and session management
# """

# from flask import Flask, request, jsonify
# import requests
# import uuid
# import os
# import json
# from datetime import datetime, timedelta, timezone
# from dotenv import load_dotenv

# app = Flask(__name__)
# load_dotenv()

# # Configuration
# SUPABASE_URL = os.getenv("SUPABASE_URL")  
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL", "oladejiolaoluwa46@gmail.com")
# GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
# GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# HEADERS = {
#     "apikey": SUPABASE_KEY,
#     "Authorization": f"Bearer {SUPABASE_KEY}",
#     "Content-Type": "application/json"
# }

# # Helper Functions
# def supabase_get_token(token: str):
#     """Fetch session data from Supabase"""
#     try:
#         r = requests.get(
#             f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
#             headers=HEADERS,
#             params={"select": "token,email,issue,active,expires_at,plan"},
#             timeout=10
#         )
#         if r.status_code == 200:
#             data = r.json()
#             return data[0] if data else None
#         return None
#     except Exception as e:
#         print(f"Supabase GET error: {e}")
#         return None


# def supabase_update_session(token: str, data: dict):
#     """Update session in Supabase"""
#     try:
#         r = requests.patch(
#             f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
#             headers=HEADERS,
#             json=data,
#             timeout=10
#         )
#         return r.status_code in [200, 204]
#     except Exception as e:
#         print(f"Supabase UPDATE error: {e}")
#         return False


# def supabase_insert_session(data: dict):
#     """Create new session in Supabase"""
#     try:
#         r = requests.post(
#             f"{SUPABASE_URL}/rest/v1/sessions",
#             headers=HEADERS,
#             json=data,
#             timeout=10
#         )
#         return r.status_code == 201
#     except Exception as e:
#         print(f"Supabase INSERT error: {e}")
#         return False




# def call_mistral_ai(prompt: str) -> dict:
#     """Call Mistral AI API with server-side key"""
#     try:
#         resp = requests.post(
#             "https://api.mistral.ai/v1/chat/completions",
#             headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
#             json={
#                 "model": "mistral-small-latest",
#                 "messages": [{"role": "user", "content": prompt}],
#                 "temperature": 0.3,
#                 "max_tokens": 2000,  # Increased from 1500
#                 "response_format": {"type": "json_object"}  # Force JSON response
#             },
#             timeout=45  # Increased timeout
#         )
        
#         if resp.status_code != 200:
#             print(f"❌ Mistral API error: {resp.status_code}")
#             print(f"Response: {resp.text}")
#             return {"error": f"Mistral API error: {resp.status_code}"}
        
#         response_data = resp.json()
#         if "choices" not in response_data or len(response_data["choices"]) == 0:
#             print(f"❌ Invalid Mistral response structure")
#             return {"error": "Invalid Mistral response"}
        
#         text = response_data["choices"][0]["message"]["content"].strip()
        
#         # Log the raw response for debugging
#         print(f"🤖 Mistral raw response (first 500 chars):\n{text[:500]}")
        
#         # Clean up the response - remove markdown code blocks
#         if "```json" in text:
#             text = text.split("```json")[1].split("```")[0]
#         elif "```" in text:
#             text = text.split("```")[1].split("```")[0]
        
#         text = text.strip()
        
#         # Try to find JSON object in the text
#         if not text.startswith("{"):
#             # Look for the first { and last }
#             start = text.find("{")
#             end = text.rfind("}")
#             if start != -1 and end != -1:
#                 text = text[start:end+1]
        
#         # Try to parse the JSON
#         try:
#             plan = json.loads(text)
#             print(f"✅ Successfully parsed JSON plan with {len(plan.get('steps', []))} steps")
#             return plan
#         except json.JSONDecodeError as e:
#             print(f"❌ JSON parse error: {e}")
#             print(f"Problematic text (first 300 chars): {text[:300]}")
            
#             # Try to fix common JSON issues
#             try:
#                 # Replace single quotes with double quotes
#                 text = text.replace("'", '"')
#                 # Remove trailing commas
#                 import re
#                 text = re.sub(r',(\s*[}\]])', r'\1', text)
#                 plan = json.loads(text)
#                 print(f"✅ Fixed and parsed JSON")
#                 return plan
#             except:
#                 print(f"❌ Could not fix JSON")
#                 return {"error": "Failed to parse AI response - invalid JSON format"}
            
#     except requests.exceptions.Timeout:
#         print(f"❌ Mistral API timeout")
#         return {"error": "Mistral API timeout"}
#     except Exception as e:
#         print(f"❌ Unexpected error: {e}")
#         import traceback
#         traceback.print_exc()
#         return {"error": f"Unexpected error: {str(e)}"}


# def sanitize_plan(plan: dict, issue: str) -> dict:
#     """Validate and sanitize the AI-generated plan"""
    
#     # If plan is still a string, try to parse it
#     if isinstance(plan, str):
#         try:
#             plan = json.loads(plan)
#         except:
#             return {
#                 "software": "Unknown",
#                 "issue": issue,
#                 "summary": "Failed to parse AI response",
#                 "steps": [{"description": "AI returned invalid format", "command": "echo Invalid response", "requires_sudo": False}],
#                 "estimated_time_minutes": 5,
#                 "needs_reboot": False
#             }
    
#     # Check for error in plan
#     if "error" in plan:
#         return {
#             "software": "Unknown",
#             "issue": issue,
#             "summary": "AI service error",
#             "steps": [{"description": plan["error"], "command": "echo AI error occurred", "requires_sudo": False}],
#             "estimated_time_minutes": 5,
#             "needs_reboot": False
#         }
    
#     # Ensure all required fields exist
#     sanitized = {
#         "software": plan.get("software", "Unknown"),
#         "issue": plan.get("issue", issue),
#         "summary": plan.get("summary", "Repair steps"),
#         "steps": [],
#         "estimated_time_minutes": plan.get("estimated_time_minutes", 10),
#         "needs_reboot": plan.get("needs_reboot", False)
#     }
    
#     # Validate and sanitize steps
#     raw_steps = plan.get("steps", [])
#     if not raw_steps:
#         sanitized["steps"] = [{
#             "description": "No repair steps generated",
#             "command": "echo No steps available",
#             "requires_sudo": False
#         }]
#     else:
#         for step in raw_steps[:6]:  # Max 6 steps
#             if isinstance(step, dict):
#                 # Ensure command is never empty
#                 command = str(step.get("command", "")).strip()
#                 if not command:
#                     command = f"echo {step.get('description', 'Manual step')[:50]}"
                
#                 sanitized["steps"].append({
#                     "description": str(step.get("description", "No description"))[:300],
#                     "command": command[:500],
#                     "requires_sudo": bool(step.get("requires_sudo", False))
#                 })
#             elif isinstance(step, str):
#                 # If step is just a string, make it a proper dict
#                 sanitized["steps"].append({
#                     "description": step[:300],
#                     "command": f"echo {step[:50]}",
#                     "requires_sudo": False
#                 })
    
#     # Validate numeric fields
#     try:
#         sanitized["estimated_time_minutes"] = max(1, min(120, int(sanitized["estimated_time_minutes"])))
#     except (ValueError, TypeError):
#         sanitized["estimated_time_minutes"] = 10
    
#     sanitized["needs_reboot"] = bool(sanitized.get("needs_reboot", False))
    
#     return sanitized





# def build_repair_prompt(issue: str, system_info: dict, search_results: list, file_info: dict = None) -> str:
#     """Build the prompt for Mistral AI"""
#     context = "\n".join([f"- {res}" for res in search_results if res and res.strip()])
#     if not context:
#         context = "No relevant online solutions found."
    
#     file_context = ""
#     if file_info and "error" not in file_info:
#         file_context = f"""
# Application File Information:
# - File: {file_info.get('filename', 'Unknown')}
# - Path: {file_info.get('path', 'Unknown')}
# - Directory: {file_info.get('directory', 'Unknown')}
# - Size: {file_info.get('size', 'Unknown')} bytes
# - Modified: {file_info.get('modified', 'Unknown')}
# """
#         if 'version' in file_info:
#             file_context += f"- Version: {file_info['version']}\n"
    
#     needs_reboot = any(kw in issue.lower() for kw in ['reboot', 'restart', 'shutdown', 'boot', 'startup'])
    
#     prompt = f"""
# You are a computer repair technician AI. You MUST respond with ONLY a valid JSON object, no other text.

# USER'S ISSUE: {issue}

# SYSTEM: {os_type} - {system_info.get('platform', 'Unknown')}

# SEARCH RESULTS: 
# {chr(10).join(f"- {result}" for result in search_results[:3]) if search_results else "None"}

# {f"FILE: {file_info.get('filename', 'N/A')} at {file_info.get('path', 'N/A')}" if file_info else ""}

# REQUIRED JSON OUTPUT FORMAT (respond with ONLY this, no markdown, no explanations):
# {{
#   "software": "software name",
#   "issue": "{issue}",
#   "summary": "Brief summary of repair approach",
#   "steps": [
#     {{
#       "description": "Step description",
#       "command": "exact command (never empty or null)",
#       "requires_sudo": true
#     }}
#   ],
#   "estimated_time_minutes": 15,
#   "needs_reboot": false
# }}

# COMMANDS FOR {os_type}:
# Windows:
# - ipconfig /flushdns (flush DNS, admin)
# - netsh winsock reset (reset network, admin)
# - sfc /scannow (system file check, admin)
# - cleanmgr /sagerun:1 (disk cleanup, admin)
# - defrag C: /O (defragment, admin)
# - del /q /f /s %TEMP%\\* (clear temp files)
# - net stop ServiceName (stop service, admin)
# - net start ServiceName (start service, admin)

# Linux:
# - sudo apt update && sudo apt upgrade -y
# - sudo systemctl restart service_name
# - sudo apt clean
# - sudo apt --fix-broken install

# RULES:
# 1. Respond with ONLY the JSON object
# 2. Every step MUST have a non-empty "command" field
# 3. If informational only, use: "echo Step information here"
# 4. Max 6 steps
# 5. Match commands to OS: {os_type}
# 6. Be specific and actionable

# Generate JSON for: {issue}
# """
    
#     return prompt




# # API Endpoints

# @app.route('/health', methods=['GET'])
# def health():
#     """Health check endpoint"""
#     return jsonify({
#         "status": "ok",
#         "time": datetime.now(timezone.utc).isoformat(),
#         "service": "AI Tech Repairer Backend"
#     })


# @app.route('/generate-token', methods=['POST'])
# def generate_token():
#     """Generate a new service token"""
#     email = request.json.get('email')
#     issue = request.json.get('issue', 'Unknown issue')
#     duration = int(request.json.get('minutes', 30))

#     if not email or '@' not in email:
#         return jsonify({"error": "Valid email required"}), 400

#     raw_token = str(uuid.uuid4())[:8].upper()
#     token = f"{raw_token[:4]}-{raw_token[4:]}"

#     expires_at = (datetime.now(timezone.utc) + timedelta(minutes=duration)).isoformat()

#     payload = {
#         "token": token,
#         "email": email,
#         "issue": issue,
#         "created_at": datetime.now(timezone.utc).isoformat(),
#         "expires_at": expires_at,
#         "active": True,
#         "plan": None
#     }

#     if supabase_insert_session(payload):
#         return jsonify({
#             "token": token,
#             "expires_in": duration,
#             "expires_at": expires_at
#         })
#     else:
#         return jsonify({"error": "Failed to create session"}), 500


# @app.route('/validate-token/<token>', methods=['GET'])
# def validate_token(token):
#     """Validate a service token"""
#     sess = supabase_get_token(token)
#     if not sess:
#         return jsonify({"valid": False, "error": "Invalid token"}), 404

#     if not sess["active"]:
#         return jsonify({"valid": False, "error": "Session inactive"}), 403

#     try:
#         exp_str = sess["expires_at"].strip()
#         if exp_str.endswith('Z'):
#             exp_str = exp_str[:-1] + '+00:00'
#         exp = datetime.fromisoformat(exp_str)
#         now_utc = datetime.now(timezone.utc)

#         if now_utc > exp:
#             supabase_update_session(token, {"active": False})
#             return jsonify({"valid": False, "error": "Session expired"}), 403

#         return jsonify({
#             "valid": True,
#             "email": sess["email"],
#             "issue": sess["issue"],
#             "expires_at": sess["expires_at"]
#         })

#     except Exception as e:
#         print(f"Validation error: {e}")
#         return jsonify({"valid": False, "error": "Invalid timestamp"}), 500



# @app.route('/generate-plan', methods=['POST'])
# def generate_plan():
#     """Generate repair plan using Mistral AI (server-side)"""
#     token = request.json.get('token')
#     issue = request.json.get('issue')
#     system_info = request.json.get('system_info', {})
#     search_results = request.json.get('search_results', [])
#     file_info = request.json.get('file_info')
    
#     if not token or not issue:
#         return jsonify({"error": "Token and issue required"}), 400
    
#     # Validate token
#     sess = supabase_get_token(token)
#     if not sess or not sess["active"]:
#         return jsonify({"error": "Invalid or inactive session"}), 401
    
#     # Check expiration
#     try:
#         exp_str = sess["expires_at"].strip()
#         if exp_str.endswith('Z'):
#             exp_str = exp_str[:-1] + '+00:00'
#         exp = datetime.fromisoformat(exp_str)
#         if datetime.now(timezone.utc) > exp:
#             return jsonify({"error": "Session expired"}), 403
#     except:
#         return jsonify({"error": "Invalid session data"}), 500
    
#     # Build enhanced prompt with explicit command requirements
#     os_type = system_info.get('os', 'Windows')
    
#     prompt = f"""
# You are a computer repair technician AI. Generate a detailed repair plan for this issue:

# **USER'S ISSUE**: {issue}

# **SYSTEM INFO**: {os_type} - {system_info.get('platform', 'Unknown')}

# **SEARCH RESULTS**: 
# {chr(10).join(f"- {result}" for result in search_results[:3])}

# {f"**FILE INFO**: {file_info.get('filename', 'N/A')} at {file_info.get('path', 'N/A')}" if file_info else ""}

# **CRITICAL REQUIREMENTS**:
# Each repair step MUST include:
# 1. "description": Clear description of what the step does
# 2. "command": The EXACT command to run (NEVER empty, NEVER null)
# 3. "requires_sudo": true if needs administrator/root privileges

# **OUTPUT FORMAT** (Valid JSON only):
# {{
#   "software": "Detected software name",
#   "issue": "{issue}",
#   "summary": "Brief 1-2 sentence summary of the repair approach",
#   "steps": [
#     {{
#       "description": "Step 1 description",
#       "command": "actual_command_here",
#       "requires_sudo": true
#     }},
#     {{
#       "description": "Step 2 description", 
#       "command": "another_command",
#       "requires_sudo": false
#     }}
#   ],
#   "estimated_time_minutes": 15,
#   "needs_reboot": false
# }}

# **COMMON COMMANDS FOR WINDOWS**:
# - Flush DNS: ipconfig /flushdns (admin required)
# - Reset Winsock: netsh winsock reset (admin required)
# - Reset TCP/IP: netsh int ip reset (admin required)
# - System File Check: sfc /scannow (admin required)
# - DISM Repair: DISM /Online /Cleanup-Image /RestoreHealth (admin required)
# - Disk Cleanup: cleanmgr /sagerun:1 (admin required)
# - Defragment: defrag C: /O (admin required)
# - Check Disk: chkdsk C: /f (admin required)
# - Clear Temp: del /q /f /s %TEMP%\\* (no admin)
# - Stop Service: net stop ServiceName (admin required)
# - Start Service: net start ServiceName (admin required)
# - Restart DNS Client: net stop Dnscache && net start Dnscache (admin required)

# **COMMON COMMANDS FOR LINUX**:
# - Update packages: sudo apt update && sudo apt upgrade -y
# - Restart service: sudo systemctl restart service_name
# - Clear cache: sudo apt clean
# - Fix broken packages: sudo apt --fix-broken install
# - Remove package: sudo apt remove package_name -y

# **COMMON COMMANDS FOR MACOS**:
# - Flush DNS: sudo dscacheutil -flushcache
# - Restart service: sudo launchctl restart service_name
# - Repair permissions: sudo diskutil resetUserPermissions / `id -u`

# **IMPORTANT**:
# - Every step MUST have a real command (never empty string or null)
# - If a step is informational only (like "Save your work"), use a command like "echo Informational step"
# - Match commands to the operating system: {os_type}
# - Set needs_reboot to true only if system restart is genuinely required
# - Prioritize executable commands over manual instructions

# Generate the complete JSON repair plan for: {issue}
# """
    
#     # Call Mistral AI
#     raw_plan = call_mistral_ai(prompt)
    
#     if "error" in raw_plan:
#         return jsonify({
#             "software": "Unknown",
#             "issue": issue,
#             "summary": "AI service error",
#             "steps": [{"description": raw_plan["error"], "command": "echo Error occurred", "requires_sudo": False}],
#             "estimated_time_minutes": 5,
#             "needs_reboot": False
#         })
    
#     # Sanitize and validate plan (ensure all commands are present)
#     plan = sanitize_plan(raw_plan, issue)
    
#     # Final validation: ensure no empty commands
#     if "steps" in plan:
#         for step in plan["steps"]:
#             if not step.get("command") or step.get("command").strip() == "":
#                 # Provide a default informational command
#                 step["command"] = f"echo {step.get('description', 'Manual step')}"
#                 step["requires_sudo"] = False
    
#     # Save to database
#     supabase_update_session(token, {"plan": plan})
    
#     return jsonify(plan)

# @app.route('/get-plan', methods=['GET'])
# def get_plan():
#     """Retrieve saved repair plan"""
#     token = request.args.get('token')
    
#     if not token:
#         return jsonify({"error": "Token required"}), 400
    
#     sess = supabase_get_token(token)
#     if sess and sess["active"] and sess["plan"]:
#         return jsonify(sess["plan"])
    
#     return jsonify({}), 204


# @app.route('/update-session', methods=['POST'])
# def update_session():
#     """Update session data"""
#     token = request.json.get('token')
#     updates = request.json.get('updates', {})
    
#     if not token:
#         return jsonify({"error": "Token required"}), 400
    
#     sess = supabase_get_token(token)
#     if not sess:
#         return jsonify({"error": "Invalid token"}), 404
    
#     if supabase_update_session(token, updates):
#         return jsonify({"status": "updated"})
#     else:
#         return jsonify({"error": "Update failed"}), 500



# @app.route('/request-human-help', methods=['POST'])
# def request_human_help():
#     """Send email alert to technician (server-side)"""
#     token = request.json.get('token')
#     email = request.json.get('email')
#     issue = request.json.get('issue')
#     rdp_code = request.json.get('rdp_code')
    
#     # Validate token
#     sess = supabase_get_token(token)
#     if not sess or not sess["active"]:
#         return jsonify({"error": "Invalid session"}), 401
    
#     try:
#         from email.mime.text import MIMEText
#         from email.mime.multipart import MIMEMultipart
#         import smtplib
        
#         GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
#         GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
#         TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL")
        
#         msg = MIMEMultipart()
#         msg["Subject"] = f"Human Help Requested - Token: {token}"
#         msg["From"] = GMAIL_ADDRESS
#         msg["To"] = TECHNICIAN_EMAIL
        
#         body = f"""
#         A user has requested live support.

#         Service Token: {token}
#         User Email: {email}
#         Issue: {issue}
#         RDP Code: {rdp_code}

#         Connect at: https://remotedesktop.google.com/access
#         Session expires in 15 minutes.
#         """
        
#         msg.attach(MIMEText(body, "plain"))
#         server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
#         server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
#         server.sendmail(GMAIL_ADDRESS, TECHNICIAN_EMAIL, msg.as_string())
#         server.quit()
        
#         return jsonify({"status": "sent"})
        
#     except Exception as e:
#         print(f"Email error: {e}")
#         return jsonify({"error": "Failed to send email"}), 500        
        


# if __name__ == '__main__':
#     port = int(os.getenv("PORT", 8080))
#     debug = os.getenv("DEBUG", "False").lower() == "true"
#     app.run(host='0.0.0.0', port=port, debug=debug)
