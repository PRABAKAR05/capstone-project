import { notFound } from "next/navigation";

/**
 * AC-15.7c: /portal/caregivers route decommissioning
 * Server renders RFC 7807 HTTP 404 boundary.
 */
export default function DecommissionedPortalCaregiversPage() {
  notFound();
}
