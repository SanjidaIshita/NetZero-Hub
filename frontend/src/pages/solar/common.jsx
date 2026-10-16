import "./solar.css";
// Small helpers shared by the solar installation pages (ORG-001).

const LABELS = {
  CONFIRMED: "Assessment booked",
  ASSESSED: "Site assessed",
  COMPLETED: "Installed",
  CANCELLED: "Cancelled",
};

const TONES = {
  CONFIRMED: "badge-confirmed",
  ASSESSED: "badge-pending",
  COMPLETED: "badge-collected",
  CANCELLED: "badge-cancelled",
};

export function SolarStatus({ status }) {
  return <span className={`badge ${TONES[status] || ""}`}>{LABELS[status] || status}</span>;
}

export function statusLabel(status) {
  return LABELS[status] || status;
}

/** Whole-dollar Australian currency, e.g. $15,429 */
export function aud(amount) {
  return Number(amount).toLocaleString("en-AU", { style: "currency", currency: "AUD", maximumFractionDigits: 0 });
}
