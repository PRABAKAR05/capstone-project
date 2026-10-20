import { notFound } from "next/navigation";

/**
 * AC-15.7a: /receptionist route decommissioning
 * Server renders RFC 7807 HTTP 404 boundary.
 */
export default function DecommissionedReceptionistPage() {
  notFound();
}
