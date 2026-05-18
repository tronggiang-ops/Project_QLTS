import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = "http://localhost:8000";

function StatusBadge({ status }) {
  const map = {
    trusted: { label: "✅ Tin cậy", cls: "badge-green" },
    unknown: { label: "⚠️ Chưa xác định", cls: "badge-yellow" },
    no_publisher: { label: "❓ Không publisher", cls: "badge-gray" },
    suspicious: { label: "🚨 Nghi ngờ", cls: "badge-red" },
  };
  const s = map[status] || map.unknown;
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

function VerifiedBadge({ status }) {
  const map = {
    verified_ok: { label: "✅ Hợp lệ", cls: "badge-green" },
    verified_crack: { label: "🚨 Vi phạm", cls: "badge-red" },
    unverified: { label: "⏳ Chưa xác nhận", cls: "badge-yellow" },
  };
  const s = map[status] || map.unverified;
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

function VerifyModal({ machine, onClose, onSave }) {
  const [status, setStatus] = useState(machine.verified_status || "unverified");
  const [note, setNote] = useState(machine.verified_note || "");
  const [by, setBy] = useState(machine.verified_by || "IT Admin");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/api/machines/${machine.hostname}/verify`, {
        status,
        note,
        by,
      });
      onSave();
      onClose();
    } catch {
      alert("Lỗi khi lưu!");
    }
    setSaving(false);
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          background: "white",
          borderRadius: 12,
          padding: 32,
          width: 480,
          boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
        }}
      >
        <h2 style={{ marginBottom: 4 }}>Xác nhận bản quyền</h2>
        <p style={{ color: "#64748b", fontSize: 13, marginBottom: 24 }}>
          Máy: <strong>{machine.hostname}</strong> — User:{" "}
          <strong>{machine.username}</strong>
        </p>

        {/* KMS Info */}
        {machine.kms_info?.detail && (
          <div
            style={{
              background: machine.kms_info.suspicious ? "#fff5f5" : "#f8fafc",
              border: `1px solid ${machine.kms_info.suspicious ? "#fca5a5" : "#e2e8f0"}`,
              borderRadius: 8,
              padding: "12px 16px",
              marginBottom: 20,
            }}
          >
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                marginBottom: 4,
                color: "#64748b",
              }}
            >
              KMS ACTIVATION INFO
            </div>
            <div style={{ fontSize: 13 }}>
              <strong>Method:</strong> {machine.kms_info.method}
            </div>
            <div
              style={{
                fontSize: 13,
                color: machine.kms_info.suspicious ? "#dc2626" : "#374151",
              }}
            >
              {machine.kms_info.detail}
            </div>
          </div>
        )}

        {/* Trạng thái */}
        <div style={{ marginBottom: 16 }}>
          <label
            style={{
              fontSize: 13,
              fontWeight: 500,
              display: "block",
              marginBottom: 8,
            }}
          >
            Trạng thái bản quyền
          </label>
          {[
            { val: "verified_ok", label: "✅ Hợp lệ — có license/hóa đơn" },
            {
              val: "verified_crack",
              label: "🚨 Vi phạm — xác nhận đang dùng crack",
            },
            { val: "unverified", label: "⏳ Chưa xác nhận" },
          ].map((opt) => (
            <label
              key={opt.val}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 14px",
                marginBottom: 8,
                borderRadius: 8,
                cursor: "pointer",
                border:
                  status === opt.val
                    ? "2px solid #3b82f6"
                    : "1px solid #e2e8f0",
                background: status === opt.val ? "#eff6ff" : "white",
              }}
            >
              <input
                type="radio"
                value={opt.val}
                checked={status === opt.val}
                onChange={() => setStatus(opt.val)}
                style={{ accentColor: "#3b82f6" }}
              />
              <span style={{ fontSize: 14 }}>{opt.label}</span>
            </label>
          ))}
        </div>

        {/* Ghi chú */}
        <div style={{ marginBottom: 16 }}>
          <label
            style={{
              fontSize: 13,
              fontWeight: 500,
              display: "block",
              marginBottom: 8,
            }}
          >
            Ghi chú
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Ví dụ: License key ABC-123, mua ngày 01/01/2025..."
            style={{
              width: "100%",
              padding: "10px 14px",
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              fontSize: 13,
              resize: "vertical",
              minHeight: 80,
              outline: "none",
              boxSizing: "border-box",
            }}
          />
        </div>

        {/* Người xác nhận */}
        <div style={{ marginBottom: 24 }}>
          <label
            style={{
              fontSize: 13,
              fontWeight: 500,
              display: "block",
              marginBottom: 8,
            }}
          >
            Người xác nhận
          </label>
          <input
            value={by}
            onChange={(e) => setBy(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 14px",
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              fontSize: 13,
              outline: "none",
              boxSizing: "border-box",
            }}
          />
        </div>

        <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
          <button className="btn" onClick={onClose}>
            Hủy
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Đang lưu..." : "Lưu xác nhận"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Summary({ onSelectMachine }) {
  const [summary, setSummary] = useState(null);
  const [machines, setMachines] = useState([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [verifyMachine, setVerifyMachine] = useState(null);

  const fetchData = useCallback(() => {
    setLoading(true);
    setError(false);
    Promise.all([
      axios.get(`${API}/api/summary`),
      axios.get(`${API}/api/machines`),
    ])
      .then(([s, m]) => {
        setSummary(s.data);
        setMachines(m.data);
        setLoading(false);
        setLastUpdate(new Date().toLocaleTimeString("vi-VN"));
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const isOnline = (lastSeen) =>
    (new Date() - new Date(lastSeen)) / 1000 / 60 < 60 * 25;

  const filtered = machines.filter((m) => {
    const matchSearch =
      m.hostname.toLowerCase().includes(search.toLowerCase()) ||
      m.ip.includes(search) ||
      (m.username || "").toLowerCase().includes(search.toLowerCase());
    const matchFilter =
      filter === "all" ||
      (filter === "online" && isOnline(m.last_seen)) ||
      (filter === "verified_ok" && m.verified_status === "verified_ok") ||
      (filter === "verified_crack" && m.verified_status === "verified_crack") ||
      (filter === "unverified" &&
        (m.verified_status === "unverified" || !m.verified_status));
    return matchSearch && matchFilter;
  });

  if (loading) return <div className="loading">Đang tải dữ liệu...</div>;
  if (error)
    return (
      <div className="loading">
        <div style={{ fontSize: 32, marginBottom: 16 }}>⚠️</div>
        <div style={{ color: "#dc2626", marginBottom: 16 }}>
          Không kết nối được API Server
        </div>
        <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 24 }}>
          Chạy:{" "}
          <code
            style={{
              background: "#f1f5f9",
              padding: "2px 8px",
              borderRadius: 4,
            }}
          >
            python -m uvicorn main:app --host 0.0.0.0 --port 8000
          </code>
        </div>
        <button className="btn btn-primary" onClick={fetchData}>
          Thử lại
        </button>
      </div>
    );

  return (
    <div>
      {verifyMachine && (
        <VerifyModal
          machine={verifyMachine}
          onClose={() => setVerifyMachine(null)}
          onSave={fetchData}
        />
      )}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <div className="page-title" style={{ margin: 0 }}>
          Tổng quan
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {lastUpdate && (
            <span style={{ fontSize: 12, color: "#94a3b8" }}>
              Cập nhật lúc {lastUpdate}
            </span>
          )}
          <button className="btn" onClick={fetchData}>
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        {[
          {
            label: "Tổng số máy",
            value: summary.total_machines,
            sub: "đang theo dõi",
            color: "#1a1a2e",
          },
          {
            label: "✅ Hợp lệ",
            value: summary.total_verified_ok,
            sub: "đã xác nhận",
            color: "#16a34a",
          },
          {
            label: "🚨 Vi phạm",
            value: summary.total_verified_crack,
            sub: "cần xử lý ngay",
            color: "#dc2626",
          },
          {
            label: "⏳ Chưa xác nhận",
            value: summary.total_unverified,
            sub: "cần IT kiểm tra",
            color: "#d97706",
          },
          {
            label: "Phần mềm nghi ngờ",
            value: summary.total_suspicious,
            sub: "toàn hệ thống",
            color: summary.total_suspicious > 0 ? "#dc2626" : "#16a34a",
          },
        ].map((s, i) => (
          <div className="stat-card" key={i}>
            <div className="label">{s.label}</div>
            <div className="value" style={{ color: s.color }}>
              {s.value}
            </div>
            <div className="sub">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Filter + Search */}
      <div className="card">
        <div
          style={{
            display: "flex",
            gap: 8,
            marginBottom: 16,
            flexWrap: "wrap",
          }}
        >
          {[
            { key: "all", label: "Tất cả" },
            { key: "unverified", label: "⏳ Chưa xác nhận" },
            { key: "verified_ok", label: "✅ Hợp lệ" },
            { key: "verified_crack", label: "🚨 Vi phạm" },
            { key: "online", label: "🟢 Online" },
          ].map((f) => (
            <button
              key={f.key}
              className={`btn ${filter === f.key ? "btn-primary" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <input
          className="search-box"
          placeholder="Tìm theo tên máy, IP, username..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <h2 style={{ marginBottom: 16 }}>
          Danh sách máy tính
          <span
            style={{
              fontSize: 13,
              fontWeight: 400,
              color: "#64748b",
              marginLeft: 8,
            }}
          >
            {filtered.length} máy
          </span>
        </h2>
        {filtered.length === 0 ? (
          <div className="empty">Không tìm thấy máy nào</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Tên máy</th>
                <th>IP</th>
                <th>Username</th>
                <th>Windows</th>
                <th>KMS</th>
                <th>Office</th>
                <th>Lần cuối sync</th>
                <th>Online</th>
                <th>Bản quyền</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((m, i) => (
                <tr
                  key={m.hostname}
                  style={{
                    background:
                      m.verified_status === "verified_crack"
                        ? "#fff5f5"
                        : "transparent",
                  }}
                >
                  <td style={{ color: "#94a3b8" }}>{i + 1}</td>
                  <td>
                    <strong>{m.hostname}</strong>
                  </td>
                  <td>
                    <span className="badge badge-gray">{m.ip}</span>
                  </td>
                  <td>{m.username || "—"}</td>
                  <td>
                    <span
                      className={`badge ${m.windows_license?.status === "Đã kích hoạt" ? "badge-green" : "badge-red"}`}
                    >
                      {m.windows_license?.status || "—"}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${m.kms_info?.suspicious ? "badge-red" : m.kms_info?.method === "HWID" ? "badge-yellow" : "badge-gray"}`}
                      title={m.kms_info?.detail || ""}
                    >
                      {m.kms_info?.method || "—"}
                    </span>
                  </td>
                  <td>
                    <span className="badge badge-blue" style={{ fontSize: 11 }}>
                      {m.office_license?.product
                        ? m.office_license.product
                            .replace("Retail", "")
                            .replace("Volume", "Vol")
                            .substring(0, 16)
                        : "Không có"}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: "#64748b" }}>
                    {new Date(m.last_seen).toLocaleString("vi-VN")}
                  </td>
                  <td>
                    {isOnline(m.last_seen) ? (
                      <span className="badge badge-green">
                        <span className="online-dot" />
                        Online
                      </span>
                    ) : (
                      <span className="badge badge-gray">Offline</span>
                    )}
                  </td>
                  <td>
                    <VerifiedBadge status={m.verified_status} />
                  </td>
                  <td style={{ display: "flex", gap: 6 }}>
                    <button className="btn" onClick={() => onSelectMachine(m)}>
                      Chi tiết
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={() => setVerifyMachine(m)}
                    >
                      Xác nhận
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function MachineDetail({ machine: initialMachine, onBack }) {
  const [machine, setMachine] = useState(initialMachine);
  const [software, setSoftware] = useState([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [verifyOpen, setVerifyOpen] = useState(false);

  useEffect(() => {
    axios
      .get(`${API}/api/machines/${machine.hostname}/software`)
      .then((r) => {
        setSoftware(r.data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [machine.hostname]);

  const refreshMachine = () => {
    axios.get(`${API}/api/machines`).then((r) => {
      const updated = r.data.find((m) => m.hostname === machine.hostname);
      if (updated) setMachine(updated);
    });
  };

  const filtered = software.filter((sw) => {
    const matchSearch =
      sw.name.toLowerCase().includes(search.toLowerCase()) ||
      (sw.publisher || "").toLowerCase().includes(search.toLowerCase());
    return (filter === "all" || sw.status === filter) && matchSearch;
  });

  const counts = {
    all: software.length,
    trusted: software.filter((s) => s.status === "trusted").length,
    unknown: software.filter((s) => s.status === "unknown").length,
    no_publisher: software.filter((s) => s.status === "no_publisher").length,
    suspicious: software.filter((s) => s.status === "suspicious").length,
  };

  return (
    <div>
      {verifyOpen && (
        <VerifyModal
          machine={machine}
          onClose={() => setVerifyOpen(false)}
          onSave={() => {
            refreshMachine();
            setVerifyOpen(false);
          }}
        />
      )}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <div className="back-btn" onClick={onBack} style={{ margin: 0 }}>
          ← Quay lại
        </div>
        <button className="btn btn-primary" onClick={() => setVerifyOpen(true)}>
          ✏️ Xác nhận bản quyền
        </button>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div className="page-title" style={{ margin: 0 }}>
          🖥️ {machine.hostname}
        </div>
        <VerifiedBadge status={machine.verified_status} />
      </div>

      {/* Thông tin máy */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="label">Địa chỉ IP</div>
          <div className="value" style={{ fontSize: 18 }}>
            {machine.ip}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Username</div>
          <div className="value" style={{ fontSize: 18 }}>
            {machine.username || "—"}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Windows License</div>
          <div style={{ marginTop: 8 }}>
            <span
              className={`badge ${machine.windows_license?.status === "Đã kích hoạt" ? "badge-green" : "badge-red"}`}
            >
              {machine.windows_license?.status || "—"}
            </span>
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 6 }}>
              {machine.windows_license?.channel}
            </div>
          </div>
        </div>
        <div className="stat-card">
          <div className="label">KMS Activation</div>
          <div style={{ marginTop: 8 }}>
            <span
              className={`badge ${machine.kms_info?.suspicious ? "badge-red" : machine.kms_info?.method === "HWID" ? "badge-yellow" : "badge-gray"}`}
            >
              {machine.kms_info?.method || "—"}
            </span>
            <div
              style={{
                fontSize: 11,
                color: machine.kms_info?.suspicious ? "#dc2626" : "#94a3b8",
                marginTop: 6,
              }}
            >
              {machine.kms_info?.detail}
            </div>
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Office License</div>
          <div style={{ marginTop: 8 }}>
            <span className="badge badge-blue" style={{ fontSize: 11 }}>
              {machine.office_license?.product || "Không có"}
            </span>
          </div>
        </div>
        <div
          className="stat-card"
          style={{
            border:
              machine.suspicious_processes?.length > 0
                ? "2px solid #dc2626"
                : "0.5px solid #e2e8f0",
          }}
        >
          <div className="label">Process nghi ngờ</div>
          <div style={{ marginTop: 8 }}>
            {machine.suspicious_processes?.length > 0 ? (
              <span className="badge badge-red">
                🚨 {machine.suspicious_processes.length} process
              </span>
            ) : (
              <span className="badge badge-green">✅ An toàn</span>
            )}
          </div>
        </div>
      </div>

      {/* Ghi chú xác nhận */}
      {machine.verified_note && (
        <div
          className="card"
          style={{
            background:
              machine.verified_status === "verified_crack"
                ? "#fff5f5"
                : "#f0fdf4",
            border: `1px solid ${machine.verified_status === "verified_crack" ? "#fca5a5" : "#86efac"}`,
          }}
        >
          <div style={{ fontSize: 13, color: "#64748b", marginBottom: 4 }}>
            Ghi chú bởi <strong>{machine.verified_by}</strong> lúc{" "}
            {machine.verified_at}
          </div>
          <div style={{ fontSize: 14 }}>{machine.verified_note}</div>
        </div>
      )}

      {/* Filter stats */}
      <div className="stats-grid" style={{ marginBottom: 24 }}>
        {[
          { key: "all", label: "Tất cả", color: "#1a1a2e" },
          { key: "trusted", label: "✅ Tin cậy", color: "#16a34a" },
          { key: "unknown", label: "⚠️ Chưa xác định", color: "#d97706" },
          {
            key: "no_publisher",
            label: "❓ Không publisher",
            color: "#6b7280",
          },
          { key: "suspicious", label: "🚨 Nghi ngờ", color: "#dc2626" },
        ].map((item) => (
          <div
            key={item.key}
            className="stat-card"
            onClick={() => setFilter(item.key)}
            style={{
              cursor: "pointer",
              border:
                filter === item.key
                  ? `2px solid ${item.color}`
                  : "0.5px solid #e2e8f0",
            }}
          >
            <div className="label">{item.label}</div>
            <div className="value" style={{ color: item.color }}>
              {counts[item.key]}
            </div>
          </div>
        ))}
      </div>

      {/* Danh sách phần mềm */}
      <div className="card">
        <h2>
          Danh sách phần mềm
          {filter !== "all" && (
            <span
              style={{
                fontSize: 13,
                fontWeight: 400,
                color: "#64748b",
                marginLeft: 8,
              }}
            >
              — {filtered.length} kết quả
            </span>
          )}
        </h2>
        <input
          className="search-box"
          placeholder="Tìm theo tên phần mềm, publisher..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {loading ? (
          <div className="loading">Đang tải...</div>
        ) : filtered.length === 0 ? (
          <div className="empty">Không tìm thấy</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Tên phần mềm</th>
                <th>Phiên bản</th>
                <th>Publisher</th>
                <th>Ngày cài</th>
                <th>Trạng thái</th>
                <th>Lý do</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((sw, i) => (
                <tr
                  key={i}
                  style={{
                    background:
                      sw.status === "suspicious" ? "#fff5f5" : "transparent",
                  }}
                >
                  <td style={{ color: "#94a3b8" }}>{i + 1}</td>
                  <td>
                    <strong>{sw.name}</strong>
                  </td>
                  <td>
                    {sw.version ? (
                      <span className="badge badge-blue">{sw.version}</span>
                    ) : (
                      <span style={{ color: "#94a3b8" }}>—</span>
                    )}
                  </td>
                  <td style={{ color: "#64748b" }}>{sw.publisher || "—"}</td>
                  <td style={{ color: "#64748b", fontSize: 12 }}>
                    {sw.install_date
                      ? sw.install_date.replace(
                          /(\d{4})(\d{2})(\d{2})/,
                          "$3/$2/$1",
                        )
                      : "—"}
                  </td>
                  <td>
                    <StatusBadge status={sw.status} />
                  </td>
                  <td style={{ fontSize: 12, color: "#94a3b8" }}>
                    {sw.reason || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState("summary");
  const [selectedMachine, setSelectedMachine] = useState(null);

  return (
    <div className="layout">
      <div className="sidebar">
        <h1>🖥️ Software Audit</h1>
        <p>Quản lý bản quyền nội bộ</p>
        <ul className="sidebar-menu">
          <li
            className={page === "summary" ? "active" : ""}
            onClick={() => {
              setPage("summary");
              setSelectedMachine(null);
            }}
          >
            📊 Tổng quan
          </li>
        </ul>
      </div>
      <div className="main">
        {page === "summary" && (
          <Summary
            onSelectMachine={(m) => {
              setSelectedMachine(m);
              setPage("detail");
            }}
          />
        )}
        {page === "detail" && (
          <MachineDetail
            machine={selectedMachine}
            onBack={() => {
              setPage("summary");
              setSelectedMachine(null);
            }}
          />
        )}
      </div>
    </div>
  );
}
