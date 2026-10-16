const LABELS = {
  PENDING: "Pending",
  CONFIRMED: "Confirmed",
  RESCHEDULED: "Rescheduled",
  COLLECTED: "Collected",
  MISSED: "Missed",
  CANCELLED: "Cancelled",
  REJECTED: "Rejected",
};

export default function StatusBadge({ status }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{LABELS[status] || status}</span>;
}
