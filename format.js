// Parse "YYYY-MM-DD" as a local date (avoids UTC off-by-one).
export function parseDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatDate(iso, opts = { weekday: "long", day: "numeric", month: "long", year: "numeric" }) {
  if (!iso) return "";
  return parseDate(iso).toLocaleDateString("en-AU", opts);
}

export function formatShortDate(iso) {
  return formatDate(iso, { weekday: "short", day: "numeric", month: "short" });
}

export function formatTime(hhmm) {
  if (!hhmm) return "";
  const [h, m] = hhmm.split(":").map(Number);
  const suffix = h >= 12 ? "pm" : "am";
  const hour = h % 12 || 12;
  return m ? `${hour}:${String(m).padStart(2, "0")}${suffix}` : `${hour}${suffix}`;
}

export function formatWindow(start, end) {
  return `${formatTime(start)} – ${formatTime(end)}`;
}

export function formatDateTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-AU", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function money(amount) {
  return `$${Number(amount).toFixed(2)}`;
}

export const QUANTITIES = [
  { value: "SMALL", label: "Small", hint: "1–2 bags or boxes" },
  { value: "MEDIUM", label: "Medium", hint: "3–5 bags or boxes" },
  { value: "LARGE", label: "Large / bulky", hint: "Whitegoods, furniture · surcharge applies" },
];

export function quantityLabel(value) {
  const q = QUANTITIES.find((x) => x.value === value);
  return q ? `${q.label} (${q.hint.split(" ·")[0]})` : value;
}
