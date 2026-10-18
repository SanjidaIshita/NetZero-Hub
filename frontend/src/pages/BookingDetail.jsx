import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api } from "../api.js";
import SlotPicker from "../components/SlotPicker.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatDate, formatDateTime, formatWindow, money, quantityLabel } from "../format.js";

export default function BookingDetail() {
  const { reference } = useParams();
  const location = useLocation();
  const [booking, setBooking] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState(location.state?.justBooked ? "Your booking is confirmed." : "");
  const [mode, setMode] = useState(null); // "reschedule" | "cancel" | "json"
  const [slots, setSlots] = useState(null);
  const [newSlot, setNewSlot] = useState(null);
  const [output, setOutput] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      api(`/bookings/${reference}/`)
        .then(setBooking)
        .catch((err) => setError(err.message)),
    [reference],
  );

  useEffect(() => {
    load();
  }, [load]);

  async function openReschedule() {
    setMode("reschedule");
    setNewSlot(null);
    setError("");
    try {
      const avail = await api("/availability/", {
        params: { postcode: booking.collection_address.postcode, waste_type: booking.waste_type.code },
      });
      setSlots(avail.slots.filter((s) => s.id !== booking.slot?.id));
    } catch (err) {
      setError(err.message);
    }
  }

  async function act(path, body, successText) {
    setBusy(true);
    setError("");
    try {
      const updated = await api(`/bookings/${reference}/${path}/`, { method: "POST", body });
      setBooking(updated);
      setMode(null);
      setMessage(successText);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleJson() {
    if (mode === "json") return setMode(null);
    setOutput(await api(`/bookings/${reference}/output/`));
    setMode("json");
  }

  if (!booking) {
    return error ? <p className="alert alert-error">{error}</p> : <p className="muted">Loading…</p>;
  }

  const c = booking.confirmed_collection;
  const p = booking.provider_contact;

  return (
    <>
      <p className="crumbs">
        <Link to="/">My bookings</Link> / {booking.booking_reference}
      </p>

      {message && <p className="alert alert-ok">{message}</p>}
      {error && <p className="alert alert-error">{error}</p>}

      <section className="card hero-card">
        <div className="hero-top">
          <div>
            <p className="eyebrow">Booking reference</p>
            <h1 className="ref-big">{booking.booking_reference}</h1>
          </div>
          <StatusBadge status={booking.booking_status} />
        </div>

        {booking.booking_status === "REJECTED" ? (
          <p className="alert alert-error">
            This request was not accepted: {booking.rejection_reason}
          </p>
        ) : c ? (
          <div className="hero-when">
            <span className="eyebrow">Collection</span>
            <strong>{formatDate(c.date)}</strong>
            <span>{formatWindow(c.start_time, c.end_time)}</span>
          </div>
        ) : null}

        {booking.booking_status === "RESCHEDULED" && (
          <p className="alert alert-warn">
            Your earlier collection was missed, so we've automatically booked this make-up collection.
          </p>
        )}

        {booking.can_change && (
          <div className="actions actions-left">
            <button className="btn" onClick={openReschedule}>
              Change date
            </button>
            <button className="btn btn-danger-outline" onClick={() => setMode("cancel")}>
              Cancel booking
            </button>
            <span className="muted small">Changes allowed until {formatDateTime(booking.change_deadline)}</span>
          </div>
        )}
      </section>

      {mode === "reschedule" && (
        <section className="card">
          <h2>Choose a new date</h2>
          {slots === null ? (
            <p className="muted">Loading available dates…</p>
          ) : (
            <SlotPicker slots={slots} value={newSlot} onChange={setNewSlot} />
          )}
          <div className="actions">
            <button className="btn" onClick={() => setMode(null)}>
              Keep current date
            </button>
            <button
              className="btn btn-primary"
              disabled={!newSlot || busy}
              onClick={() => act("reschedule", { slot_id: newSlot }, "Your collection has been rescheduled.")}
            >
              {busy ? "Saving…" : "Move collection"}
            </button>
          </div>
        </section>
      )}

      {mode === "cancel" && (
        <section className="card confirm-card">
          <h2>Cancel this collection?</h2>
          <p>
            Your slot will be released.
            {Number(booking.fee.amount) > 0 && ` Your ${money(booking.fee.amount)} payment will be refunded.`}
          </p>
          <div className="actions">
            <button className="btn" onClick={() => setMode(null)}>
              Keep booking
            </button>
            <button
              className="btn btn-danger"
              disabled={busy}
              onClick={() => act("cancel", undefined, "Your booking has been cancelled.")}
            >
              {busy ? "Cancelling…" : "Yes, cancel"}
            </button>
          </div>
        </section>
      )}

      <div className="detail-grid">
        <section className="card">
          <h2>Collection details</h2>
          <dl className="summary">
            <dt>Waste type</dt>
            <dd>
              {booking.waste_type.name}
              <p className="muted small">{booking.waste_type.accepted_items}</p>
            </dd>
            <dt>Quantity</dt>
            <dd>{quantityLabel(booking.estimated_quantity)}</dd>
            <dt>Address</dt>
            <dd>
              {booking.collection_address.address_line}, {booking.collection_address.suburb}{" "}
              {booking.collection_address.postcode}
            </dd>
            {booking.special_instructions && (
              <>
                <dt>Instructions</dt>
                <dd>{booking.special_instructions}</dd>
              </>
            )}
            <dt>Fee</dt>
            <dd>
              {booking.fee.chargeable ? (
                <>
                  {money(booking.fee.amount)} · receipt {booking.fee.receipt_number}
                  {booking.fee.payment_status === "REFUNDED" && <span className="tag tag-free">Refunded</span>}
                </>
              ) : (
                "Free"
              )}
            </dd>
          </dl>
        </section>

        <section className="card">
          <h2>Your collection provider</h2>
          {p ? (
            <dl className="summary">
              <dt>Provider</dt>
              <dd>{p.name}</dd>
              <dt>Phone</dt>
              <dd>
                <a href={`tel:${p.phone.replace(/\s/g, "")}`}>{p.phone}</a>
              </dd>
              <dt>Email</dt>
              <dd>
                <a href={`mailto:${p.email}`}>{p.email}</a>
              </dd>
            </dl>
          ) : (
            <p className="muted">No provider assigned.</p>
          )}
        </section>
      </div>

      {/* <section className="card">
        <h2>History and notifications</h2>
        <ol className="timeline">
          {booking.events.map((ev, i) => (
            <li key={i}>
              <StatusBadge status={ev.status} />
              <span>{ev.note}</span>
              <time className="muted small">{formatDateTime(ev.created_at)}</time>
            </li>
          ))}
        </ol>
        {booking.notification && (
          <p className="muted small">
            Latest notice “{booking.notification.subject}” sent to {booking.notification.recipient}{" "}
            {formatDateTime(booking.notification.sent_at)}.
          </p>
        )}
      </section> */}

      {/* <section className="card">
        <div className="row-between">
          <h2>Service output (API)</h2>
          <button className="btn btn-small" onClick={toggleJson}>
            {mode === "json" ? "Hide JSON" : "Show JSON"}
          </button>
        </div>
        <p className="muted small">
          The same WMS-002 output other services receive from <code>/api/v1/integration/bookings/</code>.
        </p>
        {mode === "json" && output && <pre className="json">{JSON.stringify(output, null, 2)}</pre>}
      </section> */}
    </>
  );
}
