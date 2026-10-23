import type { Metadata } from "next";
import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: {
    absolute: "Cookies · Cognilance",
  },
  description:
    "How cognilanceai.com uses cookies and similar technologies.",
};

export default function CookiesPage() {
  return (
    <LegalPage
      eyebrow="Legal"
      title="Cookies"
      lead="This notice explains how cognilanceai.com uses cookies and similar technologies, and how that relates to our Privacy Policy."
    >
      <p>
        <strong>Effective date:</strong> October 23, 2026
      </p>

      <h2>First-party cookies</h2>
      <p>
        The marketing Site does not currently set its own analytics or
        advertising cookies. Essential cookies may be used by our hosting
        platform only as needed to deliver the Site securely.
      </p>

      <h2>Third-party cookies and embeds</h2>
      <p>
        Some pages load content from third parties. In particular, the Contact
        page embeds a Google Map. When that embed loads, Google may set cookies
        or use similar technologies according to Google’s policies. We do not
        control those cookies.
      </p>

      <h2>Waitlist and contact forms</h2>
      <p>
        Waitlist and contact submissions are sent to our own APIs and stored in
        our database. Those forms do not use a third-party waitlist widget that
        sets additional marketing cookies on our behalf.
      </p>

      <h2>Changes</h2>
      <p>
        If we add analytics, session, or advertising cookies, we will update
        this notice before they go live and, where required, seek consent.
      </p>

      <h2>More information</h2>
      <p>
        For how we collect and use personal data more broadly, see our{" "}
        <Link href="/privacy">Privacy Policy</Link>.
      </p>
    </LegalPage>
  );
}
