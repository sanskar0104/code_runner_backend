from fastapi import FastAPI, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import subprocess, os, shutil, uuid, json, threading, time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sanskar0104.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def cleanup_temp_dirs(base_dir="/tmp", max_age_minutes=30):
    now = time.time()
    for name in os.listdir(base_dir):
        if name.startswith(("session_", "run_")):
            path = os.path.join(base_dir, name)
            if os.path.isdir(path):
                modified = os.path.getmtime(path)
                if (now - modified) / 60 > max_age_minutes:
                    try:
                        shutil.rmtree(path)
                    except:
                        pass

def run_aider_with_prompt_detection(cmd, cwd):
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    def monitor():
        for line in proc.stdout:
            print("[AIDER] →", line.strip())
            try:
                if "Run shell command?" in line:
                    proc.stdin.write("n\n")
                    proc.stdin.flush()
                elif "?" in line and "(Y)es" in line:
                    proc.stdin.write("y\n")
                    proc.stdin.flush()
            except Exception:
                pass

    thread = threading.Thread(target=monitor)
    thread.start()
    proc.wait()
    thread.join()

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)

@app.post("/aider-generate/")
async def aider_generate(prompt: str = Form(...), file: UploadFile = None):
    cleanup_temp_dirs()
    session_id = str(uuid.uuid4())
    session_dir = f"/tmp/session_{session_id}"
    os.makedirs(session_dir, exist_ok=True)

    try:
        with open(os.path.join(session_dir, "prompt.txt"), "w") as f:
            f.write(prompt)

        upload_path = os.path.join(session_dir, "upload.py")
        if file:
            with open(upload_path, "wb") as f:
                f.write(await file.read())
        else:
            with open(upload_path, "w") as f:
                f.write("# Empty file generated by Aider\n")

        shutil.copy2(upload_path, os.path.join(session_dir, "experiment.py"))

        run_aider_with_prompt_detection(
            ["aider", "experiment.py", "--message", prompt],
            cwd=session_dir
        )

        with open(os.path.join(session_dir, "experiment.py")) as f:
            generated_code = f.read()

        return JSONResponse({"generated_code": generated_code, "session_id": session_id})

    except subprocess.CalledProcessError as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/regenerate/")
async def regenerate(session_id: str = Form(...)):
    cleanup_temp_dirs()
    session_dir = f"/tmp/session_{session_id}"
    prompt_path = os.path.join(session_dir, "prompt.txt")
    upload_path = os.path.join(session_dir, "upload.py")
    experiment_path = os.path.join(session_dir, "experiment.py")

    if not os.path.exists(prompt_path) or not os.path.exists(upload_path):
        return JSONResponse({"error": "Session data not found"}, status_code=400)

    try:
        shutil.copy2(upload_path, experiment_path)

        with open(prompt_path) as f:
            prompt = f.read()

        run_aider_with_prompt_detection(
            ["aider", "experiment.py", "--message", prompt],
            cwd=session_dir
        )

        with open(experiment_path) as f:
            regenerated_code = f.read()

        return JSONResponse({"generated_code": regenerated_code})

    except subprocess.CalledProcessError as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/run-code/")
async def run_code(payload: dict):
    cleanup_temp_dirs()
    code = payload.get("code", "")
    run_id = str(uuid.uuid4())
    run_dir = f"/tmp/run_{run_id}"
    os.makedirs(run_dir, exist_ok=True)

    script_path = os.path.join(run_dir, "experiment.py")
    with open(script_path, "w") as f:
        f.write(code)

    try:
        result = subprocess.run(["python", script_path], capture_output=True, text=True, timeout=15, cwd=run_dir)
        for f_name in os.listdir(run_dir):
            if f_name.endswith(".json") and f_name != "output.json":
                os.rename(os.path.join(run_dir, f_name), os.path.join(run_dir, "output.json"))

        json_path = os.path.join(run_dir, "output.json")
        if os.path.exists(json_path):
            with open(json_path) as jf:
                return {"result": json.load(jf), "stdout": result.stdout}
        else:
            return {"error": "No JSON file created."}

    except subprocess.TimeoutExpired:
        return {"error": "Script timed out"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        shutil.rmtree(run_dir)

@app.post("/upload-json/")
async def upload_json(file: UploadFile = File(...)):
    cleanup_temp_dirs()
    run_id = str(uuid.uuid4())
    run_dir = f"/tmp/run_{run_id}"
    os.makedirs(run_dir, exist_ok=True)

    try:
        output_path = os.path.join(run_dir, "output.json")
        with open(output_path, "wb") as f:
            f.write(await file.read())

        with open(output_path) as f:
            return {"result": json.load(f)}

    except Exception as e:
        return {"error": str(e)}, status_code=500)
    finally:
        shutil.rmtree(run_dir)
