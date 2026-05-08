import subprocess
import time
import os
import json
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from dotenv import load_dotenv

# ─── Load environment variables từ .env ────────────────────
load_dotenv()

# ─── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ─── OCI Config (lấy từ environment variables) ─────────────
OCI_USER        = os.environ.get("OCI_USER", "PASTE_USER_OCID_HERE")
OCI_FINGERPRINT = os.environ.get("OCI_FINGERPRINT", "PASTE_FINGERPRINT_HERE")
OCI_TENANCY     = os.environ.get("OCI_TENANCY", "PASTE_TENANCY_OCID_HERE")
OCI_REGION      = os.environ.get("OCI_REGION", "ap-singapore-1")
OCI_KEY_CONTENT = os.environ.get("OCI_KEY_CONTENT", "")  # Nội dung file .pem

COMPARTMENT_ID  = os.environ.get("COMPARTMENT_ID", "PASTE_COMPARTMENT_ID_HERE")
SUBNET_ID       = os.environ.get("SUBNET_ID", "PASTE_SUBNET_ID_HERE")
IMAGE_ID        = os.environ.get("IMAGE_ID", "ocid1.image.oc1.ap-singapore-1.aaaaaaaavlmcv5sid7y5lltppspklnndixe5lklspoa3mypvouaykmdrzhuq")

INSTANCE_NAME   = "openclaw-vm"
RETRY_INTERVAL  = 300  # 5 phút
KEY_PATH        = "/tmp/oci_key.pem"

# ─── Status tracking ───────────────────────────────────────
status = {
    "attempts": 0,
    "last_try": None,
    "last_error": None,
    "success": False,
    "instance_id": None
}

# ─── HTTP Server để Render không spin down ─────────────────
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        response = json.dumps({
            "status": "running",
            "attempts": status["attempts"],
            "last_try": status["last_try"],
            "last_error": status["last_error"],
            "success": status["success"],
            "instance_id": status["instance_id"]
        })
        self.wfile.write(response.encode())
        log.info("Ping received — still alive")

    def log_message(self, format, *args):
        pass  # Tắt default HTTP log cho đỡ spam

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    log.info(f"HTTP server chạy trên port {port}")
    server.serve_forever()

# ─── Setup OCI credentials ─────────────────────────────────
def setup_oci():
    # Ghi private key ra file tạm
    if OCI_KEY_CONTENT:
        with open(KEY_PATH, "w") as f:
            f.write(OCI_KEY_CONTENT)
        os.chmod(KEY_PATH, 0o600)
    else:
        log.error("OCI_KEY_CONTENT chưa được set!")
        return False

    # Tạo OCI config file
    os.makedirs(os.path.expanduser("~/.oci"), exist_ok=True)
    config_content = f"""[DEFAULT]
user={OCI_USER}
fingerprint={OCI_FINGERPRINT}
tenancy={OCI_TENANCY}
region={OCI_REGION}
key_file={KEY_PATH}
"""
    with open(os.path.expanduser("~/.oci/config"), "w") as f:
        f.write(config_content)
    os.chmod(os.path.expanduser("~/.oci/config"), 0o600)
    log.info("OCI credentials đã setup xong")
    return True

# ─── Thử tạo instance ──────────────────────────────────────
def try_create_instance():
    status["attempts"] += 1
    status["last_try"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info(f"Lần thử #{status['attempts']} — đang gọi OCI API...")

    shape_config = json.dumps({"ocpus": 2, "memoryInGBs": 12})

    cmd = [
        "oci", "compute", "instance", "launch",
        "--availability-domain", "AD-1",
        "--compartment-id", COMPARTMENT_ID,
        "--shape", "VM.Standard.A1.Flex",
        "--shape-config", shape_config,
        "--image-id", IMAGE_ID,
        "--subnet-id", SUBNET_ID,
        "--display-name", INSTANCE_NAME,
        "--assign-public-ip", "true",
        "--wait-for-state", "RUNNING",
        "--max-wait-seconds", "300"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        log.info("✅ Instance tạo thành công!")
        try:
            data = json.loads(result.stdout)
            status["instance_id"] = data.get("data", {}).get("id", "unknown")
            log.info(f"Instance ID: {status['instance_id']}")
        except:
            pass
        status["success"] = True
        return True
    else:
        error_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
        status["last_error"] = error_msg
        log.warning(f"❌ Thất bại: {error_msg}")
        log.info(f"Thử lại sau {RETRY_INTERVAL // 60} phút...")
        return False

# ─── Main ──────────────────────────────────────────────────
def main():
    log.info("=" * 50)
    log.info("Oracle Instance Auto-Retry bắt đầu chạy")
    log.info("=" * 50)

    # Chạy HTTP server trong background thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # Setup OCI credentials
    if not setup_oci():
        log.error("Không setup được OCI credentials, dừng lại.")
        return

    # Loop retry
    while not status["success"]:
        try_create_instance()
        if not status["success"]:
            time.sleep(RETRY_INTERVAL)

    log.info("🎉 Xong! Instance đã chạy, script dừng lại.")

if __name__ == "__main__":
    main()
