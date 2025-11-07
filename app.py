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
import hashlib
import hmac
# from flutterwave import Flutterwave
app = Flask(__name__)

load_dotenv()

# ============= CORS CONFIGURATION =============
# At the top of your backend file, after imports

if os.getenv("FLASK_ENV") == "production":
    CORS(app, 
         resources={
             r"/*": {
                 "origins": ["https://techfix-frontend-nc49.onrender.com"],
                 "methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                 "allow_headers": ["Content-Type", "Authorization", "Accept"],
                 "expose_headers": ["Content-Type"],
                 "supports_credentials": True,
                 "max_age": 3600
             }
         }
    )
else:
    CORS(app, 
         resources={
             r"/*": {
                 "origins": [
                     "http://localhost:5173",
                     "http://localhost:3000",
                     "http://localhost:8080",
                     "http://127.0.0.1:8080"   
                 ],
                 "methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                 "allow_headers": ["Content-Type", "Authorization", "Accept"],
                 "expose_headers": ["Content-Type"],
                 "supports_credentials": True,
                 "max_age": 3600
             }
         }
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


def send_help_request_email(token: str, user_email: str, issue: str, anydesk_code: str):
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
                    <span class="label">Anydesk Remote Desktop Code:</span> <code style="background: #fff; padding: 5px 10px; border-radius: 3px;">{anydesk_code}</code>
                </div>
                
                <a href="https://remotedesktop.google.com/access" class="button">
                    🖥️ Connect via Anydesk Remote Desktop
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


# def supabase_get_token(token: str):
#     """Fetch session data from Supabase with PROPER validation"""
#     try:
#         r = requests.get(
#             f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
#             headers=HEADERS,
#             params={"select": "token,email,issue,active,expires_at,plan_type,created_at"}, # Include expires_at and created_at
#             timeout=10
#         )
#         if r.status_code == 200:
#             data = r.json()
#             if not data:
#                 print(f"🔍 Token {token} not found in database.")
#                 return None
#             session = data[0]

#             # ===== CRITICAL FIX: Validate expiry from database =====
#             expires_at_str = session.get('expires_at')
#             if not expires_at_str:
#                 print(f"⚠️ Session {token} has no expiry date in database.")
#                 return None

#             # Parse expiry as UTC-aware datetime
#             try:
#                 if expires_at_str.endswith('Z'):
#                     expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
#                 else:
#                     # If Supabase returns without 'Z', it might already be offset-aware
#                     expires_at = datetime.fromisoformat(expires_at_str)
#                 if expires_at.tzinfo is None:
#                     expires_at = expires_at.replace(tzinfo=timezone.utc)

#                 # Check if expired
#                 now_utc = datetime.now(timezone.utc)
#                 if now_utc >= expires_at:
#                     print(f"⏰ Token {token} has expired on: {expires_at_str}")
#                     print(f"   Current time (UTC): {now_utc.isoformat()}")
#                     # Auto-deactivate expired token in database (optional but recommended)
#                     try:
#                         deactivate_url = f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}"
#                         requests.patch(deactivate_url, headers=HEADERS, json={"active": False}, timeout=10)
#                         print(f"   🗑️ Token {token} deactivated in database.")
#                     except Exception as e:
#                         print(f"   ⚠️ Could not deactivate token in DB: {e}")
#                     return None # Return None if expired
#             except Exception as e:
#                 print(f"⚠️ Error parsing expiry date from database for token {token}: {e}")
#                 return None

#             # Token is valid and not expired, return session data
#             print(f"✅ Token {token} is valid and expires at: {expires_at_str}")
#             return session
#         else:
#             print(f"🔍 Supabase query failed for token {token}, status: {r.status_code}")
#             return None
#     except Exception as e:
#         print(f"🔍 Supabase GET error for token {token}: {e}")
#         return None


def supabase_get_token(token: str):
    """Fetch session data from Supabase with PROPER expiry validation"""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
            headers=HEADERS,
            params={"select": "token,email,issue,active,expires_at,plan_type,created_at"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if not data:
                print(f"🔍 Token {token} not found in database.")
                return None
            
            session = data[0]
            
            # ===== CRITICAL: Validate expiry =====
            expires_at_str = session.get('expires_at')
            if not expires_at_str:
                print(f"⚠️ Session {token} has no expiry date.")
                return None

            try:
                # Parse ISO format with timezone
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                
                # Ensure timezone-aware
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                # Check expiry
                now_utc = datetime.now(timezone.utc)
                if now_utc >= expires_at:
                    print(f"⏰ Token {token} expired at {expires_at_str}")
                    
                    # Auto-deactivate
                    try:
                        requests.patch(
                            f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
                            headers=HEADERS,
                            json={"active": False},
                            timeout=10
                        )
                        print(f"   🗑️ Token deactivated")
                    except Exception as e:
                        print(f"   ⚠️ Deactivation failed: {e}")
                    
                    return None  # Expired
                
                # Valid token
                time_left = (expires_at - now_utc).total_seconds() / 3600
                print(f"✅ Token valid. {time_left:.1f} hours remaining")
                return session
                
            except (ValueError, AttributeError) as e:
                print(f"⚠️ Error parsing expiry: {e}")
                return None
        else:
            print(f"🔍 Query failed: {r.status_code}")
            return None
            
    except Exception as e:
        print(f"🔍 Database error: {e}")
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
    """Create new session in Supabase with error logging"""
    try:
        # Only include fields that exist in your table
        allowed_fields = {
            'token', 'email', 'issue', 'created_at', 'expires_at', 
            'active', 'plan_type', 'transaction_ref', 'plan'
        }
        filtered_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/sessions",
            headers=HEADERS,
            json=filtered_data,
            timeout=10
        )
        print(f"📥 Supabase insert status: {r.status_code}")  # Debug log
        if r.status_code != 201:
            print(f"❌ Supabase error: {r.text}")  # Log the actual error
        return r.status_code == 201
    except Exception as e:
        print(f"❌ Supabase INSERT exception: {e}")
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




# @app.route('/generate-token', methods=['POST', 'OPTIONS'])
# @rate_limit
# def generate_token():
#     """Generate a new service token with PROPER tiered validity"""
#     if request.method == 'OPTIONS':
#         return '', 204
#     if is_ip_blocked():
#         obfuscate_response()
#         return jsonify({"error": "Access temporarily blocked"}), 403
#     try:
#         data = request.get_json()
#         if not data:
#             track_failed_attempt()
#             obfuscate_response()
#             return jsonify({"error": "Invalid request"}), 400
#         email = data.get('email', '').strip()
#         issue = sanitize_string(data.get('issue', 'Unknown issue'))
#         plan = data.get('plan', 'basic')  # 'basic', 'bundle', 'pro'

#         # Validate email
#         if not validate_email(email):
#             track_failed_attempt(email)
#             obfuscate_response()
#             return jsonify({"error": "Valid email required"}), 400

#         # ===== CRITICAL FIX: Proper duration mapping =====
#         plan_durations = {
#             'basic': 24,      # 24 hours
#             'bundle': 168,    # 7 days (7 * 24)
#             'pro': 720        # 30 days (30 * 24)
#         }
#         duration_hours = plan_durations.get(plan, 24)

#         # Deactivate old sessions for this email
#         try:
#             deactivate_url = f"{SUPABASE_URL}/rest/v1/sessions?email=eq.{email}"
#             requests.patch(deactivate_url, headers=HEADERS, json={"active": False}, timeout=10)
#         except Exception as e:
#             print(f"⚠️ Could not deactivate old sessions: {e}")

#         # Generate token
#         raw_token = str(uuid.uuid4())[:8].upper()
#         token = f"{raw_token[:4]}-{raw_token[4:]}"
#         # Calculate expiry in UTC
#         now_utc = datetime.now(timezone.utc)
#         expires_at = now_utc + timedelta(hours=duration_hours)
#         expires_at_str = expires_at.isoformat()

#         payload = {
#             "token": token,
#             "email": email,
#             "issue": issue,
#             "created_at": now_utc.isoformat(),
#             "expires_at": expires_at_str,  # Store the calculated expiry time
#             "active": True,
#             "plan_type": plan  # ← Critical for agent validation
#         }

#         print(f"📝 Creating token: {token}")
#         print(f"   Plan: {plan}")
#         print(f"   Duration: {duration_hours} hours")
#         print(f"   Expires: {expires_at_str}")

#         if supabase_insert_session(payload):
#             obfuscate_response()
#             return jsonify({
#                 "token": token,
#                 "plan": plan,
#                 "expires_in_hours": duration_hours,
#                 "expires_at": expires_at_str,
#                 "email": email
#             }), 201
#         else:
#             track_failed_attempt(email)
#             obfuscate_response()
#             return jsonify({"error": "Failed to create session"}), 500
#     except Exception as e:
#         print(f"Error in generate_token: {e}")
#         track_failed_attempt()
#         obfuscate_response()
#         return jsonify({"error": "Internal server error"}), 500




@app.route('/generate-token', methods=['POST', 'OPTIONS'])
@rate_limit
def generate_token():
    """Generate token with CORRECT tiered expiry"""
    if request.method == 'OPTIONS':
        return '', 204
        
    if is_ip_blocked():
        obfuscate_response()
        return jsonify({"error": "Access temporarily blocked"}), 403
    
    try:
        data = request.get_json()
        if not data:
            track_failed_attempt()
            return jsonify({"error": "Invalid request"}), 400
        
        email = data.get('email', '').strip()
        issue = sanitize_string(data.get('issue', 'Unknown issue'))
        plan = data.get('plan', 'basic')
        
        if not validate_email(email):
            track_failed_attempt(email)
            return jsonify({"error": "Valid email required"}), 400
        
        # ===== CRITICAL: Correct duration mapping =====
        plan_durations = {
            'basic': 24,      # 24 hours
            'bundle': 168,    # 7 days
            'pro': 720        # 30 days
        }
        duration_hours = plan_durations.get(plan, 24)
        
        # Deactivate old sessions
        try:
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/sessions?email=eq.{email}",
                headers=HEADERS,
                json={"active": False},
                timeout=10
            )
        except Exception as e:
            print(f"⚠️ Old session cleanup failed: {e}")
        
        # Generate token
        raw_token = str(uuid.uuid4())[:8].upper()
        token = f"{raw_token[:4]}-{raw_token[4:]}"
        
        # Calculate expiry in UTC (CRITICAL FIX)
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(hours=duration_hours)
        
        # Format as ISO 8601 with explicit timezone
        expires_at_str = expires_at.isoformat()
        
        print(f"📝 Creating token: {token}")
        print(f"   Plan: {plan} ({duration_hours}h)")
        print(f"   Created: {now_utc.isoformat()}")
        print(f"   Expires: {expires_at_str}")
        
        payload = {
            "token": token,
            "email": email,
            "issue": issue,
            "created_at": now_utc.isoformat(),
            "expires_at": expires_at_str,  # Store as ISO string
            "active": True,
            "plan_type": plan
        }
        
        if supabase_insert_session(payload):
            obfuscate_response()
            return jsonify({
                "token": token,
                "plan": plan,
                "expires_in_hours": duration_hours,
                "expires_at": expires_at_str,
                "email": email
            }), 201
        else:
            track_failed_attempt(email)
            return jsonify({"error": "Failed to create session"}), 500
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        track_failed_attempt()
        return jsonify({"error": "Internal server error"}), 500





@app.route('/download/agent/<platform>', methods=['GET', 'OPTIONS'])
@rate_limit
def download_agent(platform):
    """Proxy download requests to hide the actual GitHub URL"""
    if request.method == 'OPTIONS':
        return '', 204
    
    # Map platforms to their actual download URLs
    download_urls = {
        'linux': 'https://github.com/Boluex/techfix-frontend/releases/download/1.0/TechFIx.Agent.zip',
        'windows': 'https://github.com/Boluex/techfix-frontend/releases/download/v1.0.0/TechFix_Agent_Windows.zip',  
        
    }
    
    if platform not in download_urls:
        obfuscate_response()
        return jsonify({"error": "Invalid platform"}), 404
    
    try:
        # Fetch the file from GitHub
        github_url = download_urls[platform]
        response = requests.get(github_url, stream=True, timeout=30)
        
        if response.status_code != 200:
            obfuscate_response()
            return jsonify({"error": "Download not available"}), 404
        
        # Create a Flask response that streams the file
        from flask import Response
        
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        # Set appropriate headers
        flask_response = Response(
            generate(),
            content_type=response.headers.get('content-type', 'application/octet-stream'),
            headers={
                'Content-Disposition': f'attachment; filename=TechFix.Agent.{platform}.zip',
                'Content-Length': response.headers.get('content-length', '')
            }
        )
        
        return flask_response
        
    except Exception as e:
        print(f"Download proxy error: {e}")
        obfuscate_response()
        return jsonify({"error": "Download failed"}), 500



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
        anydesk_code = sanitize_string(data.get('anydesk_code', ''))
        
        if not validate_email(email):
            obfuscate_response()
            return jsonify({"error": "Valid email required"}), 400
        
        if not all([token, email, issue, anydesk_code]):
            obfuscate_response()
            return jsonify({"error": "Missing required fields"}), 400
        
        sess = supabase_get_token(token)
        if not sess or not sess.get("active"):
            track_failed_attempt(token)
            obfuscate_response()
            return jsonify({"error": "Invalid session"}), 401
        
        send_help_request_email(token, email, issue, anydesk_code)
        
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






@app.route('/create-checkout-session', methods=['POST', 'OPTIONS'])
def create_checkout_session():
    """Create Flutterwave payment session"""
    
    if request.method == 'OPTIONS':
        response = app.make_response('')
        response.headers['Access-Control-Allow-Origin'] = 'https://techfix-frontend-nc49.onrender.com'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, Authorization'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response, 200
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400
        
        plan_id = data.get('plan')
        email = data.get('email')
        
        if not email or '@' not in email:
            return jsonify({"error": "Valid email required"}), 400
        
        plan_prices = {
            'basic': 29,
            'bundle': 59,
            'pro': 99
        }
        
        if plan_id not in plan_prices:
            return jsonify({"error": "Invalid plan"}), 400

        tx_ref = f"TECHFIX-{uuid.uuid4().hex[:12].upper()}"

        # IMPORTANT: Redirect back to home page, not /payment-success
        frontend_url = os.getenv('FRONTEND_URL', 'https://techfix-frontend-nc49.onrender.com')
        
        payload = {
            "tx_ref": tx_ref,
            "amount": plan_prices[plan_id],
            "currency": "USD",
            "redirect_url": f"{frontend_url}/?status=successful&tx_ref={tx_ref}",  # ← Changed this
            "customer": {
                "email": email,
                "name": email.split('@')[0]
            },
            "customizations": {
                "title": "TechFix AI",
                "description": f"{plan_id.title()} Plan"
            },
            "meta": {
                "email": email,
                "plan": plan_id
            }
        }

        print(f"🔄 Creating payment for {email}, plan: {plan_id}")
        
        fw_response = requests.post(
            "https://api.flutterwave.com/v3/payments",
            json=payload,
            headers={
                "Authorization": f"Bearer {os.getenv('FLUTTERWAVE_SECRET_KEY')}",
                "Content-Type": "application/json"
            },
            timeout=15
        )
        
        print(f"📥 Flutterwave status: {fw_response.status_code}")

        if fw_response.status_code != 200:
            print(f"❌ Error: {fw_response.text}")
            return jsonify({"error": "Payment initialization failed"}), 500

        fw_data = fw_response.json()

        if fw_data.get("status") == "success":
            return jsonify({
                "redirect_url": fw_data["data"]["link"],
                "tx_ref": tx_ref
            }), 200
        else:
            print(f"❌ FW Error: {fw_data}")
            return jsonify({"error": "Payment setup failed"}), 400

    except Exception as e:
        print(f"💥 Exception: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Payment service error"}), 500








@app.route('/flutterwave-webhook', methods=['POST'])
def flutterwave_webhook():
    # Verify webhook signature (security)
    signature = request.headers.get('verif-hash')
    secret = os.getenv("FLUTTERWAVE_ENCRYPTION_KEY")
    
    if not signature or not secret:
        return jsonify(success=False), 400

    # Recompute hash
    computed_signature = hmac.new(
        secret.encode('utf-8'), 
        request.get_data(), 
        hashlib.sha256
    ).hexdigest()

    if signature != computed_signature:
        return jsonify(success=False), 401

    # Parse event
    event = request.get_json()
    
    if event.get("event") == "charge.completed":
        data = event.get("data", {})
        status = data.get("status")
        if status == "successful":
            # Extract metadata
            meta = data.get("meta", {})
            email = meta.get("email")
            plan = meta.get("plan", "basic")
            
            if not email:
                return jsonify(success=False), 400

            # Generate token
            raw_token = str(uuid.uuid4())[:8].upper()
            token = f"{raw_token[:4]}-{raw_token[4:]}"
            duration_hours = {'basic': 24, 'bundle': 168, 'pro': 720}[plan]
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat()
            
            payload = {
                "token": token,
                "email": email,
                "issue": "Paid session",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at,
                "active": True,
                "plan_type": plan
            }
            supabase_insert_session(payload)
            
            return jsonify(success=True), 200
    
    return jsonify(success=True), 200  # Acknowledge other events



# @app.route('/verify-payment', methods=['POST', 'OPTIONS'])
# def verify_payment():
#     """Verify Flutterwave payment and generate token"""
#     if request.method == 'OPTIONS':
#         response = app.make_response('')
#         response.headers['Access-Control-Allow-Origin'] = 'https://techfix-frontend-nc49.onrender.com'
#         response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
#         response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, Authorization'
#         return response, 200
    
#     try:
#         data = request.get_json()
#         if not data:
#             return jsonify({"error": "Invalid request"}), 400
        
#         tx_ref = data.get('tx_ref')
        
#         if not tx_ref:
#             return jsonify({"error": "Transaction reference required"}), 400
        
#         print(f"🔍 Verifying payment: {tx_ref}")
        
#         # Verify transaction with Flutterwave
#         headers = {
#             "Authorization": f"Bearer {os.getenv('FLUTTERWAVE_SECRET_KEY')}"
#         }
        
#         response = requests.get(
#             f"https://api.flutterwave.com/v3/transactions/verify_by_reference?tx_ref={tx_ref}",
#             headers=headers,
#             timeout=15
#         )
        
#         print(f"📥 Flutterwave verify status: {response.status_code}")
        
#         if response.status_code != 200:
#             print(f"❌ Flutterwave error: {response.text}")
#             return jsonify({"status": "failed", "error": "Verification failed"}), 400
        
#         verification_data = response.json()
#         print(f"📦 Verification data: {verification_data}")
        
#         if verification_data.get("status") != "success":
#             return jsonify({"status": "failed"}), 400
        
#         transaction = verification_data.get("data", {})
#         payment_status = transaction.get("status")
        
#         print(f"💳 Payment status: {payment_status}")
        
#         if payment_status == "successful":
#             # Extract metadata
#             customer = transaction.get("customer", {})
#             meta = transaction.get("meta", {})
#             email = customer.get("email") or meta.get("email")
#             plan = meta.get("plan", "basic")
            
#             print(f"✅ Payment successful for {email}, plan: {plan}")
            
#             if not email:
#                 return jsonify({"status": "failed", "error": "Email not found"}), 400
            
#             # Deactivate old sessions
#             try:
#                 deactivate_url = f"{SUPABASE_URL}/rest/v1/sessions?email=eq.{email}"
#                 requests.patch(deactivate_url, headers=HEADERS, json={"active": False}, timeout=10)
#                 print(f"🗑️ Deactivated old sessions for {email}")
#             except Exception as e:
#                 print(f"⚠️ Could not deactivate old sessions: {e}")
            
#             # Generate token
#             raw_token = str(uuid.uuid4())[:8].upper()
#             token = f"{raw_token[:4]}-{raw_token[4:]}"
            
#             # Map plan to duration
#             plan_durations = {
#                 'basic': 24,    # 24 hours
#                 'bundle': 168,  # 7 days
#                 'pro': 720      # 30 days
#             }
#             duration_hours = plan_durations.get(plan, 24)
#             expires_at = (datetime.now(timezone.utc) + timedelta(hours=duration_hours)).isoformat()
            
#             print(f"🎟️ Generated token: {token} (expires: {expires_at})")
            
#             # Create session
#             payload = {
#                 "token": token,
#                 "email": email,
#                 "issue": f"Paid session - {plan} plan",
#                 "created_at": datetime.now(timezone.utc).isoformat(),
#                 "expires_at": expires_at,
#                 "active": True,
#                 "plan_type": plan,
#                 "transaction_ref": tx_ref
#             }
            
#             if supabase_insert_session(payload):
#                 print(f"✅ Session created successfully")
#                 return jsonify({
#                     "status": "successful",
#                     "token": token,
#                     "expires_at": expires_at,
#                     "plan": plan
#                 }), 200
#             else:
#                 print(f"❌ Failed to create session in database")
#                 return jsonify({"status": "failed", "error": "Failed to create session"}), 500
        
#         elif payment_status == "pending":
#             print(f"⏳ Payment still pending")
#             return jsonify({"status": "pending"}), 200
#         else:
#             print(f"❌ Payment failed with status: {payment_status}")
#             return jsonify({"status": "failed"}), 400
            
#     except Exception as e:
#         print(f"💥 Verify payment exception: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"status": "failed", "error": "Verification error"}), 500

@app.route('/verify-payment', methods=['POST', 'OPTIONS'])
def verify_payment():
    """Verify Flutterwave payment and generate token with PROPER duration"""
    if request.method == 'OPTIONS':
        response = app.make_response('')
        response.headers['Access-Control-Allow-Origin'] = 'https://techfix-frontend-nc49.onrender.com'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept, Authorization'
        return response, 200
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400
        tx_ref = data.get('tx_ref')
        if not tx_ref:
            return jsonify({"error": "Transaction reference required"}), 400

        print(f"🔍 Verifying payment: {tx_ref}")
        headers = {
            "Authorization": f"Bearer {os.getenv('FLUTTERWAVE_SECRET_KEY')}"
        }
        response = requests.get(
            f"https://api.flutterwave.com/v3/transactions/verify_by_reference?tx_ref={tx_ref}",
            headers=headers,
            timeout=15
        )
        print(f"📥 Flutterwave verify status: {response.status_code}")
        if response.status_code != 200:
            print(f"❌ Flutterwave error: {response.text}")
            return jsonify({"status": "failed", "error": "Verification failed"}), 400

        verification_data = response.json()
        print(f"📦 Verification data: {verification_data}")
        if verification_data.get("status") != "success":
            return jsonify({"status": "failed"}), 400

        transaction = verification_data.get("data", {})
        payment_status = transaction.get("status")
        print(f"💳 Payment status: {payment_status}")

        if payment_status == "successful":
            customer = transaction.get("customer", {})
            meta = transaction.get("meta", {})
            email = customer.get("email") or meta.get("email")
            plan = meta.get("plan", "basic") # Get plan from meta
            print(f"✅ Payment successful for {email}, plan: {plan}")

            if not email:
                return jsonify({"status": "failed", "error": "Email not found"}), 400

            # Deactivate old sessions
            try:
                deactivate_url = f"{SUPABASE_URL}/rest/v1/sessions?email=eq.{email}"
                requests.patch(deactivate_url, headers=HEADERS, json={"active": False}, timeout=10)
                print(f"🗑️ Deactivated old sessions for {email}")
            except Exception as e:
                print(f"⚠️ Could not deactivate old sessions: {e}")

            # Generate token with PROPER duration based on plan
            raw_token = str(uuid.uuid4())[:8].upper()
            token = f"{raw_token[:4]}-{raw_token[4:]}"
            plan_durations = {
                'basic': 24,      # 24 hours
                'bundle': 168,    # 7 days
                'pro': 720        # 30 days
            }
            duration_hours = plan_durations.get(plan, 24) # Use plan to get duration
            now_utc = datetime.now(timezone.utc)
            expires_at = now_utc + timedelta(hours=duration_hours)
            expires_at_str = expires_at.isoformat() # Format expiry time

            print(f"🎟️ Generated token: {token}")
            print(f"   Plan: {plan}")
            print(f"   Duration: {duration_hours} hours")
            print(f"   Expires: {expires_at_str}")

            payload = {
                "token": token,
                "email": email,
                "issue": f"Paid session - {plan} plan",
                "created_at": now_utc.isoformat(),
                "expires_at": expires_at_str, # Store the calculated expiry time
                "active": True,
                "plan_type": plan, # Store the plan type
                "transaction_ref": tx_ref
            }

            if supabase_insert_session(payload):
                print(f"✅ Session created successfully")
                return jsonify({
                    "status": "successful",
                    "token": token,
                    "expires_at": expires_at_str, # Return expiry time
                    "plan": plan # Return plan type
                }), 200
            else:
                print(f"❌ Failed to create session in database")
                return jsonify({"status": "failed", "error": "Failed to create session"}), 500

        elif payment_status == "pending":
            print(f"⏳ Payment still pending")
            return jsonify({"status": "pending"}), 200
        else:
            print(f"❌ Payment failed with status: {payment_status}")
            return jsonify({"status": "failed"}), 400

    except Exception as e:
        print(f"💥 Verify payment exception: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "failed", "error": "Verification error"}), 500







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








