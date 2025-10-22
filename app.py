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
# import threading
# from datetime import datetime, timedelta, timezone
# from dotenv import load_dotenv
# from flask_cors import CORS
# import resend

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

# # # Configuration
# # SUPABASE_URL = os.getenv("SUPABASE_URL")  
# # SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# # MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# # TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL")
# # RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# # print("\n" + "="*60)
# # print("BACKEND STARTUP - Environment Check")
# # print("="*60)
# # print(f"SUPABASE_URL loaded: {bool(SUPABASE_URL)}")
# # print(f"SUPABASE_KEY loaded: {bool(SUPABASE_KEY)}")
# # print(f"MISTRAL_API_KEY loaded: {bool(MISTRAL_API_KEY)}")
# # print(f"RESEND_API_KEY loaded: {bool(RESEND_API_KEY)}")
# # print(f"TECHNICIAN_EMAIL: {TECHNICIAN_EMAIL}")
# # print("="*60 + "\n")

# # HEADERS = {
# #     "apikey": SUPABASE_KEY,
# #     "Authorization": f"Bearer {SUPABASE_KEY}",
# #     "Content-Type": "application/json"
# # }


# # # ============= RESEND EMAIL FUNCTIONS =============

# # def send_email_with_resend(to_email: str, subject: str, body: str):
# #     """Send email using Resend API"""
# #     print(f"\n📧 [EMAIL] Sending to {to_email}")
# #     print(f"   Subject: {subject}")
    
# #     try:
# #         response = requests.post(
# #             "https://api.resend.com/emails",
# #             headers={
# #                 "Authorization": f"Bearer {RESEND_API_KEY}",
# #                 "Content-Type": "application/json"
# #             },
# #             json={
# #                 "from": "TechFix AI <onboarding@resend.dev>",  # Use Resend's test domain or your verified domain
# #                 "to": [to_email],
# #                 "subject": subject,
# #                 "html": body
# #             },
# #             timeout=10
# #         )
        
# #         print(f"   Response status: {response.status_code}")
        
# #         if response.status_code == 200:
# #             print(f"✅ [EMAIL SUCCESS] Email sent to {to_email}")
# #             return True
# #         else:
# #             print(f"❌ [EMAIL FAILED] Resend error: {response.status_code}")
# #             print(f"   Details: {response.text}")
# #             return False
            
# #     except requests.exceptions.Timeout:
# #         print(f"❌ [EMAIL TIMEOUT] Request timed out")
# #         return False
# #     except Exception as e:
# #         print(f"❌ [EMAIL ERROR] {type(e).__name__}: {str(e)}")
# #         import traceback
# #         traceback.print_exc()
# #         return False


# # def send_email_async(to_email: str, subject: str, body: str):
# #     """Send email in background thread"""
# #     def _send():
# #         print(f"\n📧 [THREAD START] Email thread started")
# #         success = send_email_with_resend(to_email, subject, body)
# #         if success:
# #             print(f"✅ [THREAD END] Email sent successfully")
# #         else:
# #             print(f"❌ [THREAD END] Email failed")
    
# #     thread = threading.Thread(target=_send, daemon=True)
# #     thread.start()
# #     print(f"📧 [ASYNC] Email background thread started for {to_email}")


# # def send_help_request_email(token: str, user_email: str, issue: str, rdp_code: str):
# #     """Send help request to technician via email"""
# #     print(f"\n🚀 [HELP REQUEST] Initiating email to technician")
# #     print(f"   To: {TECHNICIAN_EMAIL}")
# #     print(f"   Token: {token}")
    
# #     # Use HTML formatting for better readability
# #     body = f"""
# #     <!DOCTYPE html>
# #     <html>
# #     <head>
# #         <style>
# #             body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
# #             .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
# #             .header {{ background: #4CAF50; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
# #             .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
# #             .info-row {{ margin: 10px 0; }}
# #             .label {{ font-weight: bold; color: #555; }}
# #             .button {{ 
# #                 display: inline-block;
# #                 background: #4CAF50;
# #                 color: white;
# #                 padding: 12px 24px;
# #                 text-decoration: none;
# #                 border-radius: 5px;
# #                 margin-top: 15px;
# #             }}
# #             .footer {{ margin-top: 20px; padding: 10px; text-align: center; color: #777; font-size: 12px; }}
# #         </style>
# #     </head>
# #     <body>
# #         <div class="container">
# #             <div class="header">
# #                 <h2>🆘 Help Request Received</h2>
# #             </div>
# #             <div class="content">
# #                 <div class="info-row">
# #                     <span class="label">Service Token:</span> {token}
# #                 </div>
# #                 <div class="info-row">
# #                     <span class="label">User Email:</span> {user_email}
# #                 </div>
# #                 <div class="info-row">
# #                     <span class="label">Issue:</span> {issue}
# #                 </div>
# #                 <div class="info-row">
# #                     <span class="label">Chrome Remote Desktop Code:</span> <code style="background: #fff; padding: 5px 10px; border-radius: 3px;">{rdp_code}</code>
# #                 </div>
                
# #                 <a href="https://remotedesktop.google.com/access" class="button">
# #                     🖥️ Connect via Chrome Remote Desktop
# #                 </a>
                
# #                 <p style="margin-top: 20px; color: #666; font-size: 14px;">
# #                     ⏱️ Session expires in 15 minutes. Please connect as soon as possible.
# #                 </p>
# #             </div>
# #             <div class="footer">
# #                 TechFix AI - Automated Tech Support
# #             </div>
# #         </div>
# #     </body>
# #     </html>
# #     """
    
# #     send_email_async(TECHNICIAN_EMAIL, f"🆘 Help Request - Token: {token}", body)






# # Configuration (at the top with other configs)
# SUPABASE_URL = os.getenv("SUPABASE_URL")  
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL")
# RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# # Initialize Resend
# resend.api_key = RESEND_API_KEY

# print("\n" + "="*60)
# print("BACKEND STARTUP - Environment Check")
# print("="*60)
# print(f"SUPABASE_URL loaded: {bool(SUPABASE_URL)}")
# print(f"SUPABASE_KEY loaded: {bool(SUPABASE_KEY)}")
# print(f"MISTRAL_API_KEY loaded: {bool(MISTRAL_API_KEY)}")
# print(f"RESEND_API_KEY loaded: {bool(RESEND_API_KEY)}")
# print(f"TECHNICIAN_EMAIL: {TECHNICIAN_EMAIL}")
# print("="*60 + "\n")

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









#!/usr/bin/env python3
"""
AI Tech Repairer - Backend with Resend Email
Token shown on frontend only
Email only used for request-human-help
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
import resend

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
TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# Initialize Resend
resend.api_key = RESEND_API_KEY

# IMPORTANT: Add HEADERS definition here (it was missing!)
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

print("\n" + "="*60)
print("BACKEND STARTUP - Environment Check")
print("="*60)
print(f"SUPABASE_URL loaded: {bool(SUPABASE_URL)}")
print(f"SUPABASE_KEY loaded: {bool(SUPABASE_KEY)}")
print(f"MISTRAL_API_KEY loaded: {bool(MISTRAL_API_KEY)}")
print(f"RESEND_API_KEY loaded: {bool(RESEND_API_KEY)}")
print(f"TECHNICIAN_EMAIL: {TECHNICIAN_EMAIL}")
print("="*60 + "\n")

# ============= RESEND EMAIL FUNCTIONS =============

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
    
    # Use HTML formatting for better readability
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
def generate_token():
    """Generate a new service token (NO EMAIL SENT)"""
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
            # Return token to frontend (no email sent here)
            return jsonify({
                "token": token,
                "expires_in": duration,
                "expires_at": expires_at,
                "email": email
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
    """Send email alert to technician ONLY"""
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
        
        # Send email to technician using Resend
        send_help_request_email(token, email, issue, rdp_code)
        
        return jsonify({"status": "sent"}), 200
        
    except Exception as e:
        print(f"Error in request_human_help: {e}")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug)




















