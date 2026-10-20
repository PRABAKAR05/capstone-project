/**
 * CareBridge AI - Timezone Formatting Utility
 * Default hospital timezone: Asia/Kolkata
 */

export const DEFAULT_HOSPITAL_TIMEZONE = "Asia/Kolkata";

export function formatInHospitalTimezone(
  isoString: string,
  timezone: string = DEFAULT_HOSPITAL_TIMEZONE
): { dateStr: string; timeStr: string; fullStr: string } {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) {
      return { dateStr: "Invalid Date", timeStr: "", fullStr: "Invalid Date" };
    }

    const dateStr = d.toLocaleDateString("en-IN", {
      timeZone: timezone,
      year: "numeric",
      month: "short",
      day: "numeric",
    });

    const timeStr = d.toLocaleTimeString("en-IN", {
      timeZone: timezone,
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });

    return {
      dateStr,
      timeStr,
      fullStr: `${dateStr} at ${timeStr} (${timezone.split("/")[1] || timezone})`,
    };
  } catch {
    return { dateStr: isoString, timeStr: "", fullStr: isoString };
  }
}

export function getTodayDateString(timezone: string = DEFAULT_HOSPITAL_TIMEZONE): string {
  try {
    const now = new Date();
    const formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    return formatter.format(now);
  } catch {
    return new Date().toISOString().split("T")[0];
  }
}
