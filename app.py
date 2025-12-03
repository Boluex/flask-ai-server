#!/usr/bin/env python3
"""
AI Tech Repairer - Backend (Final Production Version)
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

app = Flask(__name__)
load_dotenv()

# ============= CONFIGURATION =============
SUPABASE_URL = os.getenv("SUPABASE_URL")  
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
TECHNICIAN_EMAIL = os.getenv("TECHNICIAN_EMAIL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
ANALYTICS_API_KEY = "6G4xjZrP7IebKXnVvNQwphH0VvQdXqv9nTjKFXLae+M="

resend.api_key = RESEND_API_KEY

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ============= CORS =============
if os.getenv("FLASK_ENV") == "production":
    CORS(app, resources={r"/*": {"origins": ["https://techfix-frontend-nc49.onrender.com"], "methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization", "Accept"], "supports_credentials": True}})
else:
    CORS(app, resources={r"/*": {"origins": ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"], "methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization", "Accept"], "supports_credentials": True}})

# Security storage
rate_limit_storage = defaultdict(list)
failed_attempts = defaultdict(list)
RATE_LIMIT = 5
RATE_LIMIT_WINDOW = 60
FAILED_ATTEMPT_THRESHOLD = 10
FAILED_ATTEMPT_WINDOW = 300

print(f"\n{'='*60}\nBACKEND STARTUP\n{'='*60}\nEnvironment: {os.getenv('FLASK_ENV', 'development')}\nSupabase: {bool(SUPABASE_URL)}\nMistral: {bool(MISTRAL_API_KEY)}\n{'='*60}\n")

# ============= SECURITY FUNCTIONS =============

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = get_client_ip()
        current_time = time.time()
        rate_limit_storage[client_ip] = [t for t in rate_limit_storage[client_ip] if current_time - t < RATE_LIMIT_WINDOW]
        if len(rate_limit_storage[client_ip]) >= RATE_LIMIT:
            time.sleep(0.1)
            return jsonify({"error": "Too many requests", "retry_after": 60}), 429
        rate_limit_storage[client_ip].append(current_time)
        return f(*args, **kwargs)
    return decorated_function

def obfuscate_response():
    time.sleep(secrets.randbelow(100) / 1000)

def validate_email(email):
    return email and '@' in email and '.' in email and len(email) <= 254

def sanitize_string(text, max_length=500):
    if not text: return ""
    text = str(text).strip()
    for char in ['<', '>', '"', "'", ';', '&', '|', '`']:
        text = text.replace(char, '')
    return text[:max_length]

def track_failed_attempt(identifier=None):
    identifier = identifier or get_client_ip()
    current_time = time.time()
    failed_attempts[identifier] = [t for t in failed_attempts[identifier] if current_time - t < FAILED_ATTEMPT_WINDOW]
    failed_attempts[identifier].append(current_time)
    
    # ✅ FIX 1: Restore Security Alert Logic
    if len(failed_attempts[identifier]) >= FAILED_ATTEMPT_THRESHOLD:
        print(f"⚠️ SECURITY ALERT: Too many failed attempts from {identifier}")

def is_ip_blocked(identifier=None):
    identifier = identifier or get_client_ip()
    current_time = time.time()
    failed_attempts[identifier] = [t for t in failed_attempts[identifier] if current_time - t < FAILED_ATTEMPT_WINDOW]
    return len(failed_attempts[identifier]) >= FAILED_ATTEMPT_THRESHOLD

# ============= DATABASE FUNCTIONS =============

# def supabase_insert_event(event_type, meta=None):
#     try:
#         requests.post(f"{SUPABASE_URL}/rest/v1/analytics_events", headers=HEADERS, json={"event_type": event_type, "created_at": datetime.now(timezone.utc).isoformat(), "meta": meta or {}}, timeout=2)
#     except: pass


# def supabase_insert_event(event_type, meta=None):
#     """Insert analytics event with proper error logging"""
#     try:
#         payload = {
#             "event_type": event_type,
#             "created_at": datetime.now(timezone.utc).isoformat(),
#             "meta": meta or {}
#         }
        
#         print(f"📊 Inserting event: {event_type}")
#         print(f"   Payload: {payload}")
        
#         response = requests.post(
#             f"{SUPABASE_URL}/rest/v1/analytics_events",
#             headers=HEADERS,
#             json=payload,
#             timeout=5
#         )
        
#         print(f"📊 Response status: {response.status_code}")
        
#         if response.status_code == 201:
#             print(f"✅ Event '{event_type}' tracked successfully")
#             return True
#         else:
#             print(f"❌ Event tracking failed: {response.status_code}")
#             print(f"   Response: {response.text}")
#             return False
            
#     except Exception as e:
#         print(f"❌ Event tracking error: {type(e).__name__}: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return False






def supabase_insert_event(event_type, meta=None):
    """Insert analytics event with enhanced tracking (IP, user agent, etc.)"""
    try:
        # Get client information
        client_ip = get_client_ip()
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        now_utc = datetime.now(timezone.utc).isoformat()
        
        payload = {
            "event_type": event_type,
            "timestamp": now_utc,
            "created_at": now_utc,
            "metadata": meta or {},
            "ip_address": client_ip,
            "user_agent": user_agent
        }
        
        print(f"📊 Tracking event: {event_type} from {client_ip}")
        
        # Insert into the new 'analytics' table
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/analytics",
            headers=HEADERS,
            json=payload,
            timeout=5
        )
        
        if response.status_code == 201:
            print(f"✅ Event '{event_type}' tracked successfully")
            return True
        else:
            print(f"❌ Event tracking failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Event tracking error: {type(e).__name__}: {str(e)}")
        return False




def supabase_get_token(token: str):
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}", headers=HEADERS, params={"select": "*"}, timeout=10)
        if r.status_code == 200 and r.json():
            session = r.json()[0]
            expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00'))
            if datetime.now(timezone.utc) >= expires_at:
                return None
            return session
        return None
    except: return None

def supabase_update_session(token: str, data: dict):
    try:
        requests.patch(f"{SUPABASE_URL}/rest/v1/sessions?token=eq.{token}", headers=HEADERS, json=data, timeout=10)
    except: pass

def supabase_insert_session(data: dict):
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/sessions", headers=HEADERS, json=data, timeout=10)
        return r.status_code == 201
    except: return False

# ============= EMAIL FUNCTIONS =============

def send_email_async(to_email, subject, body):
    def _send():
        try:
            resend.Emails.send({"from": "TechFix AI <onboarding@resend.dev>", "to": [to_email], "subject": subject, "html": body})
            print(f"✅ Email sent to {to_email}")
        except Exception as e:
            print(f"❌ Email error: {e}")
    threading.Thread(target=_send, daemon=True).start()

def send_help_request_email(token, user_email, issue, anydesk_code):
    body = f"""<h1>🆘 Help Request</h1><p><b>User:</b> {user_email}</p><p><b>Token:</b> {token}</p><p><b>Issue:</b> {issue}</p><p><b>AnyDesk:</b> {anydesk_code}</p>"""
    send_email_async(TECHNICIAN_EMAIL, f"Help Request: {token}", body)

# ============= AI FUNCTIONS =============

def call_mistral_ai(prompt: str) -> dict:
    try:
        resp = requests.post("https://api.mistral.ai/v1/chat/completions", headers={"Authorization": f"Bearer {MISTRAL_API_KEY}"}, json={"model": "mistral-small-latest", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 2000, "response_format": {"type": "json_object"}}, timeout=45)
        if resp.status_code != 200: return {"error": f"AI API error: {resp.status_code}"}
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if "```json" in content: content = content.split("```json")[1].split("```")[0]
        return json.loads(content.strip())
    except Exception as e:
        return {"error": str(e)}

def sanitize_plan(plan: dict, issue: str) -> dict:
    if isinstance(plan, str):
        try: plan = json.loads(plan)
        except: return {"software": "Unknown", "issue": issue, "summary": "Invalid AI response", "steps": [{"description": "AI error", "command": "echo Error", "requires_sudo": False}], "estimated_time_minutes": 5, "needs_reboot": False}
    
    if "error" in plan:
        return {"software": "Unknown", "issue": issue, "summary": "AI service error", "steps": [{"description": plan["error"], "command": "echo Error", "requires_sudo": False}], "estimated_time_minutes": 5, "needs_reboot": False}
    
    sanitized = {"software": plan.get("software", "Unknown"), "issue": plan.get("issue", issue), "summary": plan.get("summary", "Repair steps"), "steps": [], "estimated_time_minutes": plan.get("estimated_time_minutes", 10), "needs_reboot": plan.get("needs_reboot", False)}
    
    for step in plan.get("steps", [])[:6]:
        if isinstance(step, dict):
            sanitized["steps"].append({"description": str(step.get("description", "No description"))[:300], "command": str(step.get("command", f"echo {step.get('description', 'Manual step')[:50]}"))[:500], "requires_sudo": bool(step.get("requires_sudo", False))})
    
    return sanitized

def build_repair_prompt(issue: str, system_info: dict) -> str:
    os_type = system_info.get('os', 'Windows')
    return f"""You are a computer repair technician AI. Generate a repair plan for: {issue}
SYSTEM: {os_type}
Output valid JSON:
{{
  "software": "name",
  "issue": "{issue}",
  "summary": "brief summary",
  "steps": [{{"description": "step", "command": "command", "requires_sudo": true}}],
  "estimated_time_minutes": 15,
  "needs_reboot": false
}}"""

# ============= API ENDPOINTS =============

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "TechFix Backend", "time": datetime.now(timezone.utc).isoformat()})

# @app.route('/analytics', methods=['GET', 'OPTIONS'])
# def get_analytics():
#     """Analytics Dashboard Endpoint"""
#     if request.method == 'OPTIONS': return '', 204
    
#     key = request.args.get('key', '').replace(' ', '+')
#     if key != ANALYTICS_API_KEY:
#         obfuscate_response()
#         return jsonify({"error": "Unauthorized"}), 401
    
#     try:
#         days = int(request.args.get('days', 7))
#         cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
#         # Fetch sessions
#         r_sessions = requests.get(f"{SUPABASE_URL}/rest/v1/sessions?created_at=gte.{cutoff}&select=created_at,plan,issue", headers=HEADERS, timeout=10)
#         sessions = r_sessions.json() if r_sessions.status_code == 200 else []
        
#         # Fetch events (failsafe if table doesn't exist)
#         try:
#             r_events = requests.get(f"{SUPABASE_URL}/rest/v1/analytics_events?created_at=gte.{cutoff}&select=event_type", headers=HEADERS, timeout=5)
#             events = r_events.json() if r_events.status_code == 200 else []
#         except:
#             events = []
        
#         tokens_generated = len(sessions)
#         ai_requests = 0
#         ai_errors = 0
#         recent_errors = []
        
#         for s in sessions:
#             plan = s.get('plan')
#             if plan:
#                 ai_requests += 1
#                 error_msg = None
                
#                 # ✅ FIX 3: Improved Analytics Error Logic (Fewer False Positives)
#                 if isinstance(plan, dict):
#                     # Only flag if specific keys indicate failure
#                     if 'error' in plan or plan.get('summary') == 'AI service error' or plan.get('software') == 'Unknown':
#                         error_msg = plan.get('error', 'Unknown Error')
#                 # Removed the string check 'error' in plan.lower() to prevent false positives
                
#                 if error_msg:
#                     ai_errors += 1
#                     if len(recent_errors) < 5:
#                         recent_errors.append({"timestamp": s.get('created_at'), "issue": s.get('issue'), "error": error_msg})
        
#         return jsonify({
#             "tokens_generated": tokens_generated,
#             "ai_requests": ai_requests,
#             "agent_downloads": sum(1 for e in events if e.get('event_type') == 'download'),
#             "ai_errors": ai_errors,
#             "error_rate": round((ai_errors / ai_requests * 100), 1) if ai_requests > 0 else 0,
#             "human_help_requests": sum(1 for e in events if e.get('event_type') == 'human_help'),
#             "total_events": tokens_generated + len(events),
#             "recent_errors": recent_errors
#         })
#     except Exception as e:
#         print(f"Analytics Error: {e}")
#         return jsonify({"error": str(e)}), 500






# @app.route('/analytics', methods=['GET', 'OPTIONS'])
# def get_analytics():
#     """Analytics Dashboard Endpoint - FIXED VERSION"""
#     if request.method == 'OPTIONS': 
#         return '', 204
    
#     key = request.args.get('key', '').replace(' ', '+')
#     if key != ANALYTICS_API_KEY:
#         obfuscate_response()
#         return jsonify({"error": "Unauthorized"}), 401
    
#     try:
#         days = int(request.args.get('days', 7))
#         cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
#         print(f"🔍 Fetching analytics for last {days} days (cutoff: {cutoff})")
        
#         # Fetch sessions
#         r_sessions = requests.get(
#             f"{SUPABASE_URL}/rest/v1/sessions?created_at=gte.{cutoff}&select=created_at,plan,issue", 
#             headers=HEADERS, 
#             timeout=10
#         )
        
#         if r_sessions.status_code == 200:
#             sessions = r_sessions.json()
#             print(f"✅ Fetched {len(sessions)} sessions")
#         else:
#             print(f"❌ Sessions fetch failed: {r_sessions.status_code}")
#             sessions = []
        
#         # Fetch events with better error handling
#         events = []
#         try:
#             r_events = requests.get(
#                 f"{SUPABASE_URL}/rest/v1/analytics_events?created_at=gte.{cutoff}&select=event_type,created_at", 
#                 headers=HEADERS, 
#                 timeout=10
#             )
            
#             print(f"📊 Events response status: {r_events.status_code}")
#             print(f"📊 Events response body: {r_events.text[:200]}")
            
#             if r_events.status_code == 200:
#                 events = r_events.json()
#                 print(f"✅ Fetched {len(events)} events")
                
#                 # Debug: Print event types
#                 event_types = [e.get('event_type') for e in events]
#                 print(f"📋 Event types found: {event_types}")
#             else:
#                 print(f"⚠️ Events fetch returned status {r_events.status_code}: {r_events.text}")
                
#         except requests.exceptions.Timeout:
#             print("⏱️ Events fetch timed out")
#         except Exception as e:
#             print(f"❌ Events fetch error: {type(e).__name__}: {str(e)}")
        
#         # Calculate metrics
#         tokens_generated = len(sessions)
#         ai_requests = 0
#         ai_errors = 0
#         recent_errors = []
        
#         for s in sessions:
#             plan = s.get('plan')
#             if plan:
#                 ai_requests += 1
#                 error_msg = None
                
#                 if isinstance(plan, dict):
#                     if 'error' in plan or plan.get('summary') == 'AI service error' or plan.get('software') == 'Unknown':
#                         error_msg = plan.get('error', 'Unknown Error')
                
#                 if error_msg:
#                     ai_errors += 1
#                     if len(recent_errors) < 5:
#                         recent_errors.append({
#                             "timestamp": s.get('created_at'),
#                             "issue": s.get('issue'),
#                             "error": error_msg
#                         })
        
#         # Count events
#         agent_downloads = sum(1 for e in events if e.get('event_type') == 'download')
#         human_help_requests = sum(1 for e in events if e.get('event_type') == 'human_help')
        
#         print(f"📈 Calculated metrics:")
#         print(f"   - Downloads: {agent_downloads}")
#         print(f"   - Human help: {human_help_requests}")
#         print(f"   - Total events: {len(events)}")
        
#         result = {
#             "tokens_generated": tokens_generated,
#             "ai_requests": ai_requests,
#             "agent_downloads": agent_downloads,
#             "ai_errors": ai_errors,
#             "error_rate": round((ai_errors / ai_requests * 100), 1) if ai_requests > 0 else 0,
#             "human_help_requests": human_help_requests,
#             "total_events": tokens_generated + len(events),
#             "recent_errors": recent_errors,
#             # Debug info
#             "_debug": {
#                 "sessions_count": len(sessions),
#                 "events_count": len(events),
#                 "cutoff_date": cutoff
#             }
#         }
        
#         print(f"✅ Returning analytics: {result}")
#         return jsonify(result)
        
#     except Exception as e:
#         print(f"💥 Analytics Error: {type(e).__name__}: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500



# @app.route('/analytics', methods=['GET', 'OPTIONS'])
# def get_analytics():
#     """Analytics Dashboard Endpoint - FIXED VERSION"""
#     if request.method == 'OPTIONS': 
#         return '', 204
    
#     key = request.args.get('key', '').replace(' ', '+')
#     if key != ANALYTICS_API_KEY:
#         obfuscate_response()
#         return jsonify({"error": "Unauthorized"}), 401
    
#     try:
#         days = int(request.args.get('days', 7))
        
#         # FIX: Use Supabase's timestamp format (space instead of 'T')
#         cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
#         cutoff = cutoff_dt.strftime('%Y-%m-%d %H:%M:%S+00')
        
#         print(f"🔍 Fetching analytics for last {days} days (cutoff: {cutoff})")
        
#         # Fetch sessions
#         r_sessions = requests.get(
#             f"{SUPABASE_URL}/rest/v1/sessions?created_at=gte.{cutoff}&select=created_at,plan,issue", 
#             headers=HEADERS, 
#             timeout=10
#         )
        
#         if r_sessions.status_code == 200:
#             sessions = r_sessions.json()
#             print(f"✅ Fetched {len(sessions)} sessions")
#         else:
#             print(f"❌ Sessions fetch failed: {r_sessions.status_code}")
#             sessions = []
        
#         # Fetch events with better error handling
#         events = []
#         try:
#             r_events = requests.get(
#                 f"{SUPABASE_URL}/rest/v1/analytics_events?created_at=gte.{cutoff}&select=event_type,created_at", 
#                 headers=HEADERS, 
#                 timeout=10
#             )
            
#             print(f"📊 Events response status: {r_events.status_code}")
#             print(f"📊 Events response body: {r_events.text[:200]}")
            
#             if r_events.status_code == 200:
#                 events = r_events.json()
#                 print(f"✅ Fetched {len(events)} events")
                
#                 # Debug: Print event types
#                 event_types = [e.get('event_type') for e in events]
#                 print(f"📋 Event types found: {event_types}")
#             else:
#                 print(f"⚠️ Events fetch returned status {r_events.status_code}: {r_events.text}")
                
#         except requests.exceptions.Timeout:
#             print("⏱️ Events fetch timed out")
#         except Exception as e:
#             print(f"❌ Events fetch error: {type(e).__name__}: {str(e)}")
        
#         # Calculate metrics
#         tokens_generated = len(sessions)
#         ai_requests = 0
#         ai_errors = 0
#         recent_errors = []
        
#         for s in sessions:
#             plan = s.get('plan')
#             if plan:
#                 ai_requests += 1
#                 error_msg = None
                
#                 if isinstance(plan, dict):
#                     if 'error' in plan or plan.get('summary') == 'AI service error' or plan.get('software') == 'Unknown':
#                         error_msg = plan.get('error', 'Unknown Error')
                
#                 if error_msg:
#                     ai_errors += 1
#                     if len(recent_errors) < 5:
#                         recent_errors.append({
#                             "timestamp": s.get('created_at'),
#                             "issue": s.get('issue'),
#                             "error": error_msg
#                         })
        
#         # Count events
#         agent_downloads = sum(1 for e in events if e.get('event_type') == 'download')
#         human_help_requests = sum(1 for e in events if e.get('event_type') == 'human_help')
        
#         print(f"📈 Calculated metrics:")
#         print(f"   - Downloads: {agent_downloads}")
#         print(f"   - Human help: {human_help_requests}")
#         print(f"   - Total events: {len(events)}")
        
#         result = {
#             "tokens_generated": tokens_generated,
#             "ai_requests": ai_requests,
#             "agent_downloads": agent_downloads,
#             "ai_errors": ai_errors,
#             "error_rate": round((ai_errors / ai_requests * 100), 1) if ai_requests > 0 else 0,
#             "human_help_requests": human_help_requests,
#             "total_events": tokens_generated + len(events),
#             "recent_errors": recent_errors,
#             # Debug info
#             "_debug": {
#                 "sessions_count": len(sessions),
#                 "events_count": len(events),
#                 "cutoff_date": cutoff
#             }
#         }
        
#         print(f"✅ Returning analytics: {result}")
#         return jsonify(result)
        
#     except Exception as e:
#         print(f"💥 Analytics Error: {type(e).__name__}: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500


@app.route('/analytics', methods=['GET', 'OPTIONS'])
def get_analytics():
    """Analytics Dashboard - Using enhanced 'analytics' table"""
    if request.method == 'OPTIONS': 
        return '', 204
    
    key = request.args.get('key', '').replace(' ', '+')
    if key != ANALYTICS_API_KEY:
        obfuscate_response()
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        days = int(request.args.get('days', 7))
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
        
        print(f"\n{'='*60}")
        print(f"🔍 ANALYTICS: Last {days} days")
        print(f"   Cutoff: {cutoff_dt.isoformat()}")
        print(f"{'='*60}")
        
        # ===== FETCH ALL SESSIONS =====
        print(f"\n📊 Fetching sessions...")
        r_sessions = requests.get(
            f"{SUPABASE_URL}/rest/v1/sessions?select=created_at,plan,issue", 
            headers=HEADERS, 
            timeout=10
        )
        
        all_sessions = []
        if r_sessions.status_code == 200:
            all_sessions = r_sessions.json()
            print(f"✅ Found {len(all_sessions)} total sessions")
        else:
            print(f"❌ Sessions error: {r_sessions.status_code}")
        
        # Filter sessions in Python
        sessions = []
        for s in all_sessions:
            try:
                created_str = s.get('created_at', '')
                created_str = created_str.replace(' ', 'T').replace('+00', '+00:00')
                created_dt = datetime.fromisoformat(created_str)
                
                if created_dt >= cutoff_dt:
                    sessions.append(s)
            except Exception as e:
                print(f"⚠️ Skipping session: {e}")
        
        print(f"   Filtered to {len(sessions)} sessions")
        
        # ===== FETCH ALL EVENTS FROM NEW 'analytics' TABLE =====
        print(f"\n📊 Fetching events from 'analytics' table...")
        r_events = requests.get(
            f"{SUPABASE_URL}/rest/v1/analytics?select=event_type,timestamp,ip_address,metadata", 
            headers=HEADERS, 
            timeout=10
        )
        
        all_events = []
        if r_events.status_code == 200:
            all_events = r_events.json()
            print(f"✅ Found {len(all_events)} total events")
        else:
            print(f"❌ Events error: {r_events.status_code}")
            print(f"   Response: {r_events.text[:200]}")
        
        # Filter events in Python
        events = []
        for e in all_events:
            try:
                # Use 'timestamp' field (not 'created_at' for analytics table)
                timestamp_str = e.get('timestamp', '')
                timestamp_str = timestamp_str.replace(' ', 'T').replace('+00', '+00:00')
                timestamp_dt = datetime.fromisoformat(timestamp_str)
                
                if timestamp_dt >= cutoff_dt:
                    events.append(e)
            except Exception as e_err:
                print(f"⚠️ Skipping event: {e_err}")
        
        print(f"   Filtered to {len(events)} events")
        
        # ===== CALCULATE METRICS =====
        tokens_generated = len(sessions)
        ai_requests = 0
        ai_errors = 0
        recent_errors = []
        
        for s in sessions:
            plan = s.get('plan')
            if plan:
                ai_requests += 1
                error_msg = None
                
                if isinstance(plan, dict):
                    if 'error' in plan or plan.get('summary') == 'AI service error' or plan.get('software') == 'Unknown':
                        error_msg = plan.get('error', 'Unknown Error')
                
                if error_msg:
                    ai_errors += 1
                    if len(recent_errors) < 5:
                        recent_errors.append({
                            "timestamp": s.get('created_at'),
                            "issue": s.get('issue'),
                            "error": error_msg
                        })
        
        # Count event types
        agent_downloads = sum(1 for e in events if e.get('event_type') == 'download')
        human_help_requests = sum(1 for e in events if e.get('event_type') == 'human_help')
        
        # Get unique IPs (for visitor tracking)
        unique_ips = len(set(e.get('ip_address') for e in events if e.get('ip_address')))
        
        print(f"\n📈 RESULTS:")
        print(f"   Downloads: {agent_downloads}")
        print(f"   Human Help: {human_help_requests}")
        print(f"   Sessions: {tokens_generated}")
        print(f"   Unique IPs: {unique_ips}")
        print(f"{'='*60}\n")
        
        result = {
            "tokens_generated": tokens_generated,
            "ai_requests": ai_requests,
            "agent_downloads": agent_downloads,
            "ai_errors": ai_errors,
            "error_rate": round((ai_errors / ai_requests * 100), 1) if ai_requests > 0 else 0,
            "human_help_requests": human_help_requests,
            "total_events": tokens_generated + len(events),
            "unique_visitors": unique_ips,  # New metric!
            "recent_errors": recent_errors
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"💥 Analytics Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




@app.route('/track-download', methods=['POST', 'OPTIONS'])
def track_download():
    if request.method == 'OPTIONS': return '', 204
    supabase_insert_event('download')
    return jsonify({"status": "tracked"}), 200

@app.route('/generate-token', methods=['POST', 'OPTIONS'])
@rate_limit
def generate_token():
    if request.method == 'OPTIONS': return '', 204
    if is_ip_blocked(): return jsonify({"error": "Blocked"}), 403
    
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        plan = data.get('plan', 'basic')
        
        if not validate_email(email): return jsonify({"error": "Invalid email"}), 400
        
        duration = {'basic': 24, 'bundle': 168, 'pro': 720}.get(plan, 24)
        raw_token = str(uuid.uuid4())[:8].upper()
        token = f"{raw_token[:4]}-{raw_token[4:]}"
        
        now_utc = datetime.now(timezone.utc)
        expires_at = (now_utc + timedelta(hours=duration)).isoformat()
        
        try:
            requests.patch(f"{SUPABASE_URL}/rest/v1/sessions?email=eq.{email}", headers=HEADERS, json={"active": False})
        except: pass
        
        if supabase_insert_session({"token": token, "email": email, "issue": data.get('issue'), "created_at": now_utc.isoformat(), "expires_at": expires_at, "active": True, "plan_type": plan}):
            return jsonify({"token": token, "expires_in_hours": duration, "expires_at": expires_at}), 201
        return jsonify({"error": "DB Error"}), 500
    except Exception as e:
        print(e)
        return jsonify({"error": "Server error"}), 500

@app.route('/generate-plan', methods=['POST', 'OPTIONS'])
@rate_limit
def generate_plan():
    if request.method == 'OPTIONS': return '', 204
    if is_ip_blocked(): return jsonify({"error": "Blocked"}), 403
    
    try:
        data = request.get_json()
        token = data.get('token', '').strip()
        issue = sanitize_string(data.get('issue', ''))
        system_info = data.get('system_info', {})
        
        sess = supabase_get_token(token)
        if not sess or not sess.get("active"):
            track_failed_attempt(token)
            return jsonify({"error": "Invalid/Expired Token"}), 401
        
        prompt = build_repair_prompt(issue, system_info)
        raw_plan = call_mistral_ai(prompt)
        plan = sanitize_plan(raw_plan, issue)
        
        supabase_update_session(token, {"plan": plan})
        
        return jsonify(plan), 200
    except Exception as e:
        print(f"generate_plan error: {e}")
        return jsonify({"error": "Internal error"}), 500

@app.route('/request-human-help', methods=['POST', 'OPTIONS'])
@rate_limit
def request_human_help():
    if request.method == 'OPTIONS': return '', 204
    
    try:
        data = request.get_json()
        token = data.get('token')
        
        if not supabase_get_token(token):
            return jsonify({"error": "Invalid Token"}), 401
        
        send_help_request_email(token, data.get('email'), data.get('issue'), data.get('anydesk_code'))
        supabase_insert_event('human_help', {"token": token})
        
        return jsonify({"status": "sent"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download/agent/<platform>', methods=['GET', 'OPTIONS'])
@rate_limit
def download_agent(platform):
    if request.method == 'OPTIONS': return '', 204
    urls = {'linux': 'https://github.com/Boluex/techfix-frontend/releases/download/1.0/TechFIx.Agent.zip', 'windows': 'https://github.com/Boluex/techfix-frontend/releases/download/2.3/TechFixAgent.zip'}
    if platform not in urls: return jsonify({"error": "Invalid platform"}), 404
    try:
        response = requests.get(urls[platform], stream=True, timeout=30)
        if response.status_code != 200: return jsonify({"error": "Download unavailable"}), 404
        from flask import Response
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk: yield chunk
        return Response(generate(), content_type='application/octet-stream', headers={'Content-Disposition': f'attachment; filename=TechFix.{platform}.zip'})
    except: return jsonify({"error": "Download failed"}), 500

# ============= PAYMENT =============




# @app.route('/create-checkout-session', methods=['POST', 'OPTIONS'])
# def create_checkout_session():
#     if request.method == 'OPTIONS': 
#         return '', 204
    
#     try:
#         data = request.get_json()
#         print(f"📥 Received data: {data}")
        
#         email = data.get('email')
#         plan = data.get('plan')
        
#         if not email or not plan:
#             print("❌ Missing email or plan")
#             return jsonify({"error": "Email and plan required"}), 400
        
#         prices = {'basic': 29, 'bundle': 59, 'pro': 99}
#         tx_ref = f"TECHFIX-{uuid.uuid4().hex[:12].upper()}"
#         frontend = os.getenv('FRONTEND_URL', 'https://techfix-frontend-nc49.onrender.com')
        
#         payload = {
#             "tx_ref": tx_ref,
#             "amount": prices.get(plan, 29),
#             "currency": "USD",
#             "redirect_url": f"{frontend}/?status=successful&tx_ref={tx_ref}",
#             "customer": {
#                 "email": email,
#                 "name": email.split('@')[0]
#             },
#             "customizations": {
#                 "title": "TechFix AI",
#                 "description": f"{plan.title()} Plan"
#             },
#             "meta": {
#                 "user_email": email,
#                 "plan": plan
#             }
#         }
        
#         print(f"🔄 Creating payment for {email}, plan: {plan}")
#         print(f"💰 Amount: ${prices.get(plan)}")
#         print(f"🔑 Using Flutterwave key: {os.getenv('FLUTTERWAVE_SECRET_KEY')[:10]}...")
        
#         resp = requests.post(
#             "https://api.flutterwave.com/v3/payments",
#             headers={
#                 "Authorization": f"Bearer {os.getenv('FLUTTERWAVE_SECRET_KEY')}",
#                 "Content-Type": "application/json"
#             },
#             json=payload,
#             timeout=15
#         )
        
#         print(f"📥 Flutterwave response status: {resp.status_code}")
#         print(f"📦 Response body: {resp.text[:500]}")  # First 500 chars
        
#         if resp.status_code != 200:
#             print(f"❌ Flutterwave error: {resp.text}")
#             return jsonify({"error": f"Payment initialization failed: {resp.status_code}"}), 500
        
#         fw_data = resp.json()
#         print(f"✅ Flutterwave response: {fw_data}")
        
#         if fw_data.get("status") == "success" and fw_data.get("data", {}).get("link"):
#             payment_link = fw_data["data"]["link"]
#             print(f"🔗 Payment link: {payment_link}")
            
#             return jsonify({
#                 "redirect_url": payment_link,
#                 "link": payment_link,
#                 "tx_ref": tx_ref
#             }), 200
#         else:
#             print(f"❌ Invalid response structure: {fw_data}")
#             return jsonify({"error": "Payment setup failed - invalid response"}), 400
            
#     except Exception as e:
#         print(f"💥 Payment error: {type(e).__name__}: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({"error": str(e)}), 500




# @app.route('/verify-payment', methods=['POST', 'OPTIONS'])
# def verify_payment():
#     if request.method == 'OPTIONS': return '', 204
#     try:
#         tx_ref = request.get_json().get('tx_ref')
#         resp = requests.get(f"https://api.flutterwave.com/v3/transactions/verify_by_reference?tx_ref={tx_ref}", headers={"Authorization": f"Bearer {os.getenv('FLUTTERWAVE_SECRET_KEY')}"})
#         data = resp.json().get('data', {})
        
#         if data.get('status') == 'successful':
#             meta = data.get('meta', {})
            
#             # ✅ FIX 2: Safe Email Extraction (No KeyError)
#             email = meta.get('user_email') or data.get('customer', {}).get('email')
            
#             if not email:
#                 return jsonify({"status": "failed", "error": "Email not found"}), 400

#             plan = meta.get('plan', 'basic')
#             duration = {'basic': 24, 'bundle': 168, 'pro': 720}.get(plan, 24)
            
#             raw_token = str(uuid.uuid4())[:8].upper()
#             token = f"{raw_token[:4]}-{raw_token[4:]}"
#             now_utc = datetime.now(timezone.utc)
            
#             supabase_insert_session({"token": token, "email": email, "plan_type": plan, "active": True, "created_at": now_utc.isoformat(), "expires_at": (now_utc + timedelta(hours=duration)).isoformat(), "transaction_ref": tx_ref})
#             return jsonify({"status": "successful", "token": token, "plan": plan, "email": email}), 200
#         return jsonify({"status": "failed"}), 400
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500












# Add this at the top with your other imports
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")

# ============= PAYSTACK PAYMENT ENDPOINTS =============
# Replace your existing /create-checkout-session endpoint with this:

@app.route('/create-checkout-session', methods=['POST', 'OPTIONS'])
def create_checkout_session():
    """Create Paystack payment session"""
    if request.method == 'OPTIONS': 
        return '', 204
    
    try:
        data = request.get_json()
        print(f"📥 Received payment request: {data}")
        
        email = data.get('email')
        plan = data.get('plan')
        
        if not email or not plan:
            print("❌ Missing email or plan")
            return jsonify({"error": "Email and plan required"}), 400
        
        # Prices in kobo (cents) - Paystack uses smallest currency unit
        prices = {
            'basic': 2900,      # $29.00 = 2900 cents
            'bundle': 5900,     # $59.00
            'pro': 9900         # $99.00
        }
        
        # Generate unique reference
        reference = f"TECHFIX-{uuid.uuid4().hex[:12].upper()}"
        frontend_url = os.getenv('FRONTEND_URL', 'https://techfix-frontend-nc49.onrender.com')
        
        payload = {
            "email": email,
            "amount": prices.get(plan, 2900),  # Amount in cents
            "currency": "USD",  # 🌍 International payments
            "reference": reference,
            "callback_url": f"{frontend_url}/?status=successful&reference={reference}",
            "metadata": {
                "user_email": email,
                "plan": plan,
                "cancel_action": f"{frontend_url}/?status=cancelled"
            }
        }
        
        print(f"🔄 Creating Paystack payment:")
        print(f"   Email: {email}")
        print(f"   Plan: {plan}")
        print(f"   Amount: ${prices.get(plan)/100}")
        print(f"   Reference: {reference}")
        
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers={
                "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=15
        )
        
        print(f"📥 Paystack response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Paystack error: {response.text}")
            return jsonify({
                "error": f"Payment initialization failed: {response.status_code}"
            }), 500
        
        result = response.json()
        print(f"✅ Paystack response: {result}")
        
        if result.get("status") and result.get("data"):
            payment_url = result["data"]["authorization_url"]
            
            print(f"🔗 Payment URL: {payment_url}")
            
            return jsonify({
                "redirect_url": payment_url,
                "link": payment_url,  # For compatibility with frontend
                "reference": reference,  # Changed from tx_ref
                "tx_ref": reference  # Also include for backward compatibility
            }), 200
        else:
            print(f"❌ Invalid Paystack response structure")
            return jsonify({"error": "Payment setup failed"}), 400
            
    except Exception as e:
        print(f"💥 Payment error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Replace your existing /verify-payment endpoint with this:

@app.route('/verify-payment', methods=['POST', 'OPTIONS'])
def verify_payment():
    """Verify Paystack payment and generate token"""
    if request.method == 'OPTIONS': 
        return '', 204
    
    try:
        data = request.get_json()
        # Accept both 'reference' (Paystack) and 'tx_ref' (Flutterwave) for compatibility
        reference = data.get('reference') or data.get('tx_ref')
        
        if not reference:
            return jsonify({"error": "Reference required"}), 400
        
        print(f"\n{'='*60}")
        print(f"🔍 VERIFYING PAYMENT")
        print(f"   Reference: {reference}")
        print(f"{'='*60}")
        
        # Verify with Paystack
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={
                "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            },
            timeout=15
        )
        
        print(f"📥 Verification response: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Verification failed: {response.text}")
            return jsonify({
                "status": "failed",
                "error": "Verification failed"
            }), 400
        
        result = response.json()
        
        if not result.get("status") or not result.get("data"):
            print(f"❌ Invalid response structure")
            return jsonify({"status": "failed"}), 400
        
        transaction = result["data"]
        payment_status = transaction.get("status")
        
        print(f"💳 Payment status: {payment_status}")
        
        if payment_status == "success":
            # Extract user info
            metadata = transaction.get("metadata", {})
            customer = transaction.get("customer", {})
            
            email = metadata.get("user_email") or customer.get("email")
            plan = metadata.get("plan", "basic")
            
            print(f"✅ Payment successful")
            print(f"   Email: {email}")
            print(f"   Plan: {plan}")
            
            if not email:
                print(f"❌ Email not found in transaction")
                return jsonify({
                    "status": "failed",
                    "error": "Email not found"
                }), 400
            
            # Deactivate old sessions
            try:
                deactivate_url = f"{SUPABASE_URL}/rest/v1/sessions?email=eq.{email}"
                requests.patch(
                    deactivate_url,
                    headers=HEADERS,
                    json={"active": False},
                    timeout=10
                )
                print(f"🗑️ Deactivated old sessions for {email}")
            except Exception as e:
                print(f"⚠️ Could not deactivate old sessions: {e}")
            
            # Generate service token
            raw_token = str(uuid.uuid4())[:8].upper()
            token = f"{raw_token[:4]}-{raw_token[4:]}"
            
            # Calculate expiry
            plan_durations = {
                'basic': 24,      # 24 hours
                'bundle': 168,    # 7 days
                'pro': 720        # 30 days
            }
            duration_hours = plan_durations.get(plan, 24)
            
            now_utc = datetime.now(timezone.utc)
            expires_at = now_utc + timedelta(hours=duration_hours)
            expires_at_str = expires_at.isoformat()
            
            print(f"🎟️ Generated token: {token}")
            print(f"   Duration: {duration_hours} hours")
            print(f"   Expires: {expires_at_str}")
            
            # Save to database
            session_payload = {
                "token": token,
                "email": email,
                "issue": f"Paid session - {plan} plan",
                "created_at": now_utc.isoformat(),
                "expires_at": expires_at_str,
                "active": True,
                "plan_type": plan,
                "transaction_ref": reference
            }
            
            if supabase_insert_session(session_payload):
                print(f"✅ Session created successfully")
                print(f"{'='*60}\n")
                
                return jsonify({
                    "status": "successful",
                    "token": token,
                    "expires_at": expires_at_str,
                    "plan": plan,
                    "email": email
                }), 200
            else:
                print(f"❌ Failed to create session in database")
                return jsonify({
                    "status": "failed",
                    "error": "Failed to create session"
                }), 500
                
        elif payment_status == "pending":
            print(f"⏳ Payment is pending")
            return jsonify({"status": "pending"}), 200
        else:
            print(f"❌ Payment not successful: {payment_status}")
            return jsonify({"status": "failed"}), 400
            
    except Exception as e:
        print(f"💥 Verification error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "failed",
            "error": str(e)
        }), 500



# ===============================================================================================================================================================

@app.route('/notifications', methods=['GET'])
def get_notifications():
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/notifications?limit=1&order=created_at.desc", headers=HEADERS)
        return jsonify(r.json()[0]) if r.json() else jsonify({"id": None})
    except: return jsonify({"id": None})

@app.route('/cleanup-sessions', methods=['POST'])
def cleanup_old_sessions():
    """Delete old sessions + maintain CSV"""
    try:
        if request.json.get('key') != os.getenv("CLEANUP_KEY", "secret"):
            return jsonify({"error": "Unauthorized"}), 401
        
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        requests.delete(f"{SUPABASE_URL}/rest/v1/sessions?active=eq.false&created_at=lt.{cutoff}", headers=HEADERS)
        
        new_emails_count = 0
        r = requests.get(f"{SUPABASE_URL}/rest/v1/sessions?select=email", headers=HEADERS)
        if r.status_code == 200:
            emails = {s['email'] for s in r.json() if s.get('email')}
            csv_file = 'user_emails.csv'
            existing = set()
            
            if os.path.exists(csv_file):
                with open(csv_file, 'r') as f:
                    existing = {row['email'] for row in csv.DictReader(f)}
            
            new_emails = emails - existing
            new_emails_count = len(new_emails)
            
            if new_emails:
                with open(csv_file, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=['email', 'added_at'])
                    if not existing: writer.writeheader()
                    for email in new_emails:
                        writer.writerow({'email': email, 'added_at': datetime.now(timezone.utc).isoformat()})
        
        return jsonify({"status": "success", "emails_added": new_emails_count}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/auth/login', methods=['POST'])
def honeypot():
    """Security honeypot"""
    print(f"⚠️ SECURITY: Suspicious request from {get_client_ip()}")
    obfuscate_response()
    return jsonify({"error": "Invalid endpoint"}), 404

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers.pop('Server', None)
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8000)), debug=os.getenv("DEBUG", "False").lower() == "true")




