import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatShortDate, formatWindow } from "../format.js";

export default function Bookings() {
  const { user } = useAuth();
  const [scope, setScope] = useState("upcoming");
  const [bookings, setBookings] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setBookings(null);
    api("/bookings/", { params: { scope: scope === "all" ? "" : scope } })
      .then(setBookings)
      .catch((err) => setError(err.message));
  }, [scope]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Hi {user.first_name || user.username}</h1>
          <p className="muted">Your recycling collection bookings.</p>
        </div>
        <Link className="btn btn-primary" to="/book">
          Book a collection
        </Link>
      </div>

      <div className="tabs" role="tablist">
        {[
          ["upcoming", "Upcoming"],
          ["all", "All bookings"],
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
      {bookings === null && !error && <p className="muted">Loading…</p>}
      {bookings?.length === 0 && (
        <div className="empty card">
          <h2>{scope === "upcoming" ? "No upcoming collections" : "No bookings yet"}</h2>
          <p className="muted">Book a free recycling collection, or a special collection for e-waste and bulky items.</p>
          <Link className="btn btn-primary" to="/book">
            Book a collection
          </Link>
        </div>
      )}

      <ul className="booking-list">
        {bookings?.map((b) => (
          <li key={b.booking_reference}>
            <Link to={`/bookings/${b.booking_reference}`} className="booking-row card">
              <div className="booking-when">
                {b.confirmed_collection ? (
                  <>
                    <strong>{formatShortDate(b.confirmed_collection.date)}</strong>
                    <span className="muted small">
                      {formatWindow(b.confirmed_collection.start_time, b.confirmed_collection.end_time)}
                    </span>
                  </>
                ) : (
                  <span className="muted">No date</span>
                )}
              </div>
              <div className="booking-what">
                <strong>{b.waste_type.name}</strong>
                <span className="muted small">
                  {b.collection_address.address_line}, {b.collection_address.suburb}
                </span>
              </div>
              <div className="booking-meta">
                <StatusBadge status={b.booking_status} />
                <code className="ref">{b.booking_reference}</code>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
