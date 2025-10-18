#!/usr/bin/env python3
"""
AI Tech Repairer - Backend with Mailgun Email
Works perfectly with Render (no network restrictions)
"""

from flask import Flask, request, jsonify
import requests
import uuid
import os
import json
import threading
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask_cors import CORS

app = Flask(__name__)

CORS(app, 
     origins=[
        "https://techfix-frontend-nc49.onrender.com",
        "http://localhost:5173",
        "http://localhost:3000"
     ],
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
     supports_credentials=True,
     max_age=3600
)

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")  
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL", "oladejiolaoluwa46@gmail.com")
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
MAILGUN_FROM_EMAIL = os.getenv("MAILGUN_FROM_EMAIL", "noreply@techfixai.com")
ANALYTICS_KEY = os.getenv("ANALYTICS_KEY")

print("\n" + "="*60)
print("BACKEND STARTUP - Environment Check")
print("="*60)
print(f"SUPABASE_URL loaded: {bool(SUPABASE_URL)}")
print(f"SUPABASE_KEY loaded: {bool(SUPABASE_KEY)}")
print(f"MISTRAL_API_KEY loaded: {bool(MISTRAL_API_KEY)}")
print(f"MAILGUN_API_KEY loaded: {bool(MAILGUN_API_KEY)}")
print(f"MAILGUN_DOMAIN loaded: {bool(MAILGUN_DOMAIN)}")
print(f"MAILGUN_FROM_EMAIL: {MAILGUN_FROM_EMAIL}")
print(f"TECHNICIAN_EMAIL: {TECHNICIAN_EMAIL}")
print("="*60 + "\n")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}


# ============= MAILGUN EMAIL FUNCTION =============

def send_email_mailgun(to_email: str, subject: str, body: str):
    """Send email using Mailgun API"""
    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": MAILGUN_FROM_EMAIL,
                "to": to_email,
                "subject": subject,
                "text": body
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return True, f"Email sent to {to_email}"
        else:
            return False, f"Mailgun error: {response.status_code} - {response.text}"
            
    except Exception as e:
        return False, f"Email error: {type(e).__name__}: {str(e)}"


def send_email_async(to_email: str, subject: str, body: str):
    """Send email in background thread"""
    def _send():
        success, message = send_email_mailgun(to_email, subject, body)
        if success:
            print(f"✅ {message}")
        else:
            print(f"⚠️ {message}")
    
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()


def send_token_email(to_email: str, token: str, expires_at: str):
    """Send service token to user"""
    body = f"""Hello,

Thank you for using TechFix AI!

Your 8-digit service token is: {token}

It is valid until: {expires_at}

To start your repair session:
1. Download the agent from https://techfix-frontend-nc49.onrender.com
2. Run it and enter this token.

For any issues, contact support at codepreneurs12@gmail.com.

Best regards,
TechFix AI Team
"""
    send_email_async(to_email, "Your TechFix AI Service Token", body)


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


@app.route('/test-email', methods=['GET'])
def test_email():
    """Test email configuration"""
    test_email_addr = request.args.get('email', 'test@example.com')
    
    success, message = send_email_mailgun(
        test_email_addr,
        "TechFix AI - Test Email",
        "If you received this, Mailgun email is working!"
    )
    
    return jsonify({
        "success": success,
        "message": message,
        "test_email": test_email_addr,
        "from_email": MAILGUN_FROM_EMAIL
    })


@app.route('/generate-token', methods=['POST', 'OPTIONS'])
def generate_token():
    """Generate a new service token"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
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
            send_token_email(email, token, expires_at)
            
            return jsonify({
                "token": token,
                "expires_in": duration,
                "expires_at": expires_at
            }), 201
        else:
            return jsonify({"error": "Failed to create session"}), 500
            
    except Exception as e:
        print(f"Error in generate_token: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/generate-plan', methods=['POST', 'OPTIONS'])
def generate_plan():
    """Generate repair plan using Mistral AI"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
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
        
        prompt = build_repair_prompt(issue, system_info, search_results, file_info)
        raw_plan = call_mistral_ai(prompt)
        
        if "error" in raw_plan:
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
        
        return jsonify(plan), 200
        
    except Exception as e:
        print(f"Error in generate_plan: {e}")
        return jsonify({"error": "Internal server error"}), 500


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
def request_human_help():
    """Send email alert to technician"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        token = request.json.get('token')
        email = request.json.get('email')
        issue = request.json.get('issue')
        rdp_code = request.json.get('rdp_code')
        
        sess = supabase_get_token(token)
        if not sess or not sess["active"]:
            return jsonify({"error": "Invalid session"}), 401
        
        body = f"""A user has requested live support.

Service Token: {token}
User Email: {email}
Issue: {issue}
RDP Code: {rdp_code}

Connect at: https://remotedesktop.google.com/access
"""
        
        send_email_async(TECHNICIAN_EMAIL, f"Help Request - Token: {token}", body)
        
        return jsonify({"status": "sent"}), 200
        
    except Exception as e:
        print(f"Error in request_human_help: {e}")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug)































# #!/usr/bin/env python3
# """
# AI Tech Repairer - Backend with Email Diagnostics
# """

# from flask import Flask, request, jsonify
# import requests
# import uuid
# import os
# import json
# import threading
# import time
# from datetime import datetime, timedelta, timezone
# from dotenv import load_dotenv
# from flask_cors import CORS
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart

# app = Flask(__name__)

# CORS(app, 
#      origins=[
#         "https://techfix-frontend-nc49.onrender.com",
#         "http://localhost:5173",
#         "http://localhost:3000"
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
# TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL", "oladejiolaoluwa46@gmail.com")
# GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
# GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
# ANALYTICS_KEY = os.getenv("ANALYTICS_KEY")

# print("=" * 60)
# print("BACKEND STARTUP DIAGNOSTICS")
# print("=" * 60)
# print(f"SUPABASE_URL: {SUPABASE_URL[:30]}..." if SUPABASE_URL else "❌ MISSING")
# print(f"SUPABASE_KEY: {SUPABASE_KEY[:20]}..." if SUPABASE_KEY else "❌ MISSING")
# print(f"MISTRAL_API_KEY: {MISTRAL_API_KEY[:20]}..." if MISTRAL_API_KEY else "❌ MISSING")
# print(f"GMAIL_ADDRESS: {GMAIL_ADDRESS}" if GMAIL_ADDRESS else "❌ MISSING")
# print(f"GMAIL_APP_PASSWORD: {'*' * len(GMAIL_APP_PASSWORD) if GMAIL_APP_PASSWORD else '❌ MISSING'}")
# print(f"TECHNICIAN_EMAIL: {TECHNICIAN_EMAIL}")
# print("=" * 60)

# HEADERS = {
#     "apikey": SUPABASE_KEY,
#     "Authorization": f"Bearer {SUPABASE_KEY}",
#     "Content-Type": "application/json"
# }


# # ============= EMAIL DIAGNOSTICS =============

# def test_email_send():
#     """Test if email sending works"""
#     print("\n🧪 Testing email configuration...")
#     try:
#         server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
#         print("✅ Connected to SMTP server")
        
#         server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
#         print("✅ Gmail authentication successful")
        
#         server.quit()
#         print("✅ Email configuration is WORKING")
#         return True
#     except smtplib.SMTPAuthenticationError as e:
#         print(f"❌ Gmail authentication FAILED: {e}")
#         print("   Check your GMAIL_ADDRESS and GMAIL_APP_PASSWORD")
#         return False
#     except smtplib.SMTPException as e:
#         print(f"❌ SMTP error: {e}")
#         return False
#     except Exception as e:
#         print(f"❌ Email test failed: {e}")
#         return False


# def send_email_async(to_email: str, subject: str, body: str):
#     """Send email asynchronously with detailed logging"""
#     def _send():
#         try:
#             print(f"\n📧 [Thread] Sending email to {to_email}")
            
#             msg = MIMEMultipart()
#             msg["Subject"] = subject
#             msg["From"] = GMAIL_ADDRESS
#             msg["To"] = to_email
#             msg.attach(MIMEText(body, "plain"))
            
#             print(f"📧 [Thread] Connecting to SMTP...")
#             server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
            
#             print(f"📧 [Thread] Authenticating...")
#             server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            
#             print(f"📧 [Thread] Sending message...")
#             server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
            
#             server.quit()
#             print(f"✅ [Thread] Email sent successfully to {to_email}")
            
#         except smtplib.SMTPAuthenticationError as e:
#             print(f"❌ [Thread] Gmail auth failed: {e}")
#         except smtplib.SMTPException as e:
#             print(f"❌ [Thread] SMTP error: {e}")
#         except Exception as e:
#             print(f"❌ [Thread] Email failed: {type(e).__name__}: {e}")
    
#     thread = threading.Thread(target=_send, daemon=True)
#     thread.start()
#     print(f"📧 Email thread started for {to_email}")


# def send_token_email(to_email: str, token: str, expires_at: str):
#     """Send service token to user"""
#     body = f"""Hello,

# Thank you for using TechFix AI!

# Your 8-digit service token is: {token}

# It is valid until: {expires_at}

# To start your repair session:
# 1. Download the agent from https://techfix-frontend-nc49.onrender.com
# 2. Run it and enter this token.

# For any issues, contact support at codepreneurs12@gmail.com.

# Best regards,
# TechFix AI Team
# """
#     send_email_async(to_email, "Your TechFix AI Service Token", body)


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


# # ============= API ENDPOINTS =============

# @app.route('/health', methods=['GET'])
# def health():
#     """Health check endpoint"""
#     return jsonify({
#         "status": "ok",
#         "time": datetime.now(timezone.utc).isoformat(),
#         "service": "AI Tech Repairer Backend"
#     })


# @app.route('/test-email', methods=['GET'])
# def test_email():
#     """Test email configuration"""
#     result = test_email_send()
#     return jsonify({
#         "email_working": result,
#         "gmail_address": GMAIL_ADDRESS,
#         "message": "Email configuration working!" if result else "Email configuration FAILED - check logs"
#     })


# @app.route('/generate-token', methods=['POST', 'OPTIONS'])
# def generate_token():
#     """Generate a new service token"""
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     try:
#         print("\n" + "="*60)
#         print("REQUEST: /generate-token")
#         print("="*60)
        
#         email = request.json.get('email')
#         issue = request.json.get('issue', 'Unknown issue')
#         duration = int(request.json.get('minutes', 30))
        
#         print(f"Email: {email}")
#         print(f"Issue: {issue}")
#         print(f"Duration: {duration} minutes")

#         if not email or '@' not in email:
#             return jsonify({"error": "Valid email required"}), 400

#         raw_token = str(uuid.uuid4())[:8].upper()
#         token = f"{raw_token[:4]}-{raw_token[4:]}"
#         expires_at = (datetime.now(timezone.utc) + timedelta(minutes=duration)).isoformat()

#         print(f"Generated token: {token}")
#         print(f"Expires at: {expires_at}")

#         payload = {
#             "token": token,
#             "email": email,
#             "issue": issue,
#             "created_at": datetime.now(timezone.utc).isoformat(),
#             "expires_at": expires_at,
#             "active": True,
#             "plan": None
#         }

#         print("Inserting session into Supabase...")
#         if supabase_insert_session(payload):
#             print("✅ Session inserted successfully")
            
#             print("Starting email send...")
#             send_token_email(email, token, expires_at)
            
#             response = {
#                 "token": token,
#                 "expires_in": duration,
#                 "expires_at": expires_at
#             }
#             print(f"✅ Response: {response}")
#             return jsonify(response), 201
#         else:
#             print("❌ Failed to insert session")
#             return jsonify({"error": "Failed to create session"}), 500
            
#     except Exception as e:
#         print(f"❌ Error: {type(e).__name__}: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": "Internal server error"}), 500


# @app.route('/generate-plan', methods=['POST', 'OPTIONS'])
# def generate_plan():
#     """Generate repair plan using Mistral AI"""
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     return jsonify({"error": "Not implemented yet"}), 501


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
    
#     return jsonify({"error": "Not implemented yet"}), 501


# @app.route('/request-human-help', methods=['POST', 'OPTIONS'])
# def request_human_help():
#     """Send email alert to technician"""
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     return jsonify({"error": "Not implemented yet"}), 501


# if __name__ == '__main__':
#     print("\n🚀 Starting server...\n")
    
#     # Test email on startup
#     test_email_send()
    
#     port = int(os.getenv("PORT", 8080))
#     debug = os.getenv("DEBUG", "False").lower() == "true"
#     app.run(host='0.0.0.0', port=port, debug=debug)




























# #!/usr/bin/env python3
# """
# AI Tech Repairer - Enhanced Backend with Analytics & Async Email
# Fixed: CORS issues, email timeouts, hardcoded credentials
# """

# from flask import Flask, request, jsonify
# import requests
# import uuid
# import os
# import json
# import threading
# from datetime import datetime, timedelta, timezone
# from dotenv import load_dotenv
# from flask_cors import CORS
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart

# app = Flask(__name__)

# # Configure CORS properly
# CORS(app, 
#      origins=[
#         "https://techfix-frontend-nc49.onrender.com",
#         "http://localhost:5173",
#         "http://localhost:3000"
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
# TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL", "oladejiolaoluwa46@gmail.com")
# GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
# GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
# ANALYTICS_KEY = os.getenv("ANALYTICS_KEY")

# HEADERS = {
#     "apikey": SUPABASE_KEY,
#     "Authorization": f"Bearer {SUPABASE_KEY}",
#     "Content-Type": "application/json"
# }


# # ============= ASYNC EMAIL FUNCTIONS =============

# def send_email_async(to_email: str, subject: str, body: str, is_technician=False):
#     """Send email asynchronously in background thread"""
#     def _send():
#         try:
#             msg = MIMEMultipart()
#             msg["Subject"] = subject
#             msg["From"] = GMAIL_ADDRESS
#             msg["To"] = to_email
#             msg.attach(MIMEText(body, "plain"))
            
#             # Connect with timeout to prevent hanging
#             server = smtplib.SMTP_SSL("smtp.gmail.com", 587, timeout=10)
#             server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
#             server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
#             server.quit()
            
#             print(f"✅ Email sent to {to_email}")
            
#         except smtplib.SMTPAuthenticationError:
#             print(f"❌ Gmail auth failed for {to_email}. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD")
#         except smtplib.SMTPException as e:
#             print(f"❌ SMTP error: {e}")
#         except Exception as e:
#             print(f"❌ Email error: {e}")
    
#     # Run in background so it doesn't block the API response
#     thread = threading.Thread(target=_send, daemon=True)
#     thread.start()


# def send_token_email(to_email: str, token: str, expires_at: str):
#     """Send service token to user"""
#     body = f"""Hello,

# Thank you for using TechFix AI!

# Your 8-digit service token is: {token}

# It is valid until: {expires_at}

# To start your repair session:
# 1. Download the agent from https://techfix-frontend-nc49.onrender.com
# 2. Run it and enter this token.

# For any issues, contact support at codepreneurs12@gmail.com.

# Best regards,
# TechFix AI Team
# """
#     send_email_async(to_email, "Your TechFix AI Service Token", body)


# def send_help_request_email(token: str, user_email: str, issue: str, rdp_code: str):
#     """Send help request to technician"""
#     body = f"""A user has requested live support.

# Service Token: {token}
# User Email: {user_email}
# Issue: {issue}
# RDP Code: {rdp_code}

# Connect at: https://remotedesktop.google.com/access
# """
#     send_email_async(TECHNICIAN_EMAIL, f"Help Request - Token: {token}", body, is_technician=True)


# # ============= ANALYTICS FUNCTIONS =============

# def log_analytics_event(event_type: str, metadata: dict = None):
#     """Log analytics events to Supabase"""
#     try:
#         payload = {
#             "event_type": event_type,
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#             "metadata": metadata or {},
#             "user_agent": request.headers.get('User-Agent', 'Unknown'),
#             "ip_address": request.headers.get('X-Forwarded-For', request.remote_addr)
#         }
        
#         r = requests.post(
#             f"{SUPABASE_URL}/rest/v1/analytics",
#             headers=HEADERS,
#             json=payload,
#             timeout=5
#         )
        
#         if r.status_code == 201:
#             print(f"✅ Analytics logged: {event_type}")
#         else:
#             print(f"⚠️ Analytics log failed: {r.status_code}")
            
#     except Exception as e:
#         print(f"❌ Analytics error: {e}")


# def get_analytics_summary(days: int = 7):
#     """Get analytics summary for the last N days"""
#     try:
#         start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
#         r = requests.get(
#             f"{SUPABASE_URL}/rest/v1/analytics",
#             headers=HEADERS,
#             params={
#                 "timestamp": f"gte.{start_date}",
#                 "select": "event_type,timestamp,metadata",
#                 "order": "timestamp.desc",
#                 "limit": 1000
#             },
#             timeout=10
#         )
        
#         if r.status_code == 200:
#             events = r.json()
            
#             summary = {
#                 "total_events": len(events),
#                 "tokens_generated": len([e for e in events if e["event_type"] == "token_generated"]),
#                 "ai_requests": len([e for e in events if e["event_type"] in ["ai_request_success", "ai_request_error"]]),
#                 "ai_errors": len([e for e in events if e["event_type"] == "ai_request_error"]),
#                 "agent_downloads": len([e for e in events if e["event_type"] == "agent_downloaded"]),
#                 "human_help_requests": len([e for e in events if e["event_type"] == "human_help_requested"]),
#                 "error_rate": 0,
#                 "recent_errors": []
#             }
            
#             if summary["ai_requests"] > 0:
#                 summary["error_rate"] = round((summary["ai_errors"] / summary["ai_requests"]) * 100, 2)
            
#             error_events = [e for e in events if e["event_type"] == "ai_request_error"][:10]
#             summary["recent_errors"] = [
#                 {
#                     "timestamp": e["timestamp"],
#                     "error": e["metadata"].get("error", "Unknown error"),
#                     "issue": e["metadata"].get("issue", "N/A")
#                 }
#                 for e in error_events
#             ]
            
#             return summary
        
#         return None
        
#     except Exception as e:
#         print(f"Error fetching analytics: {e}")
#         return None


# # ============= DATABASE HELPER FUNCTIONS =============

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


# # ============= AI & REPAIR FUNCTIONS =============

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
#                 "max_tokens": 2000,
#                 "response_format": {"type": "json_object"}
#             },
#             timeout=45
#         )
        
#         if resp.status_code != 200:
#             print(f"❌ Mistral API error: {resp.status_code}")
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
#         print(f"❌ Unexpected error: {e}")
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


# @app.route('/generate-token', methods=['POST', 'OPTIONS'])
# def generate_token():
#     """Generate a new service token"""
#     # Handle preflight requests
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     try:
#         email = request.json.get('email')
#         issue = request.json.get('issue', 'Unknown issue')
#         duration = int(request.json.get('minutes', 30))

#         if not email or '@' not in email:
#             return jsonify({"error": "Valid email required"}), 400

#         raw_token = str(uuid.uuid4())[:8].upper()
#         token = f"{raw_token[:4]}-{raw_token[4:]}"
#         expires_at = (datetime.now(timezone.utc) + timedelta(minutes=duration)).isoformat()

#         payload = {
#             "token": token,
#             "email": email,
#             "issue": issue,
#             "created_at": datetime.now(timezone.utc).isoformat(),
#             "expires_at": expires_at,
#             "active": True,
#             "plan": None
#         }

#         if supabase_insert_session(payload):
#             # Log analytics
#             log_analytics_event("token_generated", {
#                 "token": token,
#                 "email": email,
#                 "duration_minutes": duration
#             })
            
#             # Send email asynchronously (doesn't block response)
#             send_token_email(email, token, expires_at)
            
#             return jsonify({
#                 "token": token,
#                 "expires_in": duration,
#                 "expires_at": expires_at
#             }), 201
#         else:
#             return jsonify({"error": "Failed to create session"}), 500
            
#     except Exception as e:
#         print(f"Error in generate_token: {e}")
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
#             log_analytics_event("ai_request_error", {
#                 "token": token,
#                 "issue": issue,
#                 "error": raw_plan["error"],
#                 "os": system_info.get('os', 'Unknown')
#             })
            
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
        
#         log_analytics_event("ai_request_success", {
#             "token": token,
#             "issue": issue,
#             "software": plan.get("software", "Unknown"),
#             "steps_count": len(plan.get("steps", [])),
#             "os": system_info.get('os', 'Unknown')
#         })
        
#         return jsonify(plan), 200
        
#     except Exception as e:
#         print(f"Error in generate_plan: {e}")
#         return jsonify({"error": "Internal server error"}), 500


# @app.route('/track-download', methods=['POST', 'OPTIONS'])
# def track_download():
#     """Track agent downloads"""
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     try:
#         download_type = request.json.get('type', 'unknown')
#         version = request.json.get('version', 'unknown')
        
#         log_analytics_event("agent_downloaded", {
#             "download_type": download_type,
#             "version": version
#         })
        
#         return jsonify({"status": "tracked"}), 200
#     except Exception as e:
#         print(f"Error in track_download: {e}")
#         return jsonify({"error": "Internal server error"}), 500


# @app.route('/analytics', methods=['GET', 'OPTIONS'])
# def get_analytics():
#     """Get analytics dashboard data"""
#     if request.method == 'OPTIONS':
#         return '', 204
    
#     try:
#         auth_key = request.args.get('key')
#         if auth_key != os.getenv("ANALYTICS_KEY", "your-secret-key"):
#             return jsonify({"error": "Unauthorized"}), 401
        
#         days = int(request.args.get('days', 7))
#         summary = get_analytics_summary(days)
        
#         if summary:
#             return jsonify(summary), 200
#         else:
#             return jsonify({"error": "Failed to fetch analytics"}), 500
#     except Exception as e:
#         print(f"Error in get_analytics: {e}")
#         return jsonify({"error": "Internal server error"}), 500


# @app.route('/request-human-help', methods=['POST', 'OPTIONS'])
# def request_human_help():
#     """Send email alert to technician"""
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
        
#         # Send email asynchronously
#         send_help_request_email(token, email, issue, rdp_code)
        
#         log_analytics_event("human_help_requested", {
#             "token": token,
#             "email": email,
#             "issue": issue
#         })
        
#         return jsonify({"status": "sent"}), 200
        
#     except Exception as e:
#         print(f"Error in request_human_help: {e}")
#         return jsonify({"error": "Internal server error"}), 500


# if __name__ == '__main__':
#     port = int(os.getenv("PORT", 8080))
#     debug = os.getenv("DEBUG", "False").lower() == "true"
#     app.run(host='0.0.0.0', port=port, debug=debug)
























































# # #!/usr/bin/env python3
# # """
# # AI Tech Repairer - Enhanced Backend with Analytics
# # Tracks: token generation, AI requests, errors, and agent downloads
# # """

# # from flask import Flask, request, jsonify
# # import requests
# # import uuid
# # import os
# # import json
# # from datetime import datetime, timedelta, timezone
# # from dotenv import load_dotenv
# # from flask_cors import CORS

# # app = Flask(__name__)
# # CORS(app, 
# #      origins=[
# #         "https://techfix-frontend-nc49.onrender.com",
# #         "http://localhost:5173"
# #      ],
# #      allow_headers=["Content-Type", "Authorization"],
# #      methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
# #      supports_credentials=True
# # )

# # load_dotenv()

# # # Configuration
# # SUPABASE_URL = os.getenv("SUPABASE_URL")  
# # SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# # MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# # TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL", "oladejiolaoluwa46@gmail.com")
# # GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
# # GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
# # ANALYTICS_KEY = os.getenv("ANALYTICS_KEY")

# # HEADERS = {
# #     "apikey": SUPABASE_KEY,
# #     "Authorization": f"Bearer {SUPABASE_KEY}",
# #     "Content-Type": "application/json"
# # }




# # def log_analytics_event(event_type: str, metadata: dict = None):
# #     try:
# #         payload = {
# #             "event_type": event_type,
# #             "timestamp": datetime.now(timezone.utc).isoformat(),
# #             "metadata": metadata or {},
# #             "user_agent": request.headers.get('User-Agent', 'Unknown'),
# #             "ip_address": request.headers.get('X-Forwarded-For', request.remote_addr)
# #         }
        
# #         print(f"🔍 Attempting to log: {event_type}")
# #         print(f"📦 Payload: {payload}")
        
# #         r = requests.post(
# #             f"{SUPABASE_URL}/rest/v1/analytics",
# #             headers=HEADERS,
# #             json=payload,
# #             timeout=5
# #         )
        
# #         print(f"📤 Supabase response status: {r.status_code}")
# #         print(f"📤 Supabase response body: {r.text}")
        
# #         if r.status_code == 201:
# #             print(f"✅ Analytics logged: {event_type}")
# #         else:
# #             print(f"⚠️ Analytics log failed: {r.status_code} - {r.text}")
            
# #     except Exception as e:
# #         print(f"❌ Analytics error: {e}")
# #         import traceback
# #         traceback.print_exc()




# # def get_analytics_summary(days: int = 7):
# #     """Get analytics summary for the last N days"""
# #     try:
# #         start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
# #         r = requests.get(
# #             f"{SUPABASE_URL}/rest/v1/analytics",
# #             headers=HEADERS,
# #             params={
# #                 "timestamp": f"gte.{start_date}",
# #                 "select": "event_type,timestamp,metadata",
# #                 "order": "timestamp.desc",
# #                 "limit": 1000
# #             },
# #             timeout=10
# #         )
        
# #         if r.status_code == 200:
# #             events = r.json()
            
# #             # Calculate metrics
# #             summary = {
# #                 "total_events": len(events),
# #                 "tokens_generated": len([e for e in events if e["event_type"] == "token_generated"]),
# #                 "ai_requests": len([e for e in events if e["event_type"] in ["ai_request_success", "ai_request_error"]]),
# #                 "ai_errors": len([e for e in events if e["event_type"] == "ai_request_error"]),
# #                 "agent_downloads": len([e for e in events if e["event_type"] == "agent_downloaded"]),
# #                 "human_help_requests": len([e for e in events if e["event_type"] == "human_help_requested"]),
# #                 "error_rate": 0,
# #                 "recent_errors": []
# #             }
            
# #             # Calculate error rate
# #             if summary["ai_requests"] > 0:
# #                 summary["error_rate"] = round((summary["ai_errors"] / summary["ai_requests"]) * 100, 2)
            
# #             # Get recent error details
# #             error_events = [e for e in events if e["event_type"] == "ai_request_error"][:10]
# #             summary["recent_errors"] = [
# #                 {
# #                     "timestamp": e["timestamp"],
# #                     "error": e["metadata"].get("error", "Unknown error"),
# #                     "issue": e["metadata"].get("issue", "N/A")
# #                 }
# #                 for e in error_events
# #             ]
            
# #             return summary
        
# #         return None
        
# #     except Exception as e:
# #         print(f"Error fetching analytics: {e}")
# #         return None


# # # ============= EXISTING HELPER FUNCTIONS =============

# # def supabase_get_token(token: str):
# #     """Fetch session data from Supabase"""
# #     try:
# #         r = requests.get(
# #             f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
# #             headers=HEADERS,
# #             params={"select": "token,email,issue,active,expires_at,plan"},
# #             timeout=10
# #         )
# #         if r.status_code == 200:
# #             data = r.json()
# #             return data[0] if data else None
# #         return None
# #     except Exception as e:
# #         print(f"Supabase GET error: {e}")
# #         return None


# # def supabase_update_session(token: str, data: dict):
# #     """Update session in Supabase"""
# #     try:
# #         r = requests.patch(
# #             f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
# #             headers=HEADERS,
# #             json=data,
# #             timeout=10
# #         )
# #         return r.status_code in [200, 204]
# #     except Exception as e:
# #         print(f"Supabase UPDATE error: {e}")
# #         return False


# # def supabase_insert_session(data: dict):
# #     """Create new session in Supabase"""
# #     try:
# #         r = requests.post(
# #             f"{SUPABASE_URL}/rest/v1/sessions",
# #             headers=HEADERS,
# #             json=data,
# #             timeout=10
# #         )
# #         return r.status_code == 201
# #     except Exception as e:
# #         print(f"Supabase INSERT error: {e}")
# #         return False


# # def call_mistral_ai(prompt: str) -> dict:
# #     """Call Mistral AI API with server-side key"""
# #     try:
# #         resp = requests.post(
# #             "https://api.mistral.ai/v1/chat/completions",
# #             headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
# #             json={
# #                 "model": "mistral-small-latest",
# #                 "messages": [{"role": "user", "content": prompt}],
# #                 "temperature": 0.3,
# #                 "max_tokens": 2000,
# #                 "response_format": {"type": "json_object"}
# #             },
# #             timeout=45
# #         )
        
# #         if resp.status_code != 200:
# #             print(f"❌ Mistral API error: {resp.status_code}")
# #             return {"error": f"Mistral API error: {resp.status_code}"}
        
# #         response_data = resp.json()
# #         text = response_data["choices"][0]["message"]["content"].strip()
        
# #         # Clean up response
# #         if "```json" in text:
# #             text = text.split("```json")[1].split("```")[0]
# #         elif "```" in text:
# #             text = text.split("```")[1].split("```")[0]
        
# #         text = text.strip()
        
# #         try:
# #             plan = json.loads(text)
# #             return plan
# #         except json.JSONDecodeError:
# #             return {"error": "Failed to parse AI response"}
            
# #     except Exception as e:
# #         print(f"❌ Unexpected error: {e}")
# #         return {"error": f"Unexpected error: {str(e)}"}


# # def sanitize_plan(plan: dict, issue: str) -> dict:
# #     """Validate and sanitize the AI-generated plan"""
# #     if isinstance(plan, str):
# #         try:
# #             plan = json.loads(plan)
# #         except:
# #             return {
# #                 "software": "Unknown",
# #                 "issue": issue,
# #                 "summary": "Failed to parse AI response",
# #                 "steps": [{"description": "AI returned invalid format", "command": "echo Invalid response", "requires_sudo": False}],
# #                 "estimated_time_minutes": 5,
# #                 "needs_reboot": False
# #             }
    
# #     if "error" in plan:
# #         return {
# #             "software": "Unknown",
# #             "issue": issue,
# #             "summary": "AI service error",
# #             "steps": [{"description": plan["error"], "command": "echo AI error occurred", "requires_sudo": False}],
# #             "estimated_time_minutes": 5,
# #             "needs_reboot": False
# #         }
    
# #     sanitized = {
# #         "software": plan.get("software", "Unknown"),
# #         "issue": plan.get("issue", issue),
# #         "summary": plan.get("summary", "Repair steps"),
# #         "steps": [],
# #         "estimated_time_minutes": plan.get("estimated_time_minutes", 10),
# #         "needs_reboot": plan.get("needs_reboot", False)
# #     }
    
# #     raw_steps = plan.get("steps", [])
# #     if not raw_steps:
# #         sanitized["steps"] = [{
# #             "description": "No repair steps generated",
# #             "command": "echo No steps available",
# #             "requires_sudo": False
# #         }]
# #     else:
# #         for step in raw_steps[:6]:
# #             if isinstance(step, dict):
# #                 command = str(step.get("command", "")).strip()
# #                 if not command:
# #                     command = f"echo {step.get('description', 'Manual step')[:50]}"
                
# #                 sanitized["steps"].append({
# #                     "description": str(step.get("description", "No description"))[:300],
# #                     "command": command[:500],
# #                     "requires_sudo": bool(step.get("requires_sudo", False))
# #                 })
    
# #     return sanitized


# # def build_repair_prompt(issue: str, system_info: dict, search_results: list, file_info: dict = None) -> str:
# #     """Build the prompt for Mistral AI"""
# #     os_type = system_info.get('os', 'Windows')
    
# #     prompt = f"""
# # You are a computer repair technician AI. Generate a repair plan.

# # USER'S ISSUE: {issue}
# # SYSTEM: {os_type}

# # Output valid JSON:
# # {{
# #   "software": "name",
# #   "issue": "{issue}",
# #   "summary": "brief summary",
# #   "steps": [
# #     {{
# #       "description": "step description",
# #       "command": "actual command",
# #       "requires_sudo": true
# #     }}
# #   ],
# #   "estimated_time_minutes": 15,
# #   "needs_reboot": false
# # }}

# # Generate repair plan for: {issue}
# # """
# #     return prompt


# # # ============= API ENDPOINTS =============

# # @app.route('/health', methods=['GET'])
# # def health():
# #     """Health check endpoint"""
# #     return jsonify({
# #         "status": "ok",
# #         "time": datetime.now(timezone.utc).isoformat(),
# #         "service": "AI Tech Repairer Backend"
# #     })




# # def send_token_email(to_email: str, token: str, expires_at: str):
# #     """Send the service token to the user's email"""
# #     try:
# #         from email.mime.text import MIMEText
# #         from email.mime.multipart import MIMEMultipart
# #         import smtplib
        
# #         msg = MIMEMultipart()
# #         msg["Subject"] = f"Your TechFix AI Service Token"
# #         msg["From"] = GMAIL_ADDRESS
# #         msg["To"] = to_email
        
# #         body = f"""
# # Hello,

# # Thank you for using TechFix AI!

# # Your 8-digit service token is: **{token}**

# # It is valid until: {expires_at}

# # To start your repair session:
# # 1. Download the agent from https://techfix-frontend-nc49.onrender.com
# # 2. Run it and enter this token.

# # For any issues, contact support at codepreneurs12@gmail.com.

# # Best regards,
# # TechFix AI Team
# # """
        
# #         msg.attach(MIMEText(body, "plain"))
# #         server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
# #         server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
# #         server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
# #         server.quit()
        
# #         print(f"✅ Token email sent to {to_email}")
        
# #     except Exception as e:
# #         print(f"❌ Failed to send token email: {e}")





# # @app.route('/generate-token', methods=['POST'])
# # def generate_token():
# #     """Generate a new service token"""
# #     email = request.json.get('email')
# #     issue = request.json.get('issue', 'Unknown issue')
# #     duration = int(request.json.get('minutes', 30))

# #     if not email or '@' not in email:
# #         return jsonify({"error": "Valid email required"}), 400

# #     raw_token = str(uuid.uuid4())[:8].upper()
# #     token = f"{raw_token[:4]}-{raw_token[4:]}"
# #     expires_at = (datetime.now(timezone.utc) + timedelta(minutes=duration)).isoformat()

# #     payload = {
# #         "token": token,
# #         "email": email,
# #         "issue": issue,
# #         "created_at": datetime.now(timezone.utc).isoformat(),
# #         "expires_at": expires_at,
# #         "active": True,
# #         "plan": None
# #     }

# #     if supabase_insert_session(payload):
# #         # Log analytics event
# #         log_analytics_event("token_generated", {
# #             "token": token,
# #             "email": email,
# #             "duration_minutes": duration
# #         })
# #         send_token_email(email, token, expires_at)
# #         return jsonify({
# #             "token": token,
# #             "expires_in": duration,
# #             "expires_at": expires_at
# #         })
# #     else:
# #         return jsonify({"error": "Failed to create session"}), 500


# # @app.route('/generate-plan', methods=['POST'])
# # def generate_plan():
# #     """Generate repair plan using Mistral AI"""
# #     token = request.json.get('token')
# #     issue = request.json.get('issue')
# #     system_info = request.json.get('system_info', {})
# #     search_results = request.json.get('search_results', [])
# #     file_info = request.json.get('file_info')
    
# #     if not token or not issue:
# #         return jsonify({"error": "Token and issue required"}), 400
    
# #     sess = supabase_get_token(token)
# #     if not sess or not sess["active"]:
# #         return jsonify({"error": "Invalid or inactive session"}), 401
    
# #     # Build and call AI
# #     prompt = build_repair_prompt(issue, system_info, search_results, file_info)
# #     raw_plan = call_mistral_ai(prompt)
    
# #     # Check for errors
# #     if "error" in raw_plan:
# #         # Log error analytics
# #         log_analytics_event("ai_request_error", {
# #             "token": token,
# #             "issue": issue,
# #             "error": raw_plan["error"],
# #             "os": system_info.get('os', 'Unknown')
# #         })
        
# #         return jsonify({
# #             "software": "Unknown",
# #             "issue": issue,
# #             "summary": "AI service error",
# #             "steps": [{"description": raw_plan["error"], "command": "echo Error occurred", "requires_sudo": False}],
# #             "estimated_time_minutes": 5,
# #             "needs_reboot": False
# #         })
    
# #     # Sanitize plan
# #     plan = sanitize_plan(raw_plan, issue)
    
# #     # Save to database
# #     supabase_update_session(token, {"plan": plan})
    
# #     # Log success analytics
# #     log_analytics_event("ai_request_success", {
# #         "token": token,
# #         "issue": issue,
# #         "software": plan.get("software", "Unknown"),
# #         "steps_count": len(plan.get("steps", [])),
# #         "os": system_info.get('os', 'Unknown')
# #     })
    
# #     return jsonify(plan)


# # @app.route('/track-download', methods=['POST'])
# # def track_download():
# #     """Track agent downloads"""
# #     download_type = request.json.get('type', 'unknown')  # 'windows', 'linux', 'macos'
# #     version = request.json.get('version', 'unknown')
    
# #     log_analytics_event("agent_downloaded", {
# #         "download_type": download_type,
# #         "version": version
# #     })
    
# #     return jsonify({"status": "tracked"})


# # @app.route('/analytics', methods=['GET'])
# # def get_analytics():
# #     """Get analytics dashboard data"""
# #     # Simple authentication (you should add proper auth)
# #     auth_key = request.args.get('key')
# #     if auth_key != os.getenv("ANALYTICS_KEY", "your-secret-key"):
# #         return jsonify({"error": "Unauthorized"}), 401
    
# #     days = int(request.args.get('days', 7))
# #     summary = get_analytics_summary(days)
    
# #     if summary:
# #         return jsonify(summary)
# #     else:
# #         return jsonify({"error": "Failed to fetch analytics"}), 500


# # @app.route('/request-human-help', methods=['POST'])
# # def request_human_help():
# #     """Send email alert to technician"""
# #     token = request.json.get('token')
# #     email = request.json.get('email')
# #     issue = request.json.get('issue')
# #     rdp_code = request.json.get('rdp_code')
    
# #     sess = supabase_get_token(token)
# #     if not sess or not sess["active"]:
# #         return jsonify({"error": "Invalid session"}), 401
    
# #     try:
# #         from email.mime.text import MIMEText
# #         from email.mime.multipart import MIMEMultipart
# #         import smtplib
        
# #         msg = MIMEMultipart()
# #         msg["Subject"] = f"Human Help Requested - Token: {token}"
# #         msg["From"] = GMAIL_ADDRESS
# #         msg["To"] = TECHNICIAN_EMAIL
        
# #         body = f"""
# #         A user has requested live support.

# #         Service Token: {token}
# #         User Email: {email}
# #         Issue: {issue}
# #         RDP Code: {rdp_code}

# #         Connect at: https://remotedesktop.google.com/access
# #         """
        
# #         msg.attach(MIMEText(body, "plain"))
# #         server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
# #         # server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
# #         server.login("oladejiolaoluwa46@gmail.com","mitwfsyhlnyhmttw")
# #         server.sendmail(GMAIL_ADDRESS, TECHNICIAN_EMAIL, msg.as_string())
# #         server.quit()
        
# #         # Log analytics
# #         log_analytics_event("human_help_requested", {
# #             "token": token,
# #             "email": email,
# #             "issue": issue
# #         })
        
# #         return jsonify({"status": "sent"})
        
# #     except Exception as e:
# #         print(f"Email error: {e}")
# #         return jsonify({"error": "Failed to send email"}), 500


# # if __name__ == '__main__':
# #     port = int(os.getenv("PORT", 8080))
# #     debug = os.getenv("DEBUG", "False").lower() == "true"
# #     app.run(host='0.0.0.0', port=port, debug=debug)















































































# # # #!/usr/bin/env python3
# # # """
# # # AI Tech Repairer - Flask Backend Server
# # # Handles token validation, AI repair plan generation, and session management
# # # """

# # # from flask import Flask, request, jsonify
# # # import requests
# # # import uuid
# # # import os
# # # import json
# # # from datetime import datetime, timedelta, timezone
# # # from dotenv import load_dotenv

# # # app = Flask(__name__)
# # # load_dotenv()

# # # # Configuration
# # # SUPABASE_URL = os.getenv("SUPABASE_URL")  
# # # SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# # # MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# # # TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL", "oladejiolaoluwa46@gmail.com")
# # # GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
# # # GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# # # HEADERS = {
# # #     "apikey": SUPABASE_KEY,
# # #     "Authorization": f"Bearer {SUPABASE_KEY}",
# # #     "Content-Type": "application/json"
# # # }

# # # # Helper Functions
# # # def supabase_get_token(token: str):
# # #     """Fetch session data from Supabase"""
# # #     try:
# # #         r = requests.get(
# # #             f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
# # #             headers=HEADERS,
# # #             params={"select": "token,email,issue,active,expires_at,plan"},
# # #             timeout=10
# # #         )
# # #         if r.status_code == 200:
# # #             data = r.json()
# # #             return data[0] if data else None
# # #         return None
# # #     except Exception as e:
# # #         print(f"Supabase GET error: {e}")
# # #         return None


# # # def supabase_update_session(token: str, data: dict):
# # #     """Update session in Supabase"""
# # #     try:
# # #         r = requests.patch(
# # #             f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}",
# # #             headers=HEADERS,
# # #             json=data,
# # #             timeout=10
# # #         )
# # #         return r.status_code in [200, 204]
# # #     except Exception as e:
# # #         print(f"Supabase UPDATE error: {e}")
# # #         return False


# # # def supabase_insert_session(data: dict):
# # #     """Create new session in Supabase"""
# # #     try:
# # #         r = requests.post(
# # #             f"{SUPABASE_URL}/rest/v1/sessions",
# # #             headers=HEADERS,
# # #             json=data,
# # #             timeout=10
# # #         )
# # #         return r.status_code == 201
# # #     except Exception as e:
# # #         print(f"Supabase INSERT error: {e}")
# # #         return False




# # # def call_mistral_ai(prompt: str) -> dict:
# # #     """Call Mistral AI API with server-side key"""
# # #     try:
# # #         resp = requests.post(
# # #             "https://api.mistral.ai/v1/chat/completions",
# # #             headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"},
# # #             json={
# # #                 "model": "mistral-small-latest",
# # #                 "messages": [{"role": "user", "content": prompt}],
# # #                 "temperature": 0.3,
# # #                 "max_tokens": 2000,  # Increased from 1500
# # #                 "response_format": {"type": "json_object"}  # Force JSON response
# # #             },
# # #             timeout=45  # Increased timeout
# # #         )
        
# # #         if resp.status_code != 200:
# # #             print(f"❌ Mistral API error: {resp.status_code}")
# # #             print(f"Response: {resp.text}")
# # #             return {"error": f"Mistral API error: {resp.status_code}"}
        
# # #         response_data = resp.json()
# # #         if "choices" not in response_data or len(response_data["choices"]) == 0:
# # #             print(f"❌ Invalid Mistral response structure")
# # #             return {"error": "Invalid Mistral response"}
        
# # #         text = response_data["choices"][0]["message"]["content"].strip()
        
# # #         # Log the raw response for debugging
# # #         print(f"🤖 Mistral raw response (first 500 chars):\n{text[:500]}")
        
# # #         # Clean up the response - remove markdown code blocks
# # #         if "```json" in text:
# # #             text = text.split("```json")[1].split("```")[0]
# # #         elif "```" in text:
# # #             text = text.split("```")[1].split("```")[0]
        
# # #         text = text.strip()
        
# # #         # Try to find JSON object in the text
# # #         if not text.startswith("{"):
# # #             # Look for the first { and last }
# # #             start = text.find("{")
# # #             end = text.rfind("}")
# # #             if start != -1 and end != -1:
# # #                 text = text[start:end+1]
        
# # #         # Try to parse the JSON
# # #         try:
# # #             plan = json.loads(text)
# # #             print(f"✅ Successfully parsed JSON plan with {len(plan.get('steps', []))} steps")
# # #             return plan
# # #         except json.JSONDecodeError as e:
# # #             print(f"❌ JSON parse error: {e}")
# # #             print(f"Problematic text (first 300 chars): {text[:300]}")
            
# # #             # Try to fix common JSON issues
# # #             try:
# # #                 # Replace single quotes with double quotes
# # #                 text = text.replace("'", '"')
# # #                 # Remove trailing commas
# # #                 import re
# # #                 text = re.sub(r',(\s*[}\]])', r'\1', text)
# # #                 plan = json.loads(text)
# # #                 print(f"✅ Fixed and parsed JSON")
# # #                 return plan
# # #             except:
# # #                 print(f"❌ Could not fix JSON")
# # #                 return {"error": "Failed to parse AI response - invalid JSON format"}
            
# # #     except requests.exceptions.Timeout:
# # #         print(f"❌ Mistral API timeout")
# # #         return {"error": "Mistral API timeout"}
# # #     except Exception as e:
# # #         print(f"❌ Unexpected error: {e}")
# # #         import traceback
# # #         traceback.print_exc()
# # #         return {"error": f"Unexpected error: {str(e)}"}


# # # def sanitize_plan(plan: dict, issue: str) -> dict:
# # #     """Validate and sanitize the AI-generated plan"""
    
# # #     # If plan is still a string, try to parse it
# # #     if isinstance(plan, str):
# # #         try:
# # #             plan = json.loads(plan)
# # #         except:
# # #             return {
# # #                 "software": "Unknown",
# # #                 "issue": issue,
# # #                 "summary": "Failed to parse AI response",
# # #                 "steps": [{"description": "AI returned invalid format", "command": "echo Invalid response", "requires_sudo": False}],
# # #                 "estimated_time_minutes": 5,
# # #                 "needs_reboot": False
# # #             }
    
# # #     # Check for error in plan
# # #     if "error" in plan:
# # #         return {
# # #             "software": "Unknown",
# # #             "issue": issue,
# # #             "summary": "AI service error",
# # #             "steps": [{"description": plan["error"], "command": "echo AI error occurred", "requires_sudo": False}],
# # #             "estimated_time_minutes": 5,
# # #             "needs_reboot": False
# # #         }
    
# # #     # Ensure all required fields exist
# # #     sanitized = {
# # #         "software": plan.get("software", "Unknown"),
# # #         "issue": plan.get("issue", issue),
# # #         "summary": plan.get("summary", "Repair steps"),
# # #         "steps": [],
# # #         "estimated_time_minutes": plan.get("estimated_time_minutes", 10),
# # #         "needs_reboot": plan.get("needs_reboot", False)
# # #     }
    
# # #     # Validate and sanitize steps
# # #     raw_steps = plan.get("steps", [])
# # #     if not raw_steps:
# # #         sanitized["steps"] = [{
# # #             "description": "No repair steps generated",
# # #             "command": "echo No steps available",
# # #             "requires_sudo": False
# # #         }]
# # #     else:
# # #         for step in raw_steps[:6]:  # Max 6 steps
# # #             if isinstance(step, dict):
# # #                 # Ensure command is never empty
# # #                 command = str(step.get("command", "")).strip()
# # #                 if not command:
# # #                     command = f"echo {step.get('description', 'Manual step')[:50]}"
                
# # #                 sanitized["steps"].append({
# # #                     "description": str(step.get("description", "No description"))[:300],
# # #                     "command": command[:500],
# # #                     "requires_sudo": bool(step.get("requires_sudo", False))
# # #                 })
# # #             elif isinstance(step, str):
# # #                 # If step is just a string, make it a proper dict
# # #                 sanitized["steps"].append({
# # #                     "description": step[:300],
# # #                     "command": f"echo {step[:50]}",
# # #                     "requires_sudo": False
# # #                 })
    
# # #     # Validate numeric fields
# # #     try:
# # #         sanitized["estimated_time_minutes"] = max(1, min(120, int(sanitized["estimated_time_minutes"])))
# # #     except (ValueError, TypeError):
# # #         sanitized["estimated_time_minutes"] = 10
    
# # #     sanitized["needs_reboot"] = bool(sanitized.get("needs_reboot", False))
    
# # #     return sanitized





# # # def build_repair_prompt(issue: str, system_info: dict, search_results: list, file_info: dict = None) -> str:
# # #     """Build the prompt for Mistral AI"""
# # #     context = "\n".join([f"- {res}" for res in search_results if res and res.strip()])
# # #     if not context:
# # #         context = "No relevant online solutions found."
    
# # #     file_context = ""
# # #     if file_info and "error" not in file_info:
# # #         file_context = f"""
# # # Application File Information:
# # # - File: {file_info.get('filename', 'Unknown')}
# # # - Path: {file_info.get('path', 'Unknown')}
# # # - Directory: {file_info.get('directory', 'Unknown')}
# # # - Size: {file_info.get('size', 'Unknown')} bytes
# # # - Modified: {file_info.get('modified', 'Unknown')}
# # # """
# # #         if 'version' in file_info:
# # #             file_context += f"- Version: {file_info['version']}\n"
    
# # #     needs_reboot = any(kw in issue.lower() for kw in ['reboot', 'restart', 'shutdown', 'boot', 'startup'])
    
# # #     prompt = f"""
# # # You are a computer repair technician AI. You MUST respond with ONLY a valid JSON object, no other text.

# # # USER'S ISSUE: {issue}

# # # SYSTEM: {os_type} - {system_info.get('platform', 'Unknown')}

# # # SEARCH RESULTS: 
# # # {chr(10).join(f"- {result}" for result in search_results[:3]) if search_results else "None"}

# # # {f"FILE: {file_info.get('filename', 'N/A')} at {file_info.get('path', 'N/A')}" if file_info else ""}

# # # REQUIRED JSON OUTPUT FORMAT (respond with ONLY this, no markdown, no explanations):
# # # {{
# # #   "software": "software name",
# # #   "issue": "{issue}",
# # #   "summary": "Brief summary of repair approach",
# # #   "steps": [
# # #     {{
# # #       "description": "Step description",
# # #       "command": "exact command (never empty or null)",
# # #       "requires_sudo": true
# # #     }}
# # #   ],
# # #   "estimated_time_minutes": 15,
# # #   "needs_reboot": false
# # # }}

# # # COMMANDS FOR {os_type}:
# # # Windows:
# # # - ipconfig /flushdns (flush DNS, admin)
# # # - netsh winsock reset (reset network, admin)
# # # - sfc /scannow (system file check, admin)
# # # - cleanmgr /sagerun:1 (disk cleanup, admin)
# # # - defrag C: /O (defragment, admin)
# # # - del /q /f /s %TEMP%\\* (clear temp files)
# # # - net stop ServiceName (stop service, admin)
# # # - net start ServiceName (start service, admin)

# # # Linux:
# # # - sudo apt update && sudo apt upgrade -y
# # # - sudo systemctl restart service_name
# # # - sudo apt clean
# # # - sudo apt --fix-broken install

# # # RULES:
# # # 1. Respond with ONLY the JSON object
# # # 2. Every step MUST have a non-empty "command" field
# # # 3. If informational only, use: "echo Step information here"
# # # 4. Max 6 steps
# # # 5. Match commands to OS: {os_type}
# # # 6. Be specific and actionable

# # # Generate JSON for: {issue}
# # # """
    
# # #     return prompt




# # # # API Endpoints

# # # @app.route('/health', methods=['GET'])
# # # def health():
# # #     """Health check endpoint"""
# # #     return jsonify({
# # #         "status": "ok",
# # #         "time": datetime.now(timezone.utc).isoformat(),
# # #         "service": "AI Tech Repairer Backend"
# # #     })


# # # @app.route('/generate-token', methods=['POST'])
# # # def generate_token():
# # #     """Generate a new service token"""
# # #     email = request.json.get('email')
# # #     issue = request.json.get('issue', 'Unknown issue')
# # #     duration = int(request.json.get('minutes', 30))

# # #     if not email or '@' not in email:
# # #         return jsonify({"error": "Valid email required"}), 400

# # #     raw_token = str(uuid.uuid4())[:8].upper()
# # #     token = f"{raw_token[:4]}-{raw_token[4:]}"

# # #     expires_at = (datetime.now(timezone.utc) + timedelta(minutes=duration)).isoformat()

# # #     payload = {
# # #         "token": token,
# # #         "email": email,
# # #         "issue": issue,
# # #         "created_at": datetime.now(timezone.utc).isoformat(),
# # #         "expires_at": expires_at,
# # #         "active": True,
# # #         "plan": None
# # #     }

# # #     if supabase_insert_session(payload):
# # #         return jsonify({
# # #             "token": token,
# # #             "expires_in": duration,
# # #             "expires_at": expires_at
# # #         })
# # #     else:
# # #         return jsonify({"error": "Failed to create session"}), 500


# # # @app.route('/validate-token/<token>', methods=['GET'])
# # # def validate_token(token):
# # #     """Validate a service token"""
# # #     sess = supabase_get_token(token)
# # #     if not sess:
# # #         return jsonify({"valid": False, "error": "Invalid token"}), 404

# # #     if not sess["active"]:
# # #         return jsonify({"valid": False, "error": "Session inactive"}), 403

# # #     try:
# # #         exp_str = sess["expires_at"].strip()
# # #         if exp_str.endswith('Z'):
# # #             exp_str = exp_str[:-1] + '+00:00'
# # #         exp = datetime.fromisoformat(exp_str)
# # #         now_utc = datetime.now(timezone.utc)

# # #         if now_utc > exp:
# # #             supabase_update_session(token, {"active": False})
# # #             return jsonify({"valid": False, "error": "Session expired"}), 403

# # #         return jsonify({
# # #             "valid": True,
# # #             "email": sess["email"],
# # #             "issue": sess["issue"],
# # #             "expires_at": sess["expires_at"]
# # #         })

# # #     except Exception as e:
# # #         print(f"Validation error: {e}")
# # #         return jsonify({"valid": False, "error": "Invalid timestamp"}), 500



# # # @app.route('/generate-plan', methods=['POST'])
# # # def generate_plan():
# # #     """Generate repair plan using Mistral AI (server-side)"""
# # #     token = request.json.get('token')
# # #     issue = request.json.get('issue')
# # #     system_info = request.json.get('system_info', {})
# # #     search_results = request.json.get('search_results', [])
# # #     file_info = request.json.get('file_info')
    
# # #     if not token or not issue:
# # #         return jsonify({"error": "Token and issue required"}), 400
    
# # #     # Validate token
# # #     sess = supabase_get_token(token)
# # #     if not sess or not sess["active"]:
# # #         return jsonify({"error": "Invalid or inactive session"}), 401
    
# # #     # Check expiration
# # #     try:
# # #         exp_str = sess["expires_at"].strip()
# # #         if exp_str.endswith('Z'):
# # #             exp_str = exp_str[:-1] + '+00:00'
# # #         exp = datetime.fromisoformat(exp_str)
# # #         if datetime.now(timezone.utc) > exp:
# # #             return jsonify({"error": "Session expired"}), 403
# # #     except:
# # #         return jsonify({"error": "Invalid session data"}), 500
    
# # #     # Build enhanced prompt with explicit command requirements
# # #     os_type = system_info.get('os', 'Windows')
    
# # #     prompt = f"""
# # # You are a computer repair technician AI. Generate a detailed repair plan for this issue:

# # # **USER'S ISSUE**: {issue}

# # # **SYSTEM INFO**: {os_type} - {system_info.get('platform', 'Unknown')}

# # # **SEARCH RESULTS**: 
# # # {chr(10).join(f"- {result}" for result in search_results[:3])}

# # # {f"**FILE INFO**: {file_info.get('filename', 'N/A')} at {file_info.get('path', 'N/A')}" if file_info else ""}

# # # **CRITICAL REQUIREMENTS**:
# # # Each repair step MUST include:
# # # 1. "description": Clear description of what the step does
# # # 2. "command": The EXACT command to run (NEVER empty, NEVER null)
# # # 3. "requires_sudo": true if needs administrator/root privileges

# # # **OUTPUT FORMAT** (Valid JSON only):
# # # {{
# # #   "software": "Detected software name",
# # #   "issue": "{issue}",
# # #   "summary": "Brief 1-2 sentence summary of the repair approach",
# # #   "steps": [
# # #     {{
# # #       "description": "Step 1 description",
# # #       "command": "actual_command_here",
# # #       "requires_sudo": true
# # #     }},
# # #     {{
# # #       "description": "Step 2 description", 
# # #       "command": "another_command",
# # #       "requires_sudo": false
# # #     }}
# # #   ],
# # #   "estimated_time_minutes": 15,
# # #   "needs_reboot": false
# # # }}

# # # **COMMON COMMANDS FOR WINDOWS**:
# # # - Flush DNS: ipconfig /flushdns (admin required)
# # # - Reset Winsock: netsh winsock reset (admin required)
# # # - Reset TCP/IP: netsh int ip reset (admin required)
# # # - System File Check: sfc /scannow (admin required)
# # # - DISM Repair: DISM /Online /Cleanup-Image /RestoreHealth (admin required)
# # # - Disk Cleanup: cleanmgr /sagerun:1 (admin required)
# # # - Defragment: defrag C: /O (admin required)
# # # - Check Disk: chkdsk C: /f (admin required)
# # # - Clear Temp: del /q /f /s %TEMP%\\* (no admin)
# # # - Stop Service: net stop ServiceName (admin required)
# # # - Start Service: net start ServiceName (admin required)
# # # - Restart DNS Client: net stop Dnscache && net start Dnscache (admin required)

# # # **COMMON COMMANDS FOR LINUX**:
# # # - Update packages: sudo apt update && sudo apt upgrade -y
# # # - Restart service: sudo systemctl restart service_name
# # # - Clear cache: sudo apt clean
# # # - Fix broken packages: sudo apt --fix-broken install
# # # - Remove package: sudo apt remove package_name -y

# # # **COMMON COMMANDS FOR MACOS**:
# # # - Flush DNS: sudo dscacheutil -flushcache
# # # - Restart service: sudo launchctl restart service_name
# # # - Repair permissions: sudo diskutil resetUserPermissions / `id -u`

# # # **IMPORTANT**:
# # # - Every step MUST have a real command (never empty string or null)
# # # - If a step is informational only (like "Save your work"), use a command like "echo Informational step"
# # # - Match commands to the operating system: {os_type}
# # # - Set needs_reboot to true only if system restart is genuinely required
# # # - Prioritize executable commands over manual instructions

# # # Generate the complete JSON repair plan for: {issue}
# # # """
    
# # #     # Call Mistral AI
# # #     raw_plan = call_mistral_ai(prompt)
    
# # #     if "error" in raw_plan:
# # #         return jsonify({
# # #             "software": "Unknown",
# # #             "issue": issue,
# # #             "summary": "AI service error",
# # #             "steps": [{"description": raw_plan["error"], "command": "echo Error occurred", "requires_sudo": False}],
# # #             "estimated_time_minutes": 5,
# # #             "needs_reboot": False
# # #         })
    
# # #     # Sanitize and validate plan (ensure all commands are present)
# # #     plan = sanitize_plan(raw_plan, issue)
    
# # #     # Final validation: ensure no empty commands
# # #     if "steps" in plan:
# # #         for step in plan["steps"]:
# # #             if not step.get("command") or step.get("command").strip() == "":
# # #                 # Provide a default informational command
# # #                 step["command"] = f"echo {step.get('description', 'Manual step')}"
# # #                 step["requires_sudo"] = False
    
# # #     # Save to database
# # #     supabase_update_session(token, {"plan": plan})
    
# # #     return jsonify(plan)

# # # @app.route('/get-plan', methods=['GET'])
# # # def get_plan():
# # #     """Retrieve saved repair plan"""
# # #     token = request.args.get('token')
    
# # #     if not token:
# # #         return jsonify({"error": "Token required"}), 400
    
# # #     sess = supabase_get_token(token)
# # #     if sess and sess["active"] and sess["plan"]:
# # #         return jsonify(sess["plan"])
    
# # #     return jsonify({}), 204


# # # @app.route('/update-session', methods=['POST'])
# # # def update_session():
# # #     """Update session data"""
# # #     token = request.json.get('token')
# # #     updates = request.json.get('updates', {})
    
# # #     if not token:
# # #         return jsonify({"error": "Token required"}), 400
    
# # #     sess = supabase_get_token(token)
# # #     if not sess:
# # #         return jsonify({"error": "Invalid token"}), 404
    
# # #     if supabase_update_session(token, updates):
# # #         return jsonify({"status": "updated"})
# # #     else:
# # #         return jsonify({"error": "Update failed"}), 500



# # # @app.route('/request-human-help', methods=['POST'])
# # # def request_human_help():
# # #     """Send email alert to technician (server-side)"""
# # #     token = request.json.get('token')
# # #     email = request.json.get('email')
# # #     issue = request.json.get('issue')
# # #     rdp_code = request.json.get('rdp_code')
    
# # #     # Validate token
# # #     sess = supabase_get_token(token)
# # #     if not sess or not sess["active"]:
# # #         return jsonify({"error": "Invalid session"}), 401
    
# # #     try:
# # #         from email.mime.text import MIMEText
# # #         from email.mime.multipart import MIMEMultipart
# # #         import smtplib
        
# # #         GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
# # #         GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
# # #         TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL")
        
# # #         msg = MIMEMultipart()
# # #         msg["Subject"] = f"Human Help Requested - Token: {token}"
# # #         msg["From"] = GMAIL_ADDRESS
# # #         msg["To"] = TECHNICIAN_EMAIL
        
# # #         body = f"""
# # #         A user has requested live support.

# # #         Service Token: {token}
# # #         User Email: {email}
# # #         Issue: {issue}
# # #         RDP Code: {rdp_code}

# # #         Connect at: https://remotedesktop.google.com/access
# # #         Session expires in 15 minutes.
# # #         """
        
# # #         msg.attach(MIMEText(body, "plain"))
# # #         server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
# # #         server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
# # #         server.sendmail(GMAIL_ADDRESS, TECHNICIAN_EMAIL, msg.as_string())
# # #         server.quit()
        
# # #         return jsonify({"status": "sent"})
        
# # #     except Exception as e:
# # #         print(f"Email error: {e}")
# # #         return jsonify({"error": "Failed to send email"}), 500        
        


# # # if __name__ == '__main__':
# # #     port = int(os.getenv("PORT", 8080))
# # #     debug = os.getenv("DEBUG", "False").lower() == "true"
# # #     app.run(host='0.0.0.0', port=port, debug=debug)
