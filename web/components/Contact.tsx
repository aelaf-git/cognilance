import { ContactForm } from "./ContactForm";
import { Reveal } from "./Reveal";
import {
  EMAIL,
  OFFICE_LANDMARK,
  OFFICE_LOCALITY,
  OFFICE_MAP_EMBED,
  OFFICE_NAME,
  OFFICE_STREET,
  PHONE,
  PHONE_TEL,
} from "@/lib/site";
import styles from "./Contact.module.css";

export function Contact() {
  return (
    <section className={`section sectionLight ${styles.wrap}`} id="contact">
      <div className="container">
        <Reveal>
          <div className={styles.header}>
            <p className="eyebrow">Contact</p>
            <h2>Contact us</h2>
            <p className="lead">
              Visit us at the AI Startup Center, or send a message and we will
              get back to you.
            </p>
          </div>
        </Reveal>

        <Reveal delayMs={60}>
          <dl className={styles.meta}>
            <div>
              <dt>Address</dt>
              <dd>
                <strong>{OFFICE_NAME}</strong>
                <span>
                  {OFFICE_STREET}, {OFFICE_LOCALITY}
                </span>
                <span className={styles.landmark}>{OFFICE_LANDMARK}</span>
              </dd>
            </div>
            <div>
              <dt>Phone</dt>
              <dd>
                <a href={`tel:${PHONE_TEL}`}>{PHONE}</a>
              </dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>
                <a href={`mailto:${EMAIL}`}>{EMAIL}</a>
              </dd>
            </div>
          </dl>
        </Reveal>

        <div className={styles.panels}>
          <Reveal delayMs={100}>
            <div className={styles.formPanel}>
              <h3 className={styles.formTitle}>Send a message</h3>
              <ContactForm />
            </div>
          </Reveal>

          <Reveal delayMs={140}>
            <div className={styles.mapFrame}>
              <iframe
                title="Office location map"
                src={OFFICE_MAP_EMBED}
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                allowFullScreen
              />
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
