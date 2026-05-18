from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pymssql, json

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_CONFIG = {
    "server":   "163.223.13.31",
    "database": "MAY-IT",
    "username": "bao.ngo",
    "password": "abcDa123456",
}

def get_conn():
    return pymssql.connect(
        server=DB_CONFIG["server"],
        user=DB_CONFIG["username"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        tds_version="7.4",
        login_timeout=10,
        timeout=30
    )

class VerifyPayload(BaseModel):
    status: str        # "verified_ok" | "verified_crack" | "unverified"
    note:   Optional[str] = ""
    by:     Optional[str] = "IT Admin"

@app.get("/api/machines")
def get_machines():
    conn   = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT hostname, ip, os, username, windows_license, office_license,
               kms_info, suspicious_processes, verified_status,
               verified_note, verified_by, verified_at, last_seen
        FROM machines ORDER BY last_seen DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [{
        "hostname":             r[0],
        "ip":                   r[1],
        "os":                   r[2],
        "username":             r[3],
        "windows_license":      json.loads(r[4])  if r[4]  else {},
        "office_license":       json.loads(r[5])  if r[5]  else {},
        "kms_info":             json.loads(r[6])  if r[6]  else {},
        "suspicious_processes": json.loads(r[7])  if r[7]  else [],
        "verified_status":      r[8]  or "unverified",
        "verified_note":        r[9]  or "",
        "verified_by":          r[10] or "",
        "verified_at":          r[11] or "",
        "last_seen":            r[12]
    } for r in rows]

@app.get("/api/machines/{hostname}/software")
def get_software(hostname: str):
    conn   = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, version, publisher, status, reason, install_date, install_location
        FROM software WHERE machine_hostname=%s ORDER BY name
    """, (hostname,))
    rows = cursor.fetchall()
    conn.close()
    return [{
        "name": r[0], "version": r[1], "publisher": r[2],
        "status": r[3], "reason": r[4],
        "install_date": r[5], "install_location": r[6]
    } for r in rows]

@app.post("/api/machines/{hostname}/verify")
def verify_machine(hostname: str, payload: VerifyPayload):
    """IT Admin xác nhận trạng thái bản quyền máy"""
    from datetime import datetime
    conn   = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE machines SET
            verified_status=%s, verified_note=%s,
            verified_by=%s, verified_at=%s
        WHERE hostname=%s
    """, (payload.status, payload.note, payload.by,
          datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
          hostname))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/summary")
def get_summary():
    conn   = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM machines")
    total_machines = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT name) FROM software")
    total_software = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM software WHERE status='suspicious'")
    total_suspicious = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT name) FROM software WHERE status='no_publisher'")
    total_no_pub = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM machines WHERE verified_status='verified_ok'")
    total_ok = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM machines WHERE verified_status='verified_crack'")
    total_crack = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM machines WHERE verified_status='unverified' OR verified_status IS NULL")
    total_unverified = cursor.fetchone()[0]
    cursor.execute("SELECT TOP 5 hostname, last_seen FROM machines ORDER BY last_seen DESC")
    recent = cursor.fetchall()
    conn.close()
    return {
        "total_machines":        total_machines,
        "total_unique_software": total_software,
        "total_suspicious":      total_suspicious,
        "total_no_publisher":    total_no_pub,
        "total_verified_ok":     total_ok,
        "total_verified_crack":  total_crack,
        "total_unverified":      total_unverified,
        "recent_machines":       [{"hostname": r[0], "last_seen": r[1]} for r in recent]
    }