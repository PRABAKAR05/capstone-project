import { notFound } from "next/navigation";

/**
 * AC-15.7b: /receptionist/verify-caregivers route decommissioning
 * Server renders RFC 7807 HTTP 404 boundary.
 */
export default function DecommissionedVerifyCaregiversPage() {
  notFound();
}
