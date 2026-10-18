import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatShortDate, formatWindow } from "../format.js";
import { SolarStatus, aud } from "./solar/common.jsx";
import { PaymentStatus } from "./solar/SolarPayment.jsx";

// "My bookings": everything the signed-in user has booked, across all NetZero Hub services.
// To add another service, add an entry to SERVICES.
const SERVICES = [
  {
    key: "recycling",
    title: "Recycling collections",
    load: (upcoming) => api("/bookings/", { params: { scope: upcoming ? "upcoming" : "" } }),
    listTo: "/",
    newTo: "/book",
    newLabel: "Book a collection",
    empty: "No recycling collections",
    Row: RecyclingRow,
  },
  {
    key: "solar",
    title: "Solar installations",
    load: (upcoming) => api("/solar/requests/", { params: { scope: upcoming ? "upcoming" : undefined } }),
    listTo: "/solar",
    newTo: "/solar/new",
    newLabel: "Request a solar installation",
    empty: "No solar requests",
    Row: SolarRow,
  },
];

export default function MyBookings() {
  const { user } = useAuth();
  const [scope, setScope] = useState("upcoming");

  return (
    <>
      <div className="page-head">
        <div>
          <h1>My bookings</h1>
          <p className="muted">
            {user.first_name ? `${user.first_name}, here's` : "Here's"} everything you've booked across NetZero Hub
            services.
          </p>
        </div>
        <Link className="btn" to="/services">
          Browse services
        </Link>
      </div>

      <div className="tabs" role="tablist">
        {[
          ["upcoming", "Upcoming"],
          ["all", "All"],
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

      {SERVICES.map((s) => (
        <ServiceSection key={s.key} service={s} upcoming={scope === "upcoming"} />
      ))}
    </>
  );
}

function ServiceSection({ service, upcoming }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const { Row } = service;

  useEffect(() => {
    setItems(null);
    setError("");
    service.load(upcoming).then(setItems).catch((err) => setError(err.message));
  }, [service, upcoming]);

  return (
    <section className="my-bookings-section">
      <div className="row-between">
        <h2>{service.title}</h2>
        <div className="actions-inline">
          <Link className="btn btn-small" to={service.listTo}>
            View all
          </Link>
          <Link className="btn btn-small btn-primary" to={service.newTo}>
            {service.newLabel}
          </Link>
        </div>
      </div>
      {error && <p className="alert alert-error">{error}</p>}
      {items === null && !error && <p className="muted">Loading…</p>}
      {items?.length === 0 && (
        <p className="muted my-bookings-empty">
          {service.empty}
          {upcoming ? " coming up." : " yet."}
        </p>
      )}
      <ul className="booking-list">
        {items?.map((item) => (
          <Row key={item.booking_reference || item.reference} item={item} />
        ))}
      </ul>
    </section>
  );
}

function RecyclingRow({ item: b }) {
  return (
    <li>
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
  );
}

function SolarRow({ item: r }) {
  return (
    <li>
      <Link to={`/solar/${r.reference}`} className="booking-row card">
        <div className="booking-when">
          <strong>{formatShortDate(r.assessment.date)}</strong>
          <span className="muted small">{formatWindow(r.assessment.start_time, r.assessment.end_time)}</span>
        </div>
        <div className="booking-what">
          <strong>{r.system.name} · site assessment</strong>
          <span className="muted small">
            {r.address.address_line}, {r.address.suburb} · {aud(r.total_price)}
          </span>
        </div>
        <div className="booking-meta">
          <SolarStatus status={r.status} />
          <PaymentStatus payment={r.payment} />
          <code className="ref">{r.reference}</code>
        </div>
      </Link>
    </li>
  );
}
