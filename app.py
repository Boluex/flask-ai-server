#!/usr/bin/env python3
"""
AI Tech Repairer - Backend with Complete Security
Ready to deploy - Just copy and paste!
"""

from flask import Flask, request, jsonify
import requests
import uuid
import os
import json
import csv
import threading
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask_cors import CORS
import resend
from functools import wraps
from collections import defaultdict
import time
import secrets

app = Flask(__name__)

load_dotenv()

# CORS Configuration - Separate for dev and production
if os.getenv("FLASK_ENV") == "production":
    CORS(app, 
         origins=["https://techfix-frontend-nc49.onrender.com"],
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "OPTIONS"],
         supports_credentials=True,
         max_age=3600
    )
else:
    CORS(app, 
         origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080"   
         ],
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
         supports_credentials=True,
         max_age=3600
    )

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")  
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# Initialize Resend
resend.api_key = RESEND_API_KEY

# Headers for Supabase
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Security storage
rate_limit_storage = defaultdict(list)
failed_attempts = defaultdict(list)
RATE_LIMIT = 5
RATE_LIMIT_WINDOW = 60
FAILED_ATTEMPT_THRESHOLD = 10
FAILED_ATTEMPT_WINDOW = 300

print("\n" + "="*60)
print("BACKEND STARTUP - Environment Check")
print("="*60)
print(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
print(f"SUPABASE_URL loaded: {bool(SUPABASE_URL)}")
print(f"SUPABASE_KEY loaded: {bool(SUPABASE_KEY)}")
print(f"MISTRAL_API_KEY loaded: {bool(MISTRAL_API_KEY)}")
print(f"RESEND_API_KEY loaded: {bool(RESEND_API_KEY)}")
print(f"TECHNICIAN_EMAIL: {TECHNICIAN_EMAIL}")
print("="*60 + "\n")


# ============= SECURITY FUNCTIONS =============

def get_client_ip():
    """Get real client IP even behind proxies"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr or '0.0.0.0'

def rate_limit(f):
    """Rate limiting decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = get_client_ip()
        current_time = time.time()
        
        # Clean old entries
        rate_limit_storage[client_ip] = [
            req_time for req_time in rate_limit_storage[client_ip]
            if current_time - req_time < RATE_LIMIT_WINDOW
        ]
        
        # Check rate limit
        if len(rate_limit_storage[client_ip]) >= RATE_LIMIT:
            obfuscate_response()
            return jsonify({
                "error": "Too many requests. Please try again later.",
                "retry_after": 60
            }), 429
        
        # Add current request
        rate_limit_storage[client_ip].append(current_time)
        
        return f(*args, **kwargs)
    return decorated_function

def obfuscate_response():
    """Add random noise to response timing to prevent timing attacks"""
    time.sleep(secrets.randbelow(100) / 1000)

def validate_email(email):
    """Validate email format"""
    if not email or '@' not in email or '.' not in email:
        return False
    if len(email) > 254:
        return False
    if any(c in email for c in [' ', '"', "'", '<', '>', ';']):
        return False
    return True

def sanitize_string(text, max_length=500):
    """Sanitize user input"""
    if not text:
        return ""
    text = str(text).strip()
    dangerous_chars = ['<', '>', '"', "'", ';', '&', '|', '`']
    for char in dangerous_chars:
        text = text.replace(char, '')
    return text[:max_length]

def track_failed_attempt(identifier=None):
    """Track failed attempts"""
    if identifier is None:
        identifier = get_client_ip()
    
    current_time = time.time()
    failed_attempts[identifier] = [
        t for t in failed_attempts[identifier]
        if current_time - t < FAILED_ATTEMPT_WINDOW
    ]
    failed_attempts[identifier].append(current_time)
    
    if len(failed_attempts[identifier]) >= FAILED_ATTEMPT_THRESHOLD:
        print(f"⚠️ SECURITY ALERT: Too many failed attempts from {identifier}")
        return True
    return False

def is_ip_blocked(identifier=None):
    """Check if IP is blocked"""
    if identifier is None:
        identifier = get_client_ip()
    
    current_time = time.time()
    failed_attempts[identifier] = [
        t for t in failed_attempts[identifier]
        if current_time - t < FAILED_ATTEMPT_WINDOW
    ]
    return len(failed_attempts[identifier]) >= FAILED_ATTEMPT_THRESHOLD


# ============= EMAIL FUNCTIONS =============

def send_email_with_resend(to_email: str, subject: str, body: str):
    """Send email using Resend library"""
    print(f"\n📧 [EMAIL] Sending to {to_email}")
    print(f"   Subject: {subject}")
    
    try:
        params = {
            "from": "TechFix AI <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": body
        }
        
        email = resend.Emails.send(params)
        
        print(f"✅ [EMAIL SUCCESS] Email sent to {to_email}")
        print(f"   Email ID: {email.get('id', 'N/A')}")
        return True
            
    except Exception as e:
        print(f"❌ [EMAIL ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def send_email_async(to_email: str, subject: str, body: str):
    """Send email in background thread"""
    def _send():
        print(f"\n📧 [THREAD START] Email thread started")
        success = send_email_with_resend(to_email, subject, body)
        if success:
            print(f"✅ [THREAD END] Email sent successfully")
        else:
            print(f"❌ [THREAD END] Email failed")
    
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
    print(f"📧 [ASYNC] Email background thread started for {to_email}")


def send_help_request_email(token: str, user_email: str, issue: str, rdp_code: str):
    """Send help request to technician via email"""
    print(f"\n🚀 [HELP REQUEST] Initiating email to technician")
    print(f"   To: {TECHNICIAN_EMAIL}")
    print(f"   Token: {token}")
    
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4CAF50; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
            .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
            .info-row {{ margin: 10px 0; }}
            .label {{ font-weight: bold; color: #555; }}
            .button {{ 
                display: inline-block;
                background: #4CAF50;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 15px;
            }}
            .footer {{ margin-top: 20px; padding: 10px; text-align: center; color: #777; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>🆘 Help Request Received</h2>
            </div>
            <div class="content">
                <div class="info-row">
                    <span class="label">Service Token:</span> {token}
                </div>
                <div class="info-row">
                    <span class="label">User Email:</span> {user_email}
                </div>
                <div class="info-row">
                    <span class="label">Issue:</span> {issue}
                </div>
                <div class="info-row">
                    <span class="label">Chrome Remote Desktop Code:</span> <code style="background: #fff; padding: 5px 10px; border-radius: 3px;">{rdp_code}</code>
                </div>
                
                <a href="https://remotedesktop.google.com/access" class="button">
                    🖥️ Connect via Chrome Remote Desktop
                </a>
                
                <p style="margin-top: 20px; color: #666; font-size: 14px;">
                    ⏱️ Session expires in 15 minutes. Please connect as soon as possible.
                </p>
            </div>
            <div class="footer">
                TechFix AI - Automated Tech Support
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email_async(TECHNICIAN_EMAIL, f"🆘 Help Request - Token: {token}", body)


# ============= DATABASE FUNCTIONS =============



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


# ============= AI FUNCTIONS =============

def call_mistral_ai(prompt: str) -> dict:
    """Call Mistral AI API"""
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
            return {"error": f"Mistral API error: {resp.status_code}"}
        
        response_data = resp.json()
        text = response_data["choices"][0]["message"]["content"].strip()
        
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


@app.route('/generate-token', methods=['POST', 'OPTIONS'])
@rate_limit
def generate_token():
    """Generate a new service token"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if is_ip_blocked():
        obfuscate_response()
        return jsonify({"error": "Access temporarily blocked due to suspicious activity"}), 403
    
    try:
        data = request.get_json()
        if not data:
            track_failed_attempt()
            obfuscate_response()
            return jsonify({"error": "Invalid request"}), 400
        
        email = data.get('email', '').strip()
        issue = sanitize_string(data.get('issue', 'Unknown issue'))
        duration = int(data.get('minutes', 30))
        
        if not validate_email(email):
            track_failed_attempt(email)
            obfuscate_response()
            return jsonify({"error": "Valid email required"}), 400
        
        if duration < 1 or duration > 120:
            obfuscate_response()
            return jsonify({"error": "Invalid duration"}), 400

        # Deactivate all previous sessions for this email
        try:
            deactivate_url = f"{SUPABASE_URL}/rest/v1/sessions?email=eq.{email}"
            deactivate_payload = {"active": False}
            
            deactivate_response = requests.patch(
                deactivate_url,
                headers=HEADERS,
                json=deactivate_payload,
                timeout=10
            )
            
            if deactivate_response.status_code in [200, 204]:
                print(f"✅ Deactivated previous sessions for {email}")
            else:
                print(f"⚠️ Could not deactivate old sessions: {deactivate_response.status_code}")
        except Exception as e:
            print(f"⚠️ Error deactivating old sessions: {e}")

        # Generate new token
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
            obfuscate_response()
            return jsonify({
                "token": token,
                "expires_in": duration,
                "expires_at": expires_at,
                "email": email
            }), 201
        else:
            track_failed_attempt(email)
            obfuscate_response()
            return jsonify({"error": "Failed to create session"}), 500
            
    except Exception as e:
        print(f"Error in generate_token: {e}")
        track_failed_attempt()
        obfuscate_response()
        return jsonify({"error": "Internal server error"}), 500


@app.route('/generate-plan', methods=['POST', 'OPTIONS'])
@rate_limit
def generate_plan():
    """Generate repair plan using Mistral AI"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if is_ip_blocked():
        obfuscate_response()
        return jsonify({"error": "Access temporarily blocked"}), 403
    
    try:
        data = request.get_json()
        if not data:
            obfuscate_response()
            return jsonify({"error": "Invalid request"}), 400
        
        token = data.get('token', '').strip()
        issue = sanitize_string(data.get('issue', ''))
        system_info = data.get('system_info', {})
        search_results = data.get('search_results', [])
        file_info = data.get('file_info')
        
        if not token or not issue:
            obfuscate_response()
            return jsonify({"error": "Token and issue required"}), 400
        
        sess = supabase_get_token(token)
        if not sess or not sess.get("active"):
            track_failed_attempt(token)
            obfuscate_response()
            return jsonify({"error": "Invalid or inactive session"}), 401
        
        prompt = build_repair_prompt(issue, system_info, search_results, file_info)
        raw_plan = call_mistral_ai(prompt)
        
        if "error" in raw_plan:
            obfuscate_response()
            return jsonify({
                "software": "Unknown",
                "issue": issue,
                "summary": "AI service error",
                "steps": [{"description": raw_plan["error"], "command": "echo Error occurred", "requires_sudo": False}],
                "estimated_time_minutes": 5,
                "needs_reboot": False
            }), 500
        
        plan = sanitize_plan(raw_plan, issue)
        supabase_update_session(token, {"plan": plan})
        
        obfuscate_response()
        return jsonify(plan), 200
        
    except Exception as e:
        print(f"Error in generate_plan: {e}")
        track_failed_attempt()
        obfuscate_response()
        return jsonify({"error": "Internal server error"}), 500



@app.route('/notifications', methods=['GET'])
def get_notifications():
    """Get latest notification (no auth required)"""
    try:
        # Fetch latest notification from Supabase
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/notifications",
            headers=HEADERS,
            params={
                "select": "id,title,message,created_at",
                "order": "created_at.desc",
                "limit": 1
            },
            timeout=5
        )
        if r.status_code == 200 and r.json():
            return jsonify(r.json()[0])
        else:
            return jsonify({"id": None})
    except Exception as e:
        print(f"Notification fetch error: {e}")
        return jsonify({"id": None})
    

@app.route('/track-download', methods=['POST', 'OPTIONS'])
def track_download():
    """Track agent downloads"""
    if request.method == 'OPTIONS':
        return '', 204
    
    return jsonify({"status": "tracked"}), 200


@app.route('/analytics', methods=['GET', 'OPTIONS'])
def get_analytics():
    """Get analytics dashboard data"""
    if request.method == 'OPTIONS':
        return '', 204
    
    return jsonify({"error": "Not implemented"}), 501


@app.route('/request-human-help', methods=['POST', 'OPTIONS'])
@rate_limit
def request_human_help():
    """Send email alert to technician"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if is_ip_blocked():
        obfuscate_response()
        return jsonify({"error": "Access temporarily blocked"}), 403
    
    try:
        data = request.get_json()
        if not data:
            obfuscate_response()
            return jsonify({"error": "Invalid request"}), 400
        
        token = data.get('token', '').strip()
        email = data.get('email', '').strip()
        issue = sanitize_string(data.get('issue', ''))
        rdp_code = sanitize_string(data.get('rdp_code', ''))
        
        if not validate_email(email):
            obfuscate_response()
            return jsonify({"error": "Valid email required"}), 400
        
        if not all([token, email, issue, rdp_code]):
            obfuscate_response()
            return jsonify({"error": "Missing required fields"}), 400
        
        sess = supabase_get_token(token)
        if not sess or not sess.get("active"):
            track_failed_attempt(token)
            obfuscate_response()
            return jsonify({"error": "Invalid session"}), 401
        
        send_help_request_email(token, email, issue, rdp_code)
        
        obfuscate_response()
        return jsonify({"status": "sent"}), 200
        
    except Exception as e:
        print(f"Error in request_human_help: {e}")
        track_failed_attempt()
        obfuscate_response()
        return jsonify({"error": "Internal server error"}), 500


@app.route('/cleanup-sessions', methods=['POST'])
def cleanup_old_sessions():
    """Delete inactive sessions older than 7 days and maintain user email CSV"""
    try:
        auth_key = request.json.get('key') if request.json else None
        if auth_key != os.getenv("CLEANUP_KEY", "your-secret-cleanup-key"):
            return jsonify({"error": "Unauthorized"}), 401
        
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        
        delete_url = f"{SUPABASE_URL}/rest/v1/sessions?active=eq.false&created_at=lt.{cutoff_date}"
        response = requests.delete(delete_url, headers=HEADERS, timeout=10)
        
        cleanup_status = "success" if response.status_code in [200, 204] else "failed"
        
        sessions_url = f"{SUPABASE_URL}/rest/v1/sessions?select=email"
        sessions_response = requests.get(sessions_url, headers=HEADERS, timeout=10)
        
        if sessions_response.status_code == 200:
            sessions = sessions_response.json()
            
            csv_filename = 'user_emails.csv'
            existing_emails = set()
            
            if os.path.exists(csv_filename):
                with open(csv_filename, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    existing_emails = {row['email'] for row in reader if row.get('email')}
            
            new_emails = set()
            for session in sessions:
                email = session.get('email')
                if email and email not in existing_emails:
                    new_emails.add(email)
            
            emails_added = 0
            if new_emails:
                file_exists = os.path.exists(csv_filename)
                with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=['email', 'added_at'])
                    
                    if not file_exists:
                        writer.writeheader()
                    
                    for email in sorted(new_emails):
                        writer.writerow({
                            'email': email,
                            'added_at': datetime.now(timezone.utc).isoformat()
                        })
                        emails_added += 1
            
            return jsonify({
                "status": cleanup_status,
                "cleanup_message": f"Deleted inactive sessions older than {cutoff_date}",
                "csv_status": "updated",
                "emails_added": emails_added,
                "total_unique_emails": len(existing_emails) + emails_added
            }), 200
        else:
            return jsonify({
                "status": cleanup_status,
                "cleanup_message": f"Deleted inactive sessions older than {cutoff_date}",
                "csv_status": "failed",
                "error": "Could not fetch sessions for CSV update"
            }), 200
            
    except Exception as e:
        print(f"Cleanup error: {e}")
        return jsonify({"error": f"Cleanup failed: {str(e)}"}), 500


# Honeypot endpoint
@app.route('/api/v1/auth/login', methods=['POST'])
def honeypot():
    """Fake endpoint to detect malicious scanning"""
    client_ip = get_client_ip()
    print(f"⚠️ SECURITY ALERT: Suspicious request from {client_ip}")
    obfuscate_response()
    return jsonify({"error": "Invalid endpoint"}), 404


# Security headers
@app.after_request
def add_security_headers(response):
    """Add security headers to prevent inspection and attacks"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    response.headers.pop('Server', None)
    response.headers.pop('X-Powered-By', None)
    
    return response


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug)
















# #!/usr/bin/env python3
# """
# AI Tech Repairer - Backend with Resend Email
# Token shown on frontend only
# Email only used for request-human-help
# """

# from flask import Flask, request, jsonify
# import requests
# import uuid
# import os
# import json
# import csv
# import threading
# from datetime import datetime, timedelta, timezone
# from dotenv import load_dotenv
# from flask_cors import CORS
# import resend
# from functools import wraps
# from collections import defaultdict
# import time
# import hashlib
# import secrets

# app = Flask(__name__)

# CORS(app, 
#      origins=[
#         "https://techfix-frontend-nc49.onrender.com",
#         "http://localhost:5173",
#         "http://localhost:3000",
#         "http://localhost:8080",
#         "http://127.0.0.1:8080"   
#      ],
#      allow_headers=["Content-Type", "Authorization"],
#      methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
#      supports_credentials=True,
#      max_age=3600
# )

# load_dotenv()

# # Configuration
# SUPABASE_URL = os.getenv("SUPABASE_URL")  
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL")
# RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# # Initialize Resend
# resend.api_key = RESEND_API_KEY

# # IMPORTANT: Add HEADERS definition here (it was missing!)
# HEADERS = {
#     "apikey": SUPABASE_KEY,
#     "Authorization": f"Bearer {SUPABASE_KEY}",
#     "Content-Type": "application/json"
# }

# rate_limit_storage = defaultdict(list)
# RATE_LIMIT = 5  # requests per minute
# RATE_LIMIT_WINDOW = 60  # seconds

# print("\n" + "="*60)
# print("BACKEND STARTUP - Environment Check")
# print("="*60)
# print(f"SUPABASE_URL loaded: {bool(SUPABASE_URL)}")
# print(f"SUPABASE_KEY loaded: {bool(SUPABASE_KEY)}")
# print(f"MISTRAL_API_KEY loaded: {bool(MISTRAL_API_KEY)}")
# print(f"RESEND_API_KEY loaded: {bool(RESEND_API_KEY)}")
# print(f"TECHNICIAN_EMAIL: {TECHNICIAN_EMAIL}")
# print("="*60 + "\n")

# #============================= SECURITY AND RATE LIMITING ==============================

# def get_client_ip():
#     """Get real client IP even behind proxies"""
#     if request.headers.get('X-Forwarded-For'):
#         return request.headers.get('X-Forwarded-For').split(',')[0].strip()
#     elif request.headers.get('X-Real-IP'):
#         return request.headers.get('X-Real-IP')
#     return request.remote_addr

# def rate_limit(f):
#     """Rate limiting decorator"""
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         client_ip = get_client_ip()
#         current_time = time.time()
        
#         # Clean old entries
#         rate_limit_storage[client_ip] = [
#             req_time for req_time in rate_limit_storage[client_ip]
#             if current_time - req_time < RATE_LIMIT_WINDOW
#         ]
        
#         # Check rate limit
#         if len(rate_limit_storage[client_ip]) >= RATE_LIMIT:
#             return jsonify({
#                 "error": "Too many requests. Please try again later.",
#                 "retry_after": 60
#             }), 429
        
#         # Add current request
#         rate_limit_storage[client_ip].append(current_time)
        
#         return f(*args, **kwargs)
#     return decorated_function

# def obfuscate_response():
#     """Add random noise to response timing to prevent timing attacks"""
#     time.sleep(secrets.randbelow(100) / 1000)  # 0-100ms random delay



# # ============= RESEND EMAIL FUNCTIONS =============

# def send_email_with_resend(to_email: str, subject: str, body: str):
#     """Send email using Resend library"""
#     print(f"\n📧 [EMAIL] Sending to {to_email}")
#     print(f"   Subject: {subject}")
    
#     try:
#         params = {
#             "from": "TechFix AI <onboarding@resend.dev>",
#             "to": [to_email],
#             "subject": subject,
#             "html": body
#         }
        
#         email = resend.Emails.send(params)
        
#         print(f"✅ [EMAIL SUCCESS] Email sent to {to_email}")
#         print(f"   Email ID: {email.get('id', 'N/A')}")
#         return True
            
#     except Exception as e:
#         print(f"❌ [EMAIL ERROR] {type(e).__name__}: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return False


# def send_email_async(to_email: str, subject: str, body: str):
#     """Send email in background thread"""
#     def _send():
#         print(f"\n📧 [THREAD START] Email thread started")
#         success = send_email_with_resend(to_email, subject, body)
#         if success:
#             print(f"✅ [THREAD END] Email sent successfully")
#         else:
#             print(f"❌ [THREAD END] Email failed")
    
#     thread = threading.Thread(target=_send, daemon=True)
#     thread.start()
#     print(f"📧 [ASYNC] Email background thread started for {to_email}")


# def send_help_request_email(token: str, user_email: str, issue: str, rdp_code: str):
#     """Send help request to technician via email"""
#     print(f"\n🚀 [HELP REQUEST] Initiating email to technician")
#     print(f"   To: {TECHNICIAN_EMAIL}")
#     print(f"   Token: {token}")
    
#     # Use HTML formatting for better readability
#     body = f"""
#     <!DOCTYPE html>
#     <html>
#     <head>
#         <style>
#             body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
#             .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
#             .header {{ background: #4CAF50; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
#             .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
#             .info-row {{ margin: 10px 0; }}
#             .label {{ font-weight: bold; color: #555; }}
#             .button {{ 
#                 display: inline-block;
#                 background: #4CAF50;
#                 color: white;
#                 padding: 12px 24px;
#                 text-decoration: none;
#                 border-radius: 5px;
#                 margin-top: 15px;
#             }}
#             .footer {{ margin-top: 20px; padding: 10px; text-align: center; color: #777; font-size: 12px; }}
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <div class="header">
#                 <h2>🆘 Help Request Received</h2>
#             </div>
#             <div class="content">
#                 <div class="info-row">
#                     <span class="label">Service Token:</span> {token}
#                 </div>
#                 <div class="info-row">
#                     <span class="label">User Email:</span> {user_email}
#                 </div>
#                 <div class="info-row">
#                     <span class="label">Issue:</span> {issue}
#                 </div>
#                 <div class="info-row">
#                     <span class="label">Chrome Remote Desktop Code:</span> <code style="background: #fff; padding: 5px 10px; border-radius: 3px;">{rdp_code}</code>
#                 </div>
                
#                 <a href="https://remotedesktop.google.com/access" class="button">
#                     🖥️ Connect via Chrome Remote Desktop
#                 </a>
                
#                 <p style="margin-top: 20px; color: #666; font-size: 14px;">
#                     ⏱️ Session expires in 15 minutes. Please connect as soon as possible.
#                 </p>
#             </div>
#             <div class="footer">
#                 TechFix AI - Automated Tech Support
#             </div>
#         </div>
#     </body>
#     </html>
#     """
    
#     send_email_async(TECHNICIAN_EMAIL, f"🆘 Help Request - Token: {token}", body)







# # ============= DATABASE FUNCTIONS =============

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


# # ============= AI FUNCTIONS =============

# def call_mistral_ai(prompt: str) -> dict:
#     """Call Mistral AI API"""
#     try:
#         resp = requests.post(
#             "https://api.mistral.ai/v1/chat/completions",
#             headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
#             json={
#                 "model": "mistral-small-latest",
#                 "messages": [{"role": "user", "content": prompt}],
#                 "temperature": 0.3,
#                 "max_tokens": 2000,
#                 "response_format": {"type": "json_object"}
#             },
#             timeout=45
#         )
        
#         if resp.status_code != 200:
#             return {"error": f"Mistral API error: {resp.status_code}"}
        
#         response_data = resp.json()
#         text = response_data["choices"][0]["message"]["content"].strip()
        
#         if "```json" in text:
#             text = text.split("```json")[1].split("```")[0]
#         elif "```" in text:
#             text = text.split("```")[1].split("```")[0]
        
#         text = text.strip()
        
#         try:
#             plan = json.loads(text)
#             return plan
#         except json.JSONDecodeError:
#             return {"error": "Failed to parse AI response"}
            
#     except Exception as e:
#         return {"error": f"Unexpected error: {str(e)}"}


# def sanitize_plan(plan: dict, issue: str) -> dict:
#     """Validate and sanitize the AI-generated plan"""
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
    
#     if "error" in plan:
#         return {
#             "software": "Unknown",
#             "issue": issue,
#             "summary": "AI service error",
#             "steps": [{"description": plan["error"], "command": "echo AI error occurred", "requires_sudo": False}],
#             "estimated_time_minutes": 5,
#             "needs_reboot": False
#         }
    
#     sanitized = {
#         "software": plan.get("software", "Unknown"),
#         "issue": plan.get("issue", issue),
#         "summary": plan.get("summary", "Repair steps"),
#         "steps": [],
#         "estimated_time_minutes": plan.get("estimated_time_minutes", 10),
#         "needs_reboot": plan.get("needs_reboot", False)
#     }
    
#     raw_steps = plan.get("steps", [])
#     if not raw_steps:
#         sanitized["steps"] = [{
#             "description": "No repair steps generated",
#             "command": "echo No steps available",
#             "requires_sudo": False
#         }]
#     else:
#         for step in raw_steps[:6]:
#             if isinstance(step, dict):
#                 command = str(step.get("command", "")).strip()
#                 if not command:
#                     command = f"echo {step.get('description', 'Manual step')[:50]}"
                
#                 sanitized["steps"].append({
#                     "description": str(step.get("description", "No description"))[:300],
#                     "command": command[:500],
#                     "requires_sudo": bool(step.get("requires_sudo", False))
#                 })
    
#     return sanitized


# def build_repair_prompt(issue: str, system_info: dict, search_results: list, file_info: dict = None) -> str:
#     """Build the prompt for Mistral AI"""
#     os_type = system_info.get('os', 'Windows')
    
#     prompt = f"""
# You are a computer repair technician AI. Generate a repair plan.

# USER'S ISSUE: {issue}
# SYSTEM: {os_type}

# Output valid JSON:
# {{
#   "software": "name",
#   "issue": "{issue}",
#   "summary": "brief summary",
#   "steps": [
#     {{
#       "description": "step description",
#       "command": "actual command",
#       "requires_sudo": true
#     }}
#   ],
#   "estimated_time_minutes": 15,
#   "needs_reboot": false
# }}

# Generate repair plan for: {issue}
# """
#     return prompt


# # ============= API ENDPOINTS =============

# @app.route('/health', methods=['GET'])
# def health():
#     """Health check endpoint"""
#     return jsonify({
#         "status": "ok",
#         "time": datetime.now(timezone.utc).isoformat(),
#         "service": "AI Tech Repairer Backend"
#     })



# #============= INPUT VALIDATION AND SANITIZATION =============
# def validate_email(email):
#     """Validate email format"""
#     if not email or '@' not in email or '.' not in email:
#         return False
#     if len(email) > 254:
#         return False
#     if any(c in email for c in [' ', '"', "'", '<', '>', ';']):
#         return False
#     return True

# def sanitize_string(text, max_length=500):
#     """Sanitize user input"""
#     if not text:
#         return ""
#     text = str(text).strip()
#     dangerous_chars = ['<', '>', '"', "'", ';', '&', '|', '`']
#     for char in dangerous_chars:
#         text = text.replace(char, '')
#     return text[:max_length]


# @app.route('/generate-token', methods=['POST', 'OPTIONS'])
# @rate_limit
# def generate_token():

#     """Generate a new service token (NO EMAIL SENT)"""
#     if request.method == 'OPTIONS':
#         return '', 204

    
#     try:
#         email = request.json.get('email')
#         issue = request.json.get('issue', 'Unknown issue')
#         duration = int(request.json.get('minutes', 30))

#         if not email or '@' not in email:
#             obfuscate_response() 
#             return jsonify({"error": "Valid email required"}), 400

#         # ====== NEW: Deactivate all previous sessions for this email ======
#         try:
#             deactivate_url = f"{SUPABASE_URL}/rest/v1/sessions?email=eq.{email}"
#             deactivate_payload = {"active": False}
            
#             deactivate_response = requests.patch(
#                 deactivate_url,
#                 headers=HEADERS,
#                 json=deactivate_payload,
#                 timeout=10
#             )
            
#             if deactivate_response.status_code in [200, 204]:
#                 print(f"✅ Deactivated previous sessions for {email}")
#             else:
#                 print(f"⚠️ Could not deactivate old sessions: {deactivate_response.status_code}")
#         except Exception as e:
#             print(f"⚠️ Error deactivating old sessions: {e}")
#             # Continue anyway - not critical if this fails
#         # ================================================================

#         # Generate new token
#         raw_token = str(uuid.uuid4())[:8].upper()
#         token = f"{raw_token[:4]}-{raw_token[4:]}"
#         expires_at = (datetime.now(timezone.utc) + timedelta(minutes=duration)).isoformat()

#         payload = {
#             "token": token,
#             "email": email,
#             "issue": issue,
#             "created_at": datetime.now(timezone.utc).isoformat(),
#             "expires_at": expires_at,
#             "active": True,  # Only the NEW session is active
#             "plan": None
#         }

#         if supabase_insert_session(payload):
#             obfuscate_response()
#             return jsonify({
#                 "token": token,
#                 "expires_in": duration,
#                 "expires_at": expires_at,
#                 "email": email
#             }), 201
#         else:
#             obfuscate_response()
#             return jsonify({"error": "Failed to create session"}), 500
            
#     except Exception as e:
#         print(f"Error in generate_token: {e}")
#         obfuscate_response()
#         return jsonify({"error": "Internal server error"}), 500



# @app.route('/generate-plan', methods=['POST', 'OPTIONS'])
# def generate_plan():
#     """Generate repair plan using Mistral AI"""
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     try:
#         token = request.json.get('token')
#         issue = request.json.get('issue')
#         system_info = request.json.get('system_info', {})
#         search_results = request.json.get('search_results', [])
#         file_info = request.json.get('file_info')
        
#         if not token or not issue:
#             return jsonify({"error": "Token and issue required"}), 400
        
#         sess = supabase_get_token(token)
#         if not sess or not sess["active"]:
#             return jsonify({"error": "Invalid or inactive session"}), 401
        
#         prompt = build_repair_prompt(issue, system_info, search_results, file_info)
#         raw_plan = call_mistral_ai(prompt)
        
#         if "error" in raw_plan:
#             return jsonify({
#                 "software": "Unknown",
#                 "issue": issue,
#                 "summary": "AI service error",
#                 "steps": [{"description": raw_plan["error"], "command": "echo Error occurred", "requires_sudo": False}],
#                 "estimated_time_minutes": 5,
#                 "needs_reboot": False
#             }), 500
        
#         plan = sanitize_plan(raw_plan, issue)
#         supabase_update_session(token, {"plan": plan})
        
#         return jsonify(plan), 200
        
#     except Exception as e:
#         print(f"Error in generate_plan: {e}")
#         return jsonify({"error": "Internal server error"}), 500


# @app.route('/track-download', methods=['POST', 'OPTIONS'])
# def track_download():
#     """Track agent downloads"""
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     return jsonify({"status": "tracked"}), 200


# @app.route('/analytics', methods=['GET', 'OPTIONS'])
# def get_analytics():
#     """Get analytics dashboard data"""
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     return jsonify({"error": "Not implemented"}), 501


# @app.route('/request-human-help', methods=['POST', 'OPTIONS'])
# def request_human_help():
#     """Send email alert to technician ONLY"""
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     try:
#         token = request.json.get('token')
#         email = request.json.get('email')
#         issue = request.json.get('issue')
#         rdp_code = request.json.get('rdp_code')
        
#         sess = supabase_get_token(token)
#         if not sess or not sess["active"]:
#             return jsonify({"error": "Invalid session"}), 401
        
#         # Send email to technician using Resend
#         send_help_request_email(token, email, issue, rdp_code)
        
#         return jsonify({"status": "sent"}), 200
        
#     except Exception as e:
#         print(f"Error in request_human_help: {e}")
#         return jsonify({"error": "Internal server error"}), 500



# @app.route('/cleanup-sessions', methods=['POST'])
# def cleanup_old_sessions():
#     """Delete inactive sessions older than 7 days and maintain user email CSV"""
#     try:
#         # Require authentication
#         auth_key = request.json.get('key')
#         if auth_key != os.getenv("CLEANUP_KEY", "your-secret-cleanup-key"):
#             return jsonify({"error": "Unauthorized"}), 401
        
#         # Calculate cutoff date (7 days ago)
#         cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        
#         # Delete old inactive sessions
#         delete_url = f"{SUPABASE_URL}/rest/v1/sessions?active=eq.false&created_at=lt.{cutoff_date}"
#         response = requests.delete(delete_url, headers=HEADERS, timeout=10)
        
#         cleanup_status = "success" if response.status_code in [200, 204] else "failed"
        
#         # Fetch all sessions to extract unique emails
#         sessions_url = f"{SUPABASE_URL}/rest/v1/sessions?select=email"
#         sessions_response = requests.get(sessions_url, headers=HEADERS, timeout=10)
        
#         if sessions_response.status_code == 200:
#             sessions = sessions_response.json()
            
#             # Get existing emails from CSV
#             csv_filename = 'user_emails.csv'
#             existing_emails = set()
            
#             # Read existing CSV if it exists
#             if os.path.exists(csv_filename):
#                 with open(csv_filename, 'r', newline='', encoding='utf-8') as csvfile:
#                     reader = csv.DictReader(csvfile)
#                     existing_emails = {row['email'] for row in reader if row.get('email')}
            
#             # Extract unique emails from sessions
#             new_emails = set()
#             for session in sessions:
#                 email = session.get('email')
#                 if email and email not in existing_emails:
#                     new_emails.add(email)
            
#             # Append new emails to CSV
#             emails_added = 0
#             if new_emails:
#                 file_exists = os.path.exists(csv_filename)
#                 with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
#                     writer = csv.DictWriter(csvfile, fieldnames=['email', 'added_at'])
                    
#                     # Write header if file is new
#                     if not file_exists:
#                         writer.writeheader()
                    
#                     # Write new emails
#                     for email in sorted(new_emails):
#                         writer.writerow({
#                             'email': email,
#                             'added_at': datetime.now(timezone.utc).isoformat()
#                         })
#                         emails_added += 1
            
#             return jsonify({
#                 "status": cleanup_status,
#                 "cleanup_message": f"Deleted inactive sessions older than {cutoff_date}",
#                 "csv_status": "updated",
#                 "emails_added": emails_added,
#                 "total_unique_emails": len(existing_emails) + emails_added
#             }), 200
#         else:
#             return jsonify({
#                 "status": cleanup_status,
#                 "cleanup_message": f"Deleted inactive sessions older than {cutoff_date}",
#                 "csv_status": "failed",
#                 "error": "Could not fetch sessions for CSV update"
#             }), 200
            
#     except Exception as e:
#         print(f"Cleanup error: {e}")
#         return jsonify({"error": f"Cleanup failed: {str(e)}"}), 500
    
    

# # OPTIONAL: Add honeypot endpoint to detect scanning
# @app.route('/api/v1/auth/login', methods=['POST'])
# def honeypot():
#     """Fake endpoint to detect malicious scanning"""
#     client_ip = get_client_ip()
#     print(f"⚠️ SECURITY ALERT: Suspicious request from {client_ip}")
#     # Log to your security system
#     return jsonify({"error": "Invalid endpoint"}), 404


# # CRITICAL: Add these headers to ALL responses
# @app.after_request
# def add_security_headers(response):
#     """Add security headers to prevent inspection and attacks"""
#     response.headers['X-Content-Type-Options'] = 'nosniff'
#     response.headers['X-Frame-Options'] = 'DENY'
#     response.headers['X-XSS-Protection'] = '1; mode=block'
#     response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
#     response.headers['Content-Security-Policy'] = "default-src 'self'"
    
#     # Remove identifying headers
#     response.headers.pop('Server', None)
#     response.headers.pop('X-Powered-By', None)
    
#     return response

# if __name__ == '__main__':
#     port = int(os.getenv("PORT", 8000))
#     debug = os.getenv("DEBUG", "False").lower() == "true"
#     app.run(host='0.0.0.0', port=port, debug=debug)




















