import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { formatShortDate, formatWindow } from "../../format.js";
import { SolarStatus, aud } from "./common.jsx";
import { PaymentStatus } from "./SolarPayment.jsx";

export default function SolarRequests() {
  const { user } = useAuth();
  const [scope, setScope] = useState("upcoming");
  const [requests, setRequests] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setRequests(null);
    api("/solar/requests/", { params: { scope: scope === "upcoming" ? "upcoming" : undefined } })
      .then(setRequests)
      .catch((err) => setError(err.message));
  }, [scope]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Solar installations</h1>
          <p className="muted">
            {user.first_name ? `${user.first_name}, follow` : "Follow"} your solar requests from site assessment to installation.
          </p>
        </div>
        <Link className="btn btn-primary" to="/solar/new">
          Request a solar installation
        </Link>
      </div>

      <div className="tabs" role="tablist">
        {[
          ["upcoming", "Upcoming"],
          ["all", "All requests"],
        ].map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={scope === key}
            className={`tab ${scope === key ? "is-active" : ""}`}
            onClick={() => setScope(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p className="alert alert-error">{error}</p>}
      {requests === null && !error && <p className="muted">Loading…</p>}
      {requests?.length === 0 && (
        <div className="empty card">
          <h2>{scope === "upcoming" ? "No upcoming site assessments" : "No solar requests yet"}</h2>
          <p className="muted">Tell us about your home and book a free site assessment to get started.</p>
          <Link className="btn btn-primary" to="/solar/new">
            Request a solar installation
          </Link>
        </div>
      )}

      <ul className="booking-list">
        {requests?.map((r) => (
          <li key={r.reference}>
            <Link to={`/solar/${r.reference}`} className="booking-row card">
              <div className="booking-when">
                <strong>{formatShortDate(r.assessment.date)}</strong>
                <span className="muted small">{formatWindow(r.assessment.start_time, r.assessment.end_time)}</span>
              </div>
              <div className="booking-what">
                <strong>
                  {r.system.name}
                  {r.add_ons.length > 0 && (
                    <span className="muted"> + {r.add_ons.length} extra{r.add_ons.length > 1 ? "s" : ""}</span>
                  )}
                </strong>
                <span className="muted small">
                  {r.address.address_line}, {r.address.suburb} · {r.installer} · {aud(r.total_price)}
                </span>
              </div>
              <div className="booking-meta">
                <SolarStatus status={r.status} />
                <PaymentStatus payment={r.payment} />
                <code className="ref">{r.reference}</code>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
