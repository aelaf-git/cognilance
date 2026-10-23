import type { Metadata } from "next";
import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";
import { EMAIL, OFFICE_LOCALITY, OFFICE_NAME, OFFICE_STREET } from "@/lib/site";

export const metadata: Metadata = {
  title: {
    absolute: "Privacy Policy · Cognilance",
  },
  description:
    "How Cognilance collects, uses, shares, and protects personal data on cognilanceai.com.",
};

export default function PrivacyPage() {
  return (
    <LegalPage
      eyebrow="Legal"
      title="Privacy policy"
      lead="This Privacy Policy explains how Cognilance collects, uses, discloses, and protects personal data when you use cognilanceai.com and related marketing pages (the “Site”). It also describes your privacy rights and how to exercise them."
    >
      <p>
        <strong>Effective date:</strong> October 23, 2026
      </p>
      <p>
        Cognilance is building an AI team assistant for individuals and groups.
        Today the Site is primarily a marketing and early-access experience
        (waitlist, product information, and contact). When we launch accounts,
        shared agents, or other product features that process new categories of
        data, we will update this Privacy Policy before those features go live.
      </p>
      <p>
        This document is written to match how the Site works today. It is not a
        substitute for advice from your own counsel. If you have questions, see
        Section 9 (“Contact”).
      </p>

      <h2>1. Collection of personal data</h2>
      <p>We collect the following categories of personal data.</p>

      <h3>Personal data you provide to us directly</h3>
      <ul>
        <li>
          <strong>Waitlist data.</strong> When you join the waitlist, we collect
          your name, email address, whether you are joining as an individual or
          a team or company, your role, and, if you choose to provide them,
          company or team name, a short note about how you plan to use
          Cognilance, and where you heard about us.
        </li>
        <li>
          <strong>Contact data.</strong> When you use the contact form, we
          collect your name, email address, optional company name, and the
          contents of your message.
        </li>
        <li>
          <strong>Other communications.</strong> If you email us or otherwise
          contact us, we collect the contact details and message content you
          send.
        </li>
      </ul>

      <h3>Personal data we receive automatically</h3>
      <ul>
        <li>
          <strong>Technical and log information.</strong> When you visit the
          Site, our hosting and infrastructure providers may automatically
          receive information such as IP address, browser type, device type,
          operating system, referring URL, pages requested, and timestamps.
          We use this for security, reliability, and to operate the Site.
        </li>
        <li>
          <strong>Cookies and similar technologies.</strong> The Site does not
          currently set its own analytics or advertising cookies. Third-party
          embeds (for example the Google Maps embed on the Contact page) may
          set cookies or use similar technologies when you load that content.
          See our <Link href="/cookies">Cookies</Link> notice for more detail.
        </li>
      </ul>

      <h3>What we do not collect on the Site today</h3>
      <p>
        The marketing Site does not currently collect product conversation
        history, agent task logs, payment card data, or account credentials.
        We do not use Site waitlist or contact data to train AI models.
      </p>

      <h2>2. How we use personal data</h2>
      <p>We use personal data to:</p>
      <ul>
        <li>
          Operate the Site and provide the waitlist and contact features you
          request
        </li>
        <li>
          Invite you to early access, prioritize access, and communicate about
          Cognilance product updates related to the waitlist
        </li>
        <li>Respond to your messages and support requests</li>
        <li>
          Maintain security, prevent abuse and spam, debug issues, and protect
          Cognilance, our users, and the public
        </li>
        <li>Comply with law and enforce our terms and policies</li>
        <li>
          Improve the Site in aggregate (for example understanding which pages
          are visited), without selling your personal data
        </li>
      </ul>

      <h2>3. Recipients and service providers</h2>
      <p>
        We do not sell your personal data. We share personal data with service
        providers who process it on our behalf to run the Site, including:
      </p>
      <ul>
        <li>
          <strong>Database hosting.</strong> MongoDB Atlas stores waitlist and
          contact records.
        </li>
        <li>
          <strong>Email delivery.</strong> Resend may send a copy of contact
          form submissions to our team when that service is configured.
        </li>
        <li>
          <strong>Maps.</strong> Google provides the map embed on the Contact
          page. Interaction with that embed is also subject to Google’s own
          terms and privacy policy.
        </li>
        <li>
          <strong>Hosting and infrastructure.</strong> Providers that host,
          deliver, or secure the Site may process technical logs as described
          above.
        </li>
      </ul>
      <p>
        We may also disclose personal data if required by law, legal process, or
        government request; to protect rights, safety, and security; or in
        connection with a merger, acquisition, financing, or sale of assets,
        subject to appropriate safeguards.
      </p>

      <h2>4. Rights and choices</h2>
      <p>
        Depending on where you live, you may have rights to access, correct,
        update, or delete personal data we hold about you; to object to or
        restrict certain processing; and to withdraw consent where processing is
        based on consent (for example withdrawing from the waitlist).
      </p>
      <p>
        To exercise these rights, email us at{" "}
        <a href={`mailto:${EMAIL}`}>{EMAIL}</a> with the subject line “Privacy
        request” and enough detail for us to locate your records (usually the
        email address you used). We may need to verify your identity before
        fulfilling a request.
      </p>
      <p>
        You can also stop waitlist emails by contacting us with the same
        address. If you no longer want to be on the waitlist, ask us to delete
        or suppress your waitlist record.
      </p>

      <h2>5. International transfers</h2>
      <p>
        Cognilance is based in Ethiopia. Some service providers (including
        MongoDB Atlas, Resend, and Google) may process data in the United
        States or other countries. Those countries may have different data
        protection laws than your own. Where we transfer personal data, we rely
        on appropriate safeguards offered by our providers and applicable law.
      </p>

      <h2>6. Retention and security</h2>
      <p>
        We keep waitlist and contact records for as long as needed to operate
        early access, respond to you, and meet legal, security, and business
        record needs. We review retention periodically and delete or anonymize
        data when it is no longer needed for those purposes.
      </p>
      <p>
        We use administrative, technical, and organizational measures designed
        to protect personal data, including access controls and encrypted
        connections where provided by our vendors. No method of transmission or
        storage is completely secure. Please use a strong unique password for
        your email account and notify us promptly of any suspected unauthorized
        access related to Cognilance.
      </p>

      <h2>7. Children</h2>
      <p>
        The Site is not directed to children under 16, and we do not knowingly
        collect personal data from children under 16. If you believe a child
        has provided personal data to us, contact us and we will take steps to
        delete it.
      </p>

      <h2>8. Changes to this Privacy Policy</h2>
      <p>
        We may update this Privacy Policy from time to time. When we do, we will
        change the effective date at the top of this page and, where appropriate,
        provide additional notice on the Site. Continued use of the Site after
        an update means you acknowledge the revised policy.
      </p>

      <h2>9. Contact</h2>
      <p>
        For privacy questions or requests, contact Cognilance at{" "}
        <a href={`mailto:${EMAIL}`}>{EMAIL}</a>.
      </p>
      <p>
        Postal / office context: {OFFICE_NAME}, {OFFICE_STREET},{" "}
        {OFFICE_LOCALITY}.
      </p>

      <h2>10. Legal bases for processing</h2>
      <p>
        If you are in a jurisdiction that requires a legal basis for processing
        (for example the EEA, UK, or Switzerland), we rely on:
      </p>
      <ul>
        <li>
          <strong>Consent</strong>, when you submit the waitlist or contact form
          or otherwise ask us to process data for a stated purpose
        </li>
        <li>
          <strong>Legitimate interests</strong>, such as securing and operating
          the Site, preventing abuse, and improving our early-access program in
          ways that do not override your rights
        </li>
        <li>
          <strong>Legal obligation</strong>, when we must process or retain data
          to comply with applicable law
        </li>
      </ul>
      <p>
        Where we rely on consent, you may withdraw it as described in Section 4,
        without affecting the lawfulness of processing before withdrawal.
      </p>
    </LegalPage>
  );
}
