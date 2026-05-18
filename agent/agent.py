import winreg
import subprocess
import socket
import platform
import os
import json
import pymssql
import sys
import urllib.request
import logging
import glob
import tempfile
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor

# ============================================================
# CONFIG
# ============================================================

DB_CONFIG = {
    "server":   "163.223.13.31",
    "database": "MAY-IT",
    "username": "bao.ngo",
    "password": "abcDa123456",
}

# Từ khóa trong tên/publisher → đánh dấu suspicious
SUSPICIOUS_KEYWORDS = [
    "crack", "keygen", "activator", "loader",
    "bypass", "warez", "nulled", "pirate",
    "kmspico", "aact",
    # Adobe crack tools
    "zii", "genp", "amtemu", "patcher",
    # Office crack tools
    "kms_vl_all", "re-loader", "ezactivator",
]

# Publisher tin cậy → đánh dấu trusted
TRUSTED_PUBLISHERS = [
    "microsoft", "google", "adobe", "apple", "oracle",
    "cisco", "vmware", "intel", "amd", "nvidia",
    "autodesk", "jetbrains", "zoom", "slack",
    "mozilla", "opera", "dropbox", "teamviewer",
    "anydesk", "7-zip", "winrar", "notepad++",
    "python", "node", "git", "github"
]

# KMS server lạ → nghi ngờ dùng crack activation
SUSPICIOUS_KMS = [
    "kms.digiboy.ir", "kms8.msguides.com", "kms9.msguides.com",
    "e8.us.to", "kms.loli.beer", "kms.lolico.moe", "kms.03k.org",
    "kms.chinancce.com", "kms.lotro.cc",
    "kms.cangshui.net", "kms.luochenlong.com",
    # KMS38 dùng localhost giả
    "127.0.0.2",
    "0.0.0.0",
]

# ============================================================
# LOGGING
# Ghi vào %TEMP% — luôn có quyền ghi trên mọi máy
# ============================================================

LOG_PATH = os.path.join(tempfile.gettempdir(), "agent_audit.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# ============================================================
# POWERSHELL HELPER
# -NoProfile: bỏ qua PS profile → khởi động nhanh hơn
# -ExecutionPolicy Bypass: tránh bị block bởi Group Policy
# CREATE_NO_WINDOW: không hiện cửa sổ trên máy nhân viên
# ============================================================

def ps(cmd, timeout=10):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return r.stdout.strip()
    except:
        return ""



def get_cpu_id():
    # ProcessorId — hex string, unique theo từng CPU vật lý
    return ps(
        "Get-WmiObject Win32_Processor | "
        "Select-Object -First 1 -ExpandProperty ProcessorId"
    )


def get_mac_address():
    # MAC của adapter đang kết nối mạng (IPEnabled = true)
    return ps(
        "Get-WmiObject Win32_NetworkAdapterConfiguration | "
        "Where-Object {$_.IPEnabled -eq $true} | "
        "Select-Object -First 1 -ExpandProperty MACAddress"
    )


def build_device_uid(hostname, mac_address, cpu_id):
    """


    Python tương đương:
    MD5(hostname + mac_address + cpu_id).upper()

    """
    import hashlib

    # Ghép như SQL: @var1 + @var2 + @var3
    # Fallback nếu không lấy được hardware info
    if mac_address or cpu_id:
        raw = (hostname or "") + (mac_address or "") + (cpu_id or "")
    else:
        raw = (hostname or "") + platform.node()
        logging.warning(f"Thieu hardware info: mac={mac_address}, cpu={cpu_id}")

   
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()
# ============================================================
# HARDWARE FINGERPRINT
# Lưu vào device_info JSON để tham khảo
# Không dùng làm key — chỉ bổ sung thông tin
# ============================================================

def get_bios_serial():
    # BIOS serial — gắn liền mainboard, ổn định nhất
    return ps(
        "Get-WmiObject Win32_BIOS | "
        "Select-Object -ExpandProperty SerialNumber"
    )


def get_motherboard_serial():
    # Motherboard serial — bổ sung cho BIOS serial
    return ps(
        "Get-WmiObject Win32_BaseBoard | "
        "Select-Object -ExpandProperty SerialNumber"
    )

# ============================================================
# SOFTWARE SCAN
# Quét 4 registry key:
# HKLM 64-bit, HKLM 32-bit, HKCU 64-bit, HKCU 32-bit
# ============================================================

def get_installed_software():
    software_list = []
    all_keys = [
        # Phần mềm 64-bit cài cho toàn máy (cần admin)
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        # Phần mềm 32-bit cài cho toàn máy
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        # Phần mềm user tự cài (không cần admin)
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        # Phần mềm 32-bit user tự cài
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, key_path in all_keys:
        try:
            key   = winreg.OpenKey(hive, key_path)
            count = winreg.QueryInfoKey(key)[0]
            for i in range(count):
                try:
                    subkey = winreg.OpenKey(key, winreg.EnumKey(key, i))
                    try:
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        if not name.strip():
                            continue
                        def qv(k):
                            try: return str(winreg.QueryValueEx(subkey, k)[0]).strip()
                            except: return ""
                        software_list.append({
                            "name":             name.strip(),
                            "version":          qv("DisplayVersion"),
                            "publisher":        qv("Publisher"),
                            "install_date":     qv("InstallDate"),
                            "install_location": qv("InstallLocation"),
                        })
                    except: pass
                except: pass
        except: pass

    # Dedup theo name + version
    # Cùng phần mềm có thể xuất hiện ở nhiều registry key
    seen, unique = set(), []
    for sw in software_list:
        key = (sw["name"].lower(), sw["version"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(sw)
    return unique


def get_main_exe(location):
    """
    Lấy file exe lớn nhất trong thư mục cài đặt
    File lớn nhất = khả năng cao là exe chính
    Tránh lấy nhầm uninstaller hoặc helper nhỏ
    """
    try:
        exes = glob.glob(os.path.join(location, "*.exe"))
        if not exes:
            return None
        exes.sort(key=lambda x: os.path.getsize(x), reverse=True)
        return exes[0]
    except:
        return None


def check_status(sw):
    """
    Đánh giá trạng thái phần mềm theo 3 bước:
    1. Keyword — tên/publisher chứa từ khóa crack
    2. Digital signature — chữ ký bị sửa hoặc không có
    3. Publisher — so với danh sách tin cậy
    """
    name_lower = sw["name"].lower()
    pub_lower  = sw["publisher"].lower().strip() if sw["publisher"] else ""

    # Bước 1: Keyword check
    for kw in SUSPICIOUS_KEYWORDS:
        if kw in name_lower or kw in pub_lower:
            return "suspicious", f"Chứa từ khóa '{kw}'"

    # Bước 2: Digital signature check
    loc = sw.get("install_location", "")
    if loc and os.path.exists(loc):
        try:
            exe = get_main_exe(loc)
            if exe:
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                     "-Command", f"(Get-AuthenticodeSignature '{exe}').Status"],
                    capture_output=True, text=True, timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                sig = r.stdout.strip()
                # HashMismatch = file bị sửa sau khi ký → crack
                if sig == "HashMismatch":
                    return "suspicious", "Chữ ký số bị chỉnh sửa"
                # NotSigned + có publisher = đáng ngờ
                if sig == "NotSigned" and pub_lower:
                    return "unknown", "Không có chữ ký số"
        except: pass

    # Bước 3: Publisher check
    if not pub_lower:
        return "no_publisher", "Không có thông tin publisher"
    for tp in TRUSTED_PUBLISHERS:
        if tp in pub_lower:
            return "trusted", "Publisher tin cậy"

    return "unknown", "Chưa xác định"

# ============================================================
# HARDWARE INFO
# ============================================================

def get_hardware_info():
    cpu, ram_gb, gpu, disk_info = "", "", "", []

    # Tên CPU đầy đủ
    cpu = ps(
        "Get-WmiObject Win32_Processor | "
        "Select-Object -First 1 -ExpandProperty Name"
    )

    # RAM tổng — convert bytes → GB
    try:
        ram_raw = ps(
            "Get-WmiObject Win32_ComputerSystem | "
            "Select-Object -ExpandProperty TotalPhysicalMemory"
        )
        ram_gb = f"{round(int(ram_raw) / (1024**3), 1)} GB"
    except: pass

    # GPU — join nhiều card thành 1 string
    try:
        gpu_raw = ps(
            "Get-WmiObject Win32_VideoController | "
            "Select-Object Name | ConvertTo-Json"
        )
        gpus = json.loads(gpu_raw)
        if isinstance(gpus, dict): gpus = [gpus]
        gpu = ", ".join([g.get("Name","") for g in gpus if g.get("Name","")])
    except: pass

    # Disk — DriveType=3 là ổ cứng, bỏ USB/CD
    try:
        disk_raw = ps(
            "Get-WmiObject Win32_LogicalDisk | "
            "Where-Object {$_.DriveType -eq 3} | "
            "Select-Object DeviceID,Size,FreeSpace | ConvertTo-Json"
        )
        disks = json.loads(disk_raw)
        if isinstance(disks, dict): disks = [disks]
        for d in disks:
            try:
                size = round(int(d.get("Size",0))      / (1024**3), 1)
                free = round(int(d.get("FreeSpace",0)) / (1024**3), 1)
                disk_info.append({
                    "drive":   d.get("DeviceID",""),
                    "size_gb": size,
                    "free_gb": free,
                    "used_gb": round(size - free, 1)
                })
            except: pass
    except: pass

    return {"cpu": cpu, "ram_gb": ram_gb, "gpu": gpu, "disk_info": disk_info}

# ============================================================
# NETWORK
# ============================================================

def get_local_ip():
    """
    Kết nối UDP ra ngoài (không gửi data thật) để lấy IP LAN
    Tránh lấy 127.0.0.1 khi chỉ có loopback
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip.startswith("127."):
            return socket.gethostbyname(socket.gethostname())
        return ip
    except:
        return socket.gethostbyname(socket.gethostname())


def get_wan_ip():
    # Thử 2 service để tăng độ tin cậy
    for url in ["https://api.ipify.org", "https://ifconfig.me/ip"]:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.read().decode().strip()
        except: pass
    return ""

# ============================================================
# WINDOWS LICENSE
# Dùng slmgr.vbs /xpr thay vì chỉ đọc registry
# Registry có thể bị sửa để giả vờ đã kích hoạt
# ============================================================

def get_windows_license():
    try:
        output    = ps(
            "cscript //nologo C:\\Windows\\System32\\slmgr.vbs /xpr",
            timeout=15
        )
        activated = "permanently activated" in output.lower()
        key       = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        )
        product = winreg.QueryValueEx(key, "ProductName")[0]
        build   = winreg.QueryValueEx(key, "CurrentBuild")[0]
        return {
            "status":  "Đã kích hoạt" if activated else "Chưa kích hoạt",
            "channel": f"{product} (Build {build})"
        }
    except:
        return {"status": "Không đọc được", "channel": ""}

# ============================================================
# OFFICE LICENSE
# ClickToRun registry — detect Office 2016+ và M365
# ============================================================

def get_office_license():
    for path in [
        r"SOFTWARE\Microsoft\Office\ClickToRun\Configuration",
        r"SOFTWARE\WOW6432Node\Microsoft\Office\ClickToRun\Configuration"
    ]:
        try:
            key     = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
            product = winreg.QueryValueEx(key, "ProductReleaseIds")[0]
            channel = ""
            try: channel = winreg.QueryValueEx(key, "CDNBaseUrl")[0]
            except: pass
            return {"product": product, "channel": channel}
        except: pass
    return {"product": "Không tìm thấy", "channel": ""}

# ============================================================
# KMS DETECTION
# slmgr.vbs /dlv — phát hiện HWID (MAS) và KMS server lạ
# ============================================================

def get_kms_info():
    try:
        output = ps(
            "cscript //nologo C:\\Windows\\System32\\slmgr.vbs /dlv",
            timeout=15
        )
        ol   = output.lower()
        info = {
            "method":    "unknown",
            "server":    "",
            "suspicious": False,
            "detail":    ""
        }

        for line in output.split("\n"):
            if "kms machine" in line.lower():
                info["server"] = line.strip()

        if "hwid" in ol or "hardware hash" in ol:
            # HWID = MAS activation — gần như không phân biệt được
            info["method"] = "HWID"
            info["detail"] = "HWID detected — không xác định được hợp lệ hay crack"
        elif "kms" in ol:
            info["method"] = "KMS"
            for sus in SUSPICIOUS_KMS:
                if sus in ol:
                    info["suspicious"] = True
                    info["detail"]     = f"KMS server nghi ngờ: {sus}"
                    break
            if not info["suspicious"]:
                info["detail"] = f"KMS Server: {info['server']}"
        elif "retail" in ol or "oem" in ol:
            info["method"] = "Retail/OEM"
            info["detail"] = "License hợp lệ"
        else:
            info["detail"] = "Không xác định"

        return info
    except Exception as e:
        return {"method": "error", "server": "", "suspicious": False, "detail": str(e)}

# ============================================================
# MAS DETECTION
# Phát hiện Microsoft Activation Scripts (MAS)
# ============================================================

def check_ohook():
    """
    Phát hiện Ohook — phương pháp crack Office của MAS
    Ohook inject DLL vào Office để bypass license check
    Dấu vết: file ohook.dll trong thư mục Office
    """
    office_paths = [
        r"C:\Program Files\Microsoft Office",
        r"C:\Program Files (x86)\Microsoft Office",
        r"C:\Program Files\Common Files\Microsoft Shared",
    ]
    found = []
    for base in office_paths:
        if not os.path.exists(base):
            continue
        try:
            for root, dirs, files in os.walk(base):
                for f in files:
                    if "ohook" in f.lower():
                        found.append(os.path.join(root, f))
        except: pass
    return found


def check_kms38():
    """
    Phát hiện KMS38 — kích hoạt Windows/Office đến năm 2038
    Dấu vết:
    1. KMS server = 127.0.0.2 trong slmgr /dlv
    2. License expiry năm 2038
    """
    result = {"detected": False, "detail": ""}
    try:
        output = ps(
            "cscript //nologo C:\\Windows\\System32\\slmgr.vbs /dlv",
            timeout=15
        )
        ol = output.lower()

        # KMS38 dùng 127.0.0.2 làm KMS server giả
        if "127.0.0.2" in ol:
            result["detected"] = True
            result["detail"]   = "KMS38 — KMS server 127.0.0.2"
            return result

        # License expiry gần 2038
        if "2038" in output:
            result["detected"] = True
            result["detail"]   = "KMS38 — license expiry 2038"
            return result

        result["detail"] = "Không phát hiện KMS38"
    except Exception as e:
        result["detail"] = str(e)
    return result


def check_mas_tasks():
    """
    Phát hiện MAS Scheduled Tasks
    MAS KMS38 và Online KMS tạo task để tự renew license
    Task name thường chứa: ohook, kms_vl, activation renewal
    """
    SUSPICIOUS_TASK_KEYWORDS = [
        "ohook", "kms_vl", "activation renewal",
        "windows activation", "office activation",
    ]
    found = []
    try:
        output = ps("schtasks /query /fo CSV /nh 2>nul", timeout=15)
        for line in output.split("\n"):
            line_lower = line.lower()
            for kw in SUSPICIOUS_TASK_KEYWORDS:
                if kw in line_lower:
                    # Lấy tên task — cột đầu tiên trong CSV
                    task_name = line.split(",")[0].strip('"').strip()
                    if task_name and task_name not in found:
                        found.append(task_name)
                    break
    except: pass
    return found


def check_adobe_license():
    """
    Kiểm tra Adobe Genuine Software service
    Adobe Genuine Service (AGSService) kiểm tra bản quyền Adobe
    Crack thường disable service này để tránh bị phát hiện
    Running  = có thể hợp lệ
    Stopped/Disabled = dấu hiệu crack
    Không tìm thấy = không cài Adobe
    """
    result = {"status": "", "suspicious": False, "detail": ""}
    try:
        out = ps(
            "Get-Service -Name 'AGSService' -ErrorAction SilentlyContinue | "
            "Select-Object -ExpandProperty Status"
        )
        if not out:
            result["status"] = "not_found"
            result["detail"] = "Không tìm thấy Adobe"
        elif out.lower() == "running":
            result["status"] = "running"
            result["detail"] = "Adobe Genuine Service đang chạy"
        else:
            result["status"]    = out.lower()
            result["suspicious"] = True
            result["detail"]    = f"Adobe Genuine Service bị {out} — dấu hiệu crack"
    except Exception as e:
        result["detail"] = str(e)
    return result

# ============================================================
# PROCESS DETECTION
# ============================================================

def get_suspicious_processes():
    KEYWORDS = [
        "keygen", "crack", "activator", "loader",
        "bypass", "warez", "nulled", "kmspico", "aact",
        "zii", "genp", "amtemu", "ohook",
    ]
    try:
        raw = ps("Get-Process | Select-Object Name,Path | ConvertTo-Json")
        if not raw: return []
        procs = json.loads(raw)
        if isinstance(procs, dict): procs = [procs]
        flagged = []
        for p in procs:
            name = (p.get("Name") or "").lower()
            path = (p.get("Path") or "").lower()
            if any(kw in name or kw in path for kw in KEYWORDS):
                flagged.append({
                    "name": p.get("Name"),
                    "path": p.get("Path")
                })
        return flagged
    except:
        return []

# ============================================================
# CONVERT INSTALL DATE
# Registry lưu YYYYMMDD (string) → convert sang date object
# để lưu vào cột DATE trong SQL
# ============================================================

def parse_install_date(raw):
    """
    Convert string YYYYMMDD → datetime.date
    Trả về None nếu format sai hoặc ngày không hợp lệ
    """
    try:
        if not raw or len(raw) != 8 or not raw.isdigit():
            return None
        year, month, day = int(raw[0:4]), int(raw[4:6]), int(raw[6:8])
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        return date(year, month, day)
    except:
        return None

# ============================================================
# DATABASE SAVE
# machines: INSERT nếu mới, UPDATE nếu đã có
#   → verified_status/note/config_note KHÔNG bị ghi đè
#     khi UPDATE vì IT đã xác nhận rồi
# software: MERGE để giữ created_at gốc
#   → created_at: ngày đầu phát hiện phần mềm
#   → updated_at: ngày agent chạy gần nhất
# ============================================================

def save_to_db(device_uid, ip_lan, ip_wan,
               bios_serial, motherboard_serial,
               device_info, software_with_status):
    conn = None
    try:
        conn = pymssql.connect(
            server=DB_CONFIG["server"],
            user=DB_CONFIG["username"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            tds_version="7.4",
            login_timeout=10,
            timeout=30
        )
        cursor = conn.cursor()

        cursor.execute(
            "SELECT device_uid FROM machines WHERE device_uid=%s",
            (device_uid,)
        )
        exists      = cursor.fetchone()
        device_json = json.dumps(device_info, ensure_ascii=False)
        now         = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if exists:
            # Không ghi đè verified_status/note/config_note
            cursor.execute("""
                UPDATE machines SET
                    ip_lan=%s, ip_wan=%s,
                    bios_serial=%s, motherboard_serial=%s,
                    device_info=%s, last_seen=%s
                WHERE device_uid=%s
            """, (ip_lan, ip_wan,
                  bios_serial, motherboard_serial,
                  device_json, now, device_uid))
        else:
            cursor.execute("""
                INSERT INTO machines (
                    device_uid, ip_lan, ip_wan,
                    bios_serial, motherboard_serial,
                    device_info, verified_status, last_seen
                ) VALUES (%s,%s,%s,%s,%s,%s,'unverified',%s)
            """, (device_uid, ip_lan, ip_wan,
                  bios_serial, motherboard_serial,
                  device_json, now))

        # MERGE software:
        # MATCHED → UPDATE, giữ nguyên created_at
        # NOT MATCHED → INSERT mới với created_at = GETDATE()
        for sw in software_with_status:
            install_date = parse_install_date(sw.get("install_date",""))
            cursor.execute("""
                MERGE software AS target
                USING (
                    SELECT %s AS device_uid, %s AS name, %s AS version
                ) AS source
                ON (
                    target.device_uid  = source.device_uid
                    AND target.name    = source.name
                    AND target.version = source.version
                )
                WHEN MATCHED THEN
                    UPDATE SET
                        publisher        = %s,
                        status           = %s,
                        reason           = %s,
                        install_date     = %s,
                        install_location = %s,
                        updated_at       = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (
                        device_uid, name, version, publisher,
                        status, reason, install_date, install_location,
                        created_at, updated_at
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s, GETDATE(), GETDATE());
            """, (
                device_uid, sw["name"], sw["version"],
                sw["publisher"], sw["status"], sw["reason"],
                install_date, sw.get("install_location",""),
                device_uid, sw["name"], sw["version"],
                sw["publisher"], sw["status"], sw["reason"],
                install_date, sw.get("install_location","")
            ))

        # Xóa phần mềm đã gỡ cài đặt
        # Chỉ xóa tên không còn trong danh sách mới
        if software_with_status:
            names        = [sw["name"] for sw in software_with_status]
            placeholders = ",".join(["%s"] * len(names))
            cursor.execute(
                f"DELETE FROM software "
                f"WHERE device_uid=%s AND name NOT IN ({placeholders})",
                [device_uid] + names
            )

        conn.commit()

    except Exception as e:
        logging.exception(e)
        raise
    finally:
        if conn:
            conn.close()

# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 35)
    print("   Software Audit — Chi Bao IT")
    print("=" * 35)
    t_start = datetime.now()
    print(f"[{t_start.strftime('%H:%M:%S')}] Đang thu thập thông tin...")

    # Chạy song song — slmgr.vbs chậm ~5-10s (timeout 15s)
    # kms38 cũng gọi slmgr nên chạy song song với kms_info
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {
            "software":    executor.submit(get_installed_software),
            "windows":     executor.submit(get_windows_license),
            "office":      executor.submit(get_office_license),
            "kms":         executor.submit(get_kms_info),
            "kms38":       executor.submit(check_kms38),
            "ohook":       executor.submit(check_ohook),
            "mas_tasks":   executor.submit(check_mas_tasks),
            "adobe":       executor.submit(check_adobe_license),
            "procs":       executor.submit(get_suspicious_processes),
            "hardware":    executor.submit(get_hardware_info),
            "wan":         executor.submit(get_wan_ip),
            "bios":        executor.submit(get_bios_serial),
            "motherboard": executor.submit(get_motherboard_serial),
            "cpu_id":      executor.submit(get_cpu_id),
            "mac":         executor.submit(get_mac_address),
        }
        results = {k: v.result() for k, v in futures.items()}

    # Gắn status cho từng phần mềm
    raw_software = results["software"]
    software_with_status = []
    counts = {"trusted": 0, "suspicious": 0, "no_publisher": 0, "unknown": 0}
    for sw in raw_software:
        status, reason = check_status(sw)
        counts[status] += 1
        software_with_status.append({**sw, "status": status, "reason": reason})

    hostname    = socket.gethostname()
    ip_lan      = get_local_ip()
    ip_wan      = results["wan"]
    mac_address = results["mac"]
    cpu_id      = results["cpu_id"]
    bios_serial = results["bios"]
    mb_serial   = results["motherboard"]
    hardware    = results["hardware"]

    # Tạo device_uid dạng dễ đọc
    device_uid = build_device_uid(hostname, mac_address, cpu_id)

    # Tổng hợp MAS detection
    mas_detection = {
        # Ohook: crack Office bằng DLL injection
        "ohook_files":  results["ohook"],
        # KMS38: fake KMS server đến 2038
        "kms38":        results["kms38"],
        # Scheduled tasks của MAS
        "mas_tasks":    results["mas_tasks"],
        # Adobe Genuine Service
        "adobe_license": results["adobe"],
    }

    # Đóng gói toàn bộ vào device_info JSON
    device_info = {
        "timestamp":   datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "hostname":    hostname,
        "username":    os.getlogin(),
        "os":          platform.version(),
        "cpu":         hardware["cpu"],
        "ram_gb":      hardware["ram_gb"],
        "gpu":         hardware["gpu"],
        "disk_info":   hardware["disk_info"],
        "mac_address": mac_address,
        "cpu_id":      cpu_id,
        "windows_license":      results["windows"],
        "office_license":       results["office"],
        "kms_info":             results["kms"],
        "mas_detection":        mas_detection,
        "suspicious_processes": results["procs"],
        "software_summary": {
            "total":        len(raw_software),
            "trusted":      counts["trusted"],
            "unknown":      counts["unknown"],
            "no_publisher": counts["no_publisher"],
            "suspicious":   counts["suspicious"],
        }
    }

    # In kết quả
    t_collect = (datetime.now() - t_start).seconds
    print(f"  → Device UID : {device_uid}")
    print(f"  → IP         : LAN {ip_lan} | WAN {ip_wan}")
    print(f"  → User       : {device_info['username']}")
    print(f"  → OS         : {results['windows']['channel']}")
    print(f"  → CPU        : {hardware['cpu']}")
    print(f"  → RAM        : {hardware['ram_gb']} | GPU: {hardware['gpu']}")
    print(f"  → BIOS       : {bios_serial} | Mainboard: {mb_serial}")
    for d in hardware["disk_info"]:
        print(f"  → Disk {d['drive']}  : "
              f"{d['used_gb']}GB/{d['size_gb']}GB (còn {d['free_gb']}GB)")
    print(f"  → KMS        : {results['kms']['method']} — {results['kms']['detail']}")
    print(f"  → Office     : {results['office']['product']}")
    print(f"  → Phần mềm  : {len(raw_software)} "
          f"(✅{counts['trusted']} ⚠️{counts['unknown']} "
          f"❓{counts['no_publisher']} 🚨{counts['suspicious']})")

    # MAS detection summary
    mas = mas_detection
    if mas["ohook_files"]:
        print(f"  → 🚨 Ohook: {mas['ohook_files']}")
    if mas["kms38"]["detected"]:
        print(f"  → 🚨 KMS38: {mas['kms38']['detail']}")
    if mas["mas_tasks"]:
        print(f"  → 🚨 MAS Tasks: {mas['mas_tasks']}")
    if mas["adobe_license"]["suspicious"]:
        print(f"  → 🚨 Adobe: {mas['adobe_license']['detail']}")
    if results["procs"]:
        print(f"  → 🚨 Process nghi ngờ: {len(results['procs'])}")
    if not any([
        mas["ohook_files"], mas["kms38"]["detected"],
        mas["mas_tasks"], mas["adobe_license"]["suspicious"],
        results["procs"]
    ]):
        print("  → ✅ Không phát hiện crack/MAS")

    print(f"  → Thu thập xong sau {t_collect}s")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Đang ghi vào database...")
    try:
        save_to_db(
            device_uid, ip_lan, ip_wan,
            bios_serial, mb_serial,
            device_info, software_with_status
        )
        t_total = (datetime.now() - t_start).seconds
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Hoàn tất sau {t_total}s ✓")
        logging.info(f"OK — {device_uid} — {len(raw_software)} phần mềm")
    except Exception as e:
        print(f"  → Lỗi DB: {e}")
        logging.error(f"FAIL — {device_uid} — {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()