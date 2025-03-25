from fastapi import FastAPI, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import subprocess, os, shutil, uuid, json, threading

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sanskar0104.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def run_aider_with_prompt_detection(filename, prompt, cwd):
    proc = subprocess.Popen(
        ["aider", filename, "--message", prompt],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    def monitor_stdout():
        for line in proc.stdout:
            print("[AIDER] →", line.strip())
            try:
                if "Run shell command?" in line:
                    proc.stdin.write("n\n"); proc.stdin.flush()
                elif "?" in line and "(Y)es" in line:
                    proc.stdin.write("y\n"); proc.stdin.flush()
            except Exception as e:
                print("❌ Failed to respond:", e)

    thread = threading.Thread(target=monitor_stdout)
    thread.start()
    proc.wait()
    thread.join()

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, filename)

def get_next_version(session_dir):
    version_path = os.path.join(session_dir, "version.txt")
    version = 1
    if os.path.exists(version_path):
        with open(version_path) as vf:
            version = int(vf.read()) + 1
    with open(version_path, "w") as vf:
        vf.write(str(version))
    return version

@app.post("/aider-generate/")
async def aider_generate(prompt: str = Form(...), file: UploadFile = None):
    session_id = str(uuid.uuid4())
    session_dir = f"/tmp/session_{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    prompt_path = os.path.join(session_dir, "prompt.txt")
    with open(prompt_path, "w") as f:
        f.write(prompt)

    upload_path = os.path.join(session_dir, "upload.py")
    if file:
        with open(upload_path, "wb") as f:
            f.write(await file.read())
    else:
        with open(upload_path, "w") as f:
            f.write("# Empty file")

    version = 1
    with open(os.path.join(session_dir, "version.txt"), "w") as f:
        f.write("1")

    versioned_file = os.path.join(session_dir, f"experiment_v{version}.py")
    shutil.copy2(upload_path, versioned_file)

    run_aider_with_prompt_detection(f"experiment_v{version}.py", prompt, session_dir)

    with open(versioned_file) as f:
        return {"generated_code": f.read(), "session_id": session_id, "version": version}

@app.post("/regenerate/")
async def regenerate(session_id: str = Form(...)):
    session_dir = f"/tmp/session_{session_id}"
    if not os.path.exists(session_dir):
        return {"error": "Session not found"}

    prompt = open(os.path.join(session_dir, "prompt.txt")).read()
    upload_path = os.path.join(session_dir, "upload.py")

    version = get_next_version(session_dir)
    versioned_file = os.path.join(session_dir, f"experiment_v{version}.py")
    shutil.copy2(upload_path, versioned_file)

    run_aider_with_prompt_detection(f"experiment_v{version}.py", prompt, session_dir)

    with open(versioned_file) as f:
        return {"generated_code": f.read(), "version": version}

@app.post("/run-code/")
async def run_code(payload: dict):
    code = payload.get("code")
    session_id = payload.get("session_id")
    if not session_id:
        return {"error": "Missing session_id"}

    session_dir = f"/tmp/session_{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    version = get_next_version(session_dir)
    code_path = os.path.join(session_dir, f"experiment_v{version}.py")
    with open(code_path, "w") as f:
        f.write(code)

    try:
        subprocess.run(["python", code_path], capture_output=True, text=True, timeout=15, cwd=session_dir)

        for fname in os.listdir(session_dir):
            if fname.endswith(".json") and not fname.startswith("output_v"):
                os.rename(
                    os.path.join(session_dir, fname),
                    os.path.join(session_dir, f"output_v{version}.json")
                )
                break

        output_path = os.path.join(session_dir, f"output_v{version}.json")
        if os.path.exists(output_path):
            with open(output_path) as jf:
                return {"result": json.load(jf), "version": version}
        else:
            return {"error": "No JSON file created."}

    except subprocess.TimeoutExpired:
        return {"error": "Script timed out"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/upload-json/")
async def upload_json(file: UploadFile = File(...)):
    session_id = str(uuid.uuid4())
    session_dir = f"/tmp/session_{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    version = get_next_version(session_dir)
    output_path = os.path.join(session_dir, f"output_v{version}.json")

    try:
        with open(output_path, "wb") as f:
            f.write(await file.read())
        with open(output_path) as f:
            return {"result": json.load(f), "version": version}
    except Exception as e:
        return {"error": str(e)}

@app.get("/versions/")
async def list_versions(session_id: str):
    session_dir = f"/tmp/session_{session_id}"
    if not os.path.exists(session_dir):
        return {"error": "Session not found"}
    return {
        "code_versions": sorted(f for f in os.listdir(session_dir) if f.startswith("experiment_v")),
        "output_versions": sorted(f for f in os.listdir(session_dir) if f.startswith("output_v")),
    }
