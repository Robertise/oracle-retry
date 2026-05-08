import time
import os
import json
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ─── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ─── OCI Config ────────────────────────────────────────────
OCI_USER        = os.environ.get("OCI_USER", "")
OCI_FINGERPRINT = os.environ.get("OCI_FINGERPRINT", "")
OCI_TENANCY     = os.environ.get("OCI_TENANCY", "")
OCI_REGION      = os.environ.get("OCI_REGION", "ap-singapore-1")
OCI_KEY_CONTENT = os.environ.get("OCI_KEY_CONTENT", "")
COMPARTMENT_ID  = os.environ.get("COMPARTMENT_ID", "")
SUBNET_ID       = os.environ.get("SUBNET_ID", "")
IMAGE_ID        = os.environ.get("IMAGE_ID", "ocid1.image.oc1.ap-singapore-1.aaaaaaaavlmcv5sid7y5lltppspklnndixe5lklspoa3mypvouaykmdrzhuq")

INSTANCE_NAME  = "openclaw-vm"
RETRY_INTERVAL = 300
KEY_PATH       = "/tmp/oci_key.pem"

status = {
    "attempts": 0,
    "last_try": None,
    "last_error": None,
    "success": False,
    "instance_id": None
}

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(status, ensure_ascii=False, indent=2).encode())

    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    log.info(f"HTTP server chạy trên port {port}")
    server.serve_forever()

def setup_oci():
    if not OCI_KEY_CONTENT:
        log.error("OCI_KEY_CONTENT chưa được set!")
        return False
    with open(KEY_PATH, "w") as f:
        f.write(OCI_KEY_CONTENT)
    os.chmod(KEY_PATH, 0o600)
    log.info("OCI credentials đã setup xong")
    return True

def try_create_instance():
    status["attempts"] += 1
    status["last_try"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info(f"Lần thử #{status['attempts']} — đang gọi OCI API...")

    try:
        import oci

        config = {
            "user": OCI_USER,
            "fingerprint": OCI_FINGERPRINT,
            "tenancy": OCI_TENANCY,
            "region": OCI_REGION,
            "key_file": KEY_PATH,
        }

        # Lấy tên AD thật từ API
        identity = oci.identity.IdentityClient(config)
        ads = identity.list_availability_domains(COMPARTMENT_ID).data
        ad_name = ads[0].name
        log.info(f"Dùng Availability Domain: {ad_name}")

        compute = oci.core.ComputeClient(config)
        details = oci.core.models.LaunchInstanceDetails(
            compartment_id=COMPARTMENT_ID,
            availability_domain=ad_name,
            display_name=INSTANCE_NAME,
            shape="VM.Standard.A1.Flex",
            shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=2,
                memory_in_gbs=12
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id=IMAGE_ID
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=SUBNET_ID,
                assign_public_ip=True
            )
        )

        response = compute.launch_instance(details)
        status["instance_id"] = response.data.id
        status["success"] = True
        log.info(f"✅ Thành công! ID: {response.data.id}")
        return True

    except Exception as e:
        error_msg = str(e)[:800]
        status["last_error"] = error_msg
        log.warning(f"❌ Thất bại: {error_msg}")
        log.info(f"Thử lại sau {RETRY_INTERVAL // 60} phút...")
        return False

def main():
    log.info("=" * 50)
    log.info("Oracle Instance Auto-Retry bắt đầu chạy")
    log.info("=" * 50)

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    if not setup_oci():
        log.error("Không setup được OCI credentials, dừng lại.")
        return

    while not status["success"]:
        try_create_instance()
        if not status["success"]:
            time.sleep(RETRY_INTERVAL)

    log.info("🎉 Xong! Instance đã chạy.")

if __name__ == "__main__":
    main()