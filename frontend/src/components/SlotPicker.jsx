import { useEffect, useMemo, useState } from "react";
import { formatDate, formatWindow, parseDate } from "../format.js";

/** Pick a collection slot: a row of dates, then the time windows for that date. */
export default function SlotPicker({ slots, value, onChange }) {
  const byDate = useMemo(() => {
    const groups = new Map();
    for (const slot of slots) {
      if (!groups.has(slot.date)) groups.set(slot.date, []);
      groups.get(slot.date).push(slot);
    }
    return groups;
  }, [slots]);

  const dates = [...byDate.keys()];
  const selectedSlot = slots.find((s) => s.id === value);
  const [activeDate, setActiveDate] = useState(selectedSlot?.date || dates[0]);

  useEffect(() => {
    if (!byDate.has(activeDate)) setActiveDate(dates[0]);
  }, [byDate, activeDate, dates]);

  if (!slots.length) {
    return <p className="notice">No collection slots are available in the next few weeks. Please check back soon.</p>;
  }

  return (
    <div className="slot-picker">
      <div className="date-strip" role="group" aria-label="Collection date">
        {dates.map((iso) => {
          const d = parseDate(iso);
          return (
            <button
              type="button"
              key={iso}
              aria-label={formatDate(iso)}
              aria-pressed={iso === activeDate}
              className={`date-chip ${iso === activeDate ? "is-active" : ""} ${
                selectedSlot?.date === iso ? "has-selection" : ""
              }`}
              onClick={() => setActiveDate(iso)}
            >
              <span className="date-chip-dow">{d.toLocaleDateString("en-AU", { weekday: "short" })}</span>
              <span className="date-chip-day">{d.getDate()}</span>
              <span className="date-chip-mon">{d.toLocaleDateString("en-AU", { month: "short" })}</span>
            </button>
          );
        })}
      </div>

      {activeDate && (
        <fieldset className="windows">
          <legend>{formatDate(activeDate)}</legend>
          {byDate.get(activeDate)?.map((slot) => (
            <label key={slot.id} className={`window ${value === slot.id ? "is-selected" : ""}`}>
              <input
                type="radio"
                name="slot"
                checked={value === slot.id}
                onChange={() => onChange(slot.id)}
              />
              <span className="window-time">{formatWindow(slot.start_time, slot.end_time)}</span>
              <span className="window-left">
                {slot.remaining <= 5 ? `Only ${slot.remaining} left` : `${slot.remaining} available`}
              </span>
            </label>
          ))}
        </fieldset>
      )}
    </div>
  );
}
