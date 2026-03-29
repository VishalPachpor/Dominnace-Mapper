const IST_TIMEZONE = "Asia/Kolkata";

type DateLike = string | number | Date | null | undefined;

function toDate(value: DateLike): Date | null {
  if (value == null) return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatIstDate(value: DateLike): string {
  const d = toDate(value);
  if (!d) return "—";
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: IST_TIMEZONE,
  });
}

export function formatIstTime(value: DateLike): string {
  const d = toDate(value);
  if (!d) return "—";
  return d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: IST_TIMEZONE,
  });
}

export function formatIstDateTime(value: DateLike): string {
  const d = toDate(value);
  if (!d) return "—";
  return `${formatIstDate(d)} • ${formatIstTime(d)}`;
}

