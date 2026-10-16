import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api } from "../../api.js";
import { formatDate, formatDateTime, formatWindow } from "../../format.js";
import { SolarStatus, aud } from "./common.jsx";

export default function SolarDetail() {
  const { reference } = useParams();
  const location = useLocation();
  const justBooked = location.state?.justBooked;
  const [r, setR] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState(justBooked ? "Your site assessment is booked. We've emailed the details." : "");
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api(`/solar/requests/${reference}/`).then(setR).catch((err) => setError(err.message));
  }, [reference]);

  async function cancel() {
    setBusy(true);
    setError("");
    try {
      setR(await api(`/solar/requests/${reference}/cancel/`, { method: "POST" }));
      setMessage("Your solar request has been cancelled.");
      setConfirmCancel(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!r) return error ? <p className="alert alert-error">{error}</p> : <p className="muted">Loading…</p>;

  return (
    <>
      <p className="crumbs">
        <Link to="/solar">Solar installations</Link> / {r.reference}
      </p>

      {message && <p className="alert alert-ok">{message}</p>}
      {error && <p className="alert alert-error">{error}</p>}

      <section className="card hero-card">
        <div className="hero-top">
          <div>
            <p className="eyebrow">Request reference</p>
            <h1 className="ref-big">{r.reference}</h1>
          </div>
          <SolarStatus status={r.status} />
        </div>

        <div className="hero-when">
          <span className="eyebrow">Site assessment</span>
          <strong>{formatDate(r.assessment.date)}</strong>
          <span>{formatWindow(r.assessment.start_time, r.assessment.end_time)} · {r.installer}</span>
        </div>

        {r.can_cancel && !confirmCancel && (
          <div className="actions actions-left">
            <button className="btn btn-danger-outline" onClick={() => setConfirmCancel(true)}>
              Cancel request
            </button>
            <span className="muted small">You can cancel at no cost any time before installation.</span>
          </div>
        )}
        {confirmCancel && (
          <div className="actions actions-left">
            <span>Cancel this solar request?</span>
            <button className="btn" onClick={() => setConfirmCancel(false)} disabled={busy}>Keep it</button>
            <button className="btn btn-danger" onClick={cancel} disabled={busy}>
              {busy ? "Cancelling…" : "Yes, cancel"}
            </button>
          </div>
        )}
      </section>

      {r.staff_note && r.status !== "CONFIRMED" && (
        <p className={`alert ${r.status === "CANCELLED" ? "alert-warn" : "alert-ok"}`}>
          <strong>Latest update:</strong> {r.staff_note}
        </p>
      )}

      {r.history?.length > 0 && (
        <section className="card">
          <h2>Progress</h2>
          <ol className="timeline solar-timeline">
            {r.history.map((ev, i) => (
              <li key={i}>
                <SolarStatus status={ev.status} />
                <span>
                  {ev.note || ev.status_label}
                  <span className="muted small"> · {ev.actor}</span>
                </span>
                <time className="muted small">{formatDateTime(ev.created_at)}</time>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="card">
        <h2>Your request</h2>
        <dl className="summary">
          <dt>System</dt>
          <dd>{r.system.name} ({r.system.panels} panels)</dd>
          {r.add_on_names.length > 0 && (<><dt>Extras</dt><dd>{r.add_on_names.join(", ")}</dd></>)}
          <dt>Address</dt>
          <dd>{r.address.address_line}, {r.address.suburb} {r.address.postcode}</dd>
          <dt>Property</dt>
          <dd>{r.property.type} · {r.property.storeys} · {r.property.roof} roof</dd>
          <dt>Quarterly usage</dt>
          <dd>{r.quarterly_usage_kwh.toLocaleString()} kWh</dd>
          {r.notes && (<><dt>Notes</dt><dd>{r.notes}</dd></>)}
          <dt>Contact</dt>
          <dd>{r.customer_name} · {r.customer_phone} · {r.customer_email}</dd>
          <dt>Requested</dt>
          <dd>{formatDateTime(r.created_at)}</dd>
        </dl>
      </section>

      <section className="card">
        <h2>Quote estimate</h2>
        <table className="fee-table">
          <tbody>
            {r.price_lines.map((line) => (
              <tr key={line.item}><td>{line.item}</td><td>{aud(line.amount)}</td></tr>
            ))}
            <tr className="total"><td>Estimated total (inc. GST)</td><td>{aud(r.total_price)}</td></tr>
          </tbody>
        </table>
        <p className="hint">The final price is confirmed after the site assessment. Government STC rebates may reduce it.</p>
      </section>

      <div className="actions">
        <Link className="btn" to="/solar">All solar requests</Link>
        <Link className="btn btn-primary" to="/solar/new">Request another installation</Link>
      </div>
    </>
  );
}
