// Small helpers shared by the solar installation pages (ORG-001).

const LABELS = {
  CONFIRMED: "Assessment booked",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export function SolarStatus({ status }) {
  const tone = { CONFIRMED: "badge-confirmed", COMPLETED: "badge-collected", CANCELLED: "badge-cancelled" }[status];
  return <span className={`badge ${tone || ""}`}>{LABELS[status] || status}</span>;
}

/** Whole-dollar Australian currency, e.g. $15,429 */
export function aud(amount) {
  return Number(amount).toLocaleString("en-AU", { style: "currency", currency: "AUD", maximumFractionDigits: 0 });
}
