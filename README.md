# Oracle Instance Auto-Retry

Script tự động retry tạo Oracle VM.Standard.A1.Flex mỗi 5 phút cho đến khi thành công.

---

## Cấu Trúc File

```
oracle-retry/
├── main.py           ← Script chính
├── requirements.txt  ← Dependencies
├── render.yaml       ← Config cho Render
└── README.md
```

---

## Bước 1: Lấy Thông Tin Từ OCI Console

### User OCID
Profile (góc phải trên) → My Profile → copy OCID

### Tenancy OCID  
Profile → Tenancy → copy OCID

### Fingerprint
Profile → My Profile → API Keys → copy fingerprint của key vừa tạo
(dạng: `xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx`)

### Private Key Content
Mở file `.pem` vừa download bằng Notepad/TextEditor
Copy toàn bộ nội dung kể cả dòng `-----BEGIN PRIVATE KEY-----` và `-----END PRIVATE KEY-----`

### Compartment ID
Menu ☰ → Identity & Security → Compartments → click root → copy OCID

### Subnet ID
Menu ☰ → Networking → Virtual Cloud Networks → click VCN → Subnets → Public Subnet → copy OCID

---

## Bước 2: Đưa Lên GitHub

```bash
git init
git add .
git commit -m "oracle retry script"
git remote add origin https://github.com/YOUR_USERNAME/oracle-retry.git
git push -u origin main
```

---

## Bước 3: Deploy Lên Render

1. Vào **render.com** → **New** → **Web Service** (chọn Web Service để có URL ping được)
2. Connect GitHub repo vừa tạo
3. Settings:
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`

4. Vào tab **Environment** → Add các biến sau:

| Key | Value |
|-----|-------|
| `OCI_USER` | ocid1.user.oc1..xxx |
| `OCI_FINGERPRINT` | xx:xx:xx:xx... |
| `OCI_TENANCY` | ocid1.tenancy.oc1..xxx |
| `OCI_REGION` | ap-singapore-1 |
| `OCI_KEY_CONTENT` | -----BEGIN PRIVATE KEY-----\nxxx\n-----END PRIVATE KEY----- |
| `COMPARTMENT_ID` | ocid1.tenancy.oc1..xxx (thường giống Tenancy) |
| `SUBNET_ID` | ocid1.subnet.oc1..xxx |
| `IMAGE_ID` | ocid1.image.oc1.ap-singapore-1.aaaaaaaavlmcv5sid7y5lltppspklnndixe5lklspoa3mypvouaykmdrzhuq |

> ⚠️ OCI_KEY_CONTENT: paste nguyên nội dung file .pem, kể cả dòng BEGIN/END

5. Click **Deploy**

---

## Bước 4: Setup Ping Giữ Render Sống

Dùng **UptimeRobot** (free):
1. Vào uptimerobot.com → Add New Monitor
2. Monitor Type: HTTP(s)
3. URL: URL của Render service (dạng `https://oracle-retry-xxx.onrender.com`)
4. Monitoring Interval: **5 minutes**

Khi ping vào URL đó, script sẽ trả về JSON status hiện tại:
```json
{
  "status": "running",
  "attempts": 12,
  "last_try": "2024-01-15 03:45:00",
  "last_error": "Out of capacity...",
  "success": false
}
```

---

## Bước 5: Biết Khi Nào Thành Công

Khi `"success": true` xuất hiện trong response ping → instance đã tạo xong!

Vào OCI Console → Compute → Instances để xem instance đang chạy.

---

## Lưu Ý Quan Trọng

- Script retry mỗi **5 phút** — không quá aggressive, không vi phạm ToS
- Capacity ARM thường available vào **2-6 giờ sáng** giờ VN
- Sau khi instance tạo xong, **xóa Render service đi** để không tốn free hours
- **Không commit file .pem lên GitHub** — chỉ paste vào Render Environment Variables
