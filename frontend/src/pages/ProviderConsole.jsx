import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import StatusBadge from "../components/StatusBadge.jsx";
import { formatDate, formatShortDate, formatWindow, quantityLabel } from "../format.js";

/** Staff view of the collection run sheet; simulates the provider's ICollectionStatus callbacks. */
export default function ProviderConsole() {
  const [date, setDate] = useState(""); // "" = all upcoming collections
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [busyRef, setBusyRef] = useState(null);

  const load = useCallback(() => {
    setRows(null);
    api("/provider/collections/", { params: { date } })
      .then(setRows)
      .catch((err) => setError(err.message));
  }, [date]);

  useEffect(() => {
    load();
  }, [load]);

  async function report(ref, outcome) {
    let body;
    if (outcome === "missed") {
      const reason = window.prompt("Reason the collection was missed (optional):", "");
      if (reason === null) return;
      body = { reason };
    }
    setBusyRef(ref);
    setError("");
    try {
      await api(`/provider/collections/${ref}/${outcome}/`, { method: "POST", body });
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyRef(null);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Provider console</h1>
          <p className="muted">
            All residents' upcoming collections. Mark each one as collected or missed.
          </p>
        </div>
        <div className="filter-bar">
          <label className="inline-field">
            Date
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          {date && (
            <button className="btn btn-small" onClick={() => setDate("")}>
              Show all upcoming
            </button>
          )}
        </div>
      </div>

      {error && <p className="alert alert-error">{error}</p>}
      {rows === null && !error && <p className="muted">Loading…</p>}
      {rows?.length === 0 && (
        <p className="card empty muted">
          {date ? `No collections booked for ${formatDate(date)}.` : "No upcoming collections booked."}
        </p>
      )}
      {rows?.length > 0 && (
        <p className="muted small">
          {rows.length} collection{rows.length === 1 ? "" : "s"} {date ? `on ${formatDate(date)}` : "upcoming"}
        </p>
      )}

      {rows?.length > 0 && (
        <div className="card table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Window</th>
                <th>Reference</th>
                <th>Resident</th>
                <th>Address</th>
                <th>Waste</th>
                <th>Instructions</th>
                <th>Status</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rows.map((b) => (
                <tr key={b.booking_reference}>
                  <td className="nowrap">{formatShortDate(b.confirmed_collection.date)}</td>
                  <td className="nowrap">{formatWindow(b.confirmed_collection.start_time, b.confirmed_collection.end_time)}</td>
                  <td>
                    <code>{b.booking_reference}</code>
                  </td>
                  <td>
                    {b.resident.name}
                    <div className="muted small">
                      {b.resident.username} · ID {b.resident.user_id}
                    </div>
                    <div className="muted small">{b.resident.phone}</div>
                  </td>
                  <td>
                    {b.collection_address.address_line}, {b.collection_address.suburb}{" "}
                    {b.collection_address.postcode}
                  </td>
                  <td>
                    {b.waste_type.name}
                    <div className="muted small">{quantityLabel(b.estimated_quantity)}</div>
                  </td>
                  <td className="small">{b.special_instructions || "—"}</td>
                  <td>
                    <StatusBadge status={b.booking_status} />
                  </td>
                  <td className="nowrap">
                    <button
                      className="btn btn-small btn-primary"
                      disabled={busyRef === b.booking_reference}
                      onClick={() => report(b.booking_reference, "completed")}
                    >
                      Collected
                    </button>{" "}
                    <button
                      className="btn btn-small btn-danger-outline"
                      disabled={busyRef === b.booking_reference}
                      onClick={() => report(b.booking_reference, "missed")}
                    >
                      Missed
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
