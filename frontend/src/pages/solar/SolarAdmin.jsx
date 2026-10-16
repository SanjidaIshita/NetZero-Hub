import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api.js";
import { formatDate, formatShortDate, formatWindow } from "../../format.js";
import { SolarStatus, aud } from "./common.jsx";


const FILTERS = [
  ["ACTIVE", "In progress"],
  ["CONFIRMED", "Assessment booked"],
  ["ASSESSED", "Site assessed"],
  ["COMPLETED", "Installed"],
  ["CANCELLED", "Cancelled"],
  ["", "All"],
];

const ACTION_HINT = {
  ASSESSED: "e.g. Roof checked, suits 13 panels facing north. Quote confirmed.",
  COMPLETED: "e.g. System installed and switched on. Paperwork emailed.",
  CANCELLED: "Reason for cancelling (shown to the customer)",
};

/** Staff view: every customer's solar request, with actions to move each one to its next stage. */
export default function SolarAdmin() {
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState(null);
  const [status, setStatus] = useState("ACTIVE");
  const [date, setDate] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(null); // { reference, status, label }
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setRows(null);
    Promise.all([
      api("/solar/admin/summary/"),
      api("/solar/admin/requests/", { params: { status, date, q: search } }),
    ])
      .then(([s, r]) => {
        setSummary(s);
        setRows(r);
      })
      .catch((err) => setError(err.message));
  }, [status, date, search]);

  useEffect(() => {
    load();
  }, [load]);

  // Search as you type, after a short pause
  useEffect(() => {
    const t = setTimeout(() => setSearch(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  async function save() {
    setBusy(true);
    setError("");
    try {
      const updated = await api(`/solar/admin/requests/${editing.reference}/status/`, {
        method: "POST",
        body: { status: editing.status, note },
      });
      setMessage(`${updated.reference} is now "${updated.status_label}".`);
      setEditing(null);
      setNote("");
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const s = summary;
  const maxSize = s ? Math.max(1, ...s.by_system_size.map((x) => x.count)) : 1;

  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Staff only · ORG-001</p>
          <h1>Solar admin dashboard</h1>
          <p className="muted">Every customer's solar request. Record each site assessment and installation here.</p>
        </div>
      </div>

      {s && (
        <div className="sa-stats">
          <div className="sa-stat">
            <span className="sa-stat-label">Assessments today</span>
            <strong>{s.assessments_today}</strong>
            <span className="muted small">{s.assessments_next_7_days} in the next 7 days</span>
          </div>
          <div className="sa-stat">
            <span className="sa-stat-label">In progress</span>
            <strong>{s.by_status.CONFIRMED + s.by_status.ASSESSED}</strong>
            <span className="muted small">
              {s.by_status.CONFIRMED} booked · {s.by_status.ASSESSED} assessed
            </span>
          </div>
          <div className="sa-stat">
            <span className="sa-stat-label">Installed</span>
            <strong>{s.by_status.COMPLETED}</strong>
            <span className="muted small">{aud(s.installed_value)} installed</span>
          </div>
          <div className="sa-stat">
            <span className="sa-stat-label">Pipeline value</span>
            <strong>{aud(s.pipeline_value)}</strong>
            <span className="muted small">{s.by_status.CANCELLED} cancelled · {s.total} total</span>
          </div>
        </div>
      )}

      {s && s.total > 0 && (
        <section className="card sa-sizes">
          <h2>Requests by system size</h2>
          <ul>
            {s.by_system_size.map((x) => (
              <li key={x.id}>
                <span className="sa-size-name">{x.name}</span>
                <span className="sa-bar" aria-hidden="true">
                  <span style={{ width: `${(x.count / maxSize) * 100}%` }} />
                </span>
                <span className="sa-size-count">{x.count}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="tabs" role="tablist">
        {FILTERS.map(([key, label]) => (
          <button key={key || "all"} role="tab" aria-selected={status === key}
            className={`tab ${status === key ? "is-active" : ""}`} onClick={() => setStatus(key)}>
            {label}
          </button>
        ))}
      </div>

      <div className="filter-bar sa-filters">
        <label className="inline-field">
          Assessment date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="inline-field sa-search">
          Search
          <input type="search" placeholder="Name, reference, suburb, postcode…" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        {(date || q) && (
          <button className="btn btn-small" onClick={() => { setDate(""); setQ(""); }}>Clear</button>
        )}
      </div>

      {message && <p className="alert alert-ok">{message}</p>}
      {error && <p className="alert alert-error">{error}</p>}
      {rows === null && !error && <p className="muted">Loading…</p>}
      {rows?.length === 0 && <p className="card empty muted">No solar requests match these filters.</p>}

      {editing && (
        <section className="card sa-edit">
          <h2>Mark {editing.reference} as “{editing.label}”</h2>
          <label className="field">
            <span>Note for the customer {editing.status === "CANCELLED" ? "" : "(optional)"}</span>
            <textarea rows={3} maxLength={1000} placeholder={ACTION_HINT[editing.status]} value={note}
              onChange={(e) => setNote(e.target.value)} />
          </label>
          <div className="actions actions-left">
            <button className="btn" onClick={() => setEditing(null)} disabled={busy}>Back</button>
            <button className={`btn ${editing.status === "CANCELLED" ? "btn-danger" : "btn-primary"}`}
              onClick={save} disabled={busy || (editing.status === "CANCELLED" && !note.trim())}>
              {busy ? "Saving…" : `Save as “${editing.label}”`}
            </button>
          </div>
        </section>
      )}

      {rows?.length > 0 && (
        <>
          <p className="muted small">{rows.length} request{rows.length === 1 ? "" : "s"}</p>
          <div className="card table-card">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Assessment</th>
                  <th>Reference</th>
                  <th>Customer</th>
                  <th>Address</th>
                  <th>System</th>
                  <th>Quote</th>
                  <th>Status</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.reference}>
                    <td className="nowrap">
                      {formatShortDate(r.assessment.date)}
                      <div className="muted small">{formatWindow(r.assessment.start_time, r.assessment.end_time)}</div>
                    </td>
                    <td><code>{r.reference}</code></td>
                    <td>
                      {r.customer_name}
                      <div className="muted small">{r.customer_account.username} · {r.customer_phone}</div>
                    </td>
                    <td>
                      {r.address.address_line}, {r.address.suburb} {r.address.postcode}
                      <div className="muted small">{r.property.storeys} · {r.property.roof} roof</div>
                    </td>
                    <td>
                      {r.system.name}
                      {r.add_on_names.length > 0 && <div className="muted small">+ {r.add_on_names.join(", ")}</div>}
                    </td>
                    <td className="nowrap">{aud(r.total_price)}</td>
                    <td><SolarStatus status={r.status} /></td>
                    <td className="nowrap">
                      {r.allowed_transitions.map((t) => (
                        <button key={t.status}
                          className={`btn btn-small ${t.status === "CANCELLED" ? "btn-danger-outline" : "btn-primary"}`}
                          onClick={() => { setEditing({ reference: r.reference, status: t.status, label: t.label }); setNote(""); setMessage(""); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                          {t.status === "CANCELLED" ? "Cancel" : t.label}
                        </button>
                      ))}
                      {r.allowed_transitions.length === 0 && <span className="muted small">No actions</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {date && <p className="muted small">Showing assessments on {formatDate(date)}.</p>}
        </>
      )}

      <p className="muted small">
        Need to edit something else? Use <Link to="/solar">the customer view</Link> or Django admin at <code>/admin/</code>.
      </p>
    </>
  );
}
