"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./Solution.module.css";

type Phase = "closeup" | "fleet" | "gather" | "deliver";

/** Close-up light-beam timeline (unchanged behavior) */
type CloseBeat =
  | "idle"
  | "beamHire"
  | "workersLoad"
  | "workersDone"
  | "beamVal"
  | "valsLoad"
  | "valsDone"
  | "beamUser"
  | "userLit";

/**
 * Wide view: one orchestrator emit, then light only moves down.
 * Upper rows freeze once done — they never reload.
 */
type WideBeat =
  | "idle"
  | "orchBeam"
  | "fleetLoad"
  | "fleetDone"
  | "fleetValBeam"
  | "fleetValLoad"
  | "fleetValDone"
  | "gatherBeam"
  | "gatherLoad"
  | "gatherDone"
  | "gatherValBeam"
  | "gatherValLoad"
  | "gatherValDone"
  | "userBeam"
  | "userLit";

type Status = "idle" | "loading" | "done";

const FLEET = Array.from({ length: 6 }, (_, i) => i + 1);
const GATHER = ["E", "F", "G", "H"];

function ArrowDown({ lit = false, beam = false }: { lit?: boolean; beam?: boolean }) {
  return (
    <div
      className={`${styles.beamTrack} ${lit ? styles.beamTrackLit : ""} ${beam ? styles.beamTrackActive : ""}`}
    >
      <svg className={styles.arrow} viewBox="0 0 24 36" aria-hidden="true">
        <path d="M12 2v26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path
          d="M6 22l6 10 6-10"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className={styles.beam} aria-hidden="true" />
    </div>
  );
}

function StatusIcon({ state }: { state: Status }) {
  if (state === "idle") return null;
  if (state === "loading") {
    return (
      <span className={styles.status} aria-hidden="true">
        <span className={styles.spinner} />
      </span>
    );
  }
  return (
    <span className={`${styles.status} ${styles.statusDone}`} aria-hidden="true">
      <svg viewBox="0 0 16 16" className={styles.tick}>
        <path
          d="M3.5 8.5l3 3 6-7"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

const TONE = {
  orch: styles.tone_orch,
  agent: styles.tone_agent,
  validator: styles.tone_validator,
  gather: styles.tone_gather,
  user: styles.tone_user,
} as const;

function Node({
  title,
  sub,
  tone = "agent",
  compact = false,
  lit = false,
  status = "idle",
}: {
  title: string;
  sub: string;
  tone?: keyof typeof TONE;
  compact?: boolean;
  lit?: boolean;
  status?: Status;
}) {
  return (
    <div
      className={[
        styles.box,
        TONE[tone],
        compact ? styles.boxCompact : "",
        lit ? styles.boxLit : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span className={styles.boxAccent} aria-hidden="true" />
      <div className={styles.boxBody}>
        <span className={styles.boxTitle}>{title}</span>
        <span className={styles.boxSub}>{sub}</span>
      </div>
      <StatusIcon state={status} />
    </div>
  );
}

function MergeBeam({ active = false, lit = false }: { active?: boolean; lit?: boolean }) {
  return (
    <div
      className={`${styles.mergeWrap} ${lit ? styles.beamTrackLit : ""} ${active ? styles.beamTrackActive : ""}`}
    >
      <svg className={styles.mergeArrowsClose} viewBox="0 0 400 56" aria-hidden="true">
        <path d="M80 6 C80 30, 200 30, 200 42" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M320 6 C320 30, 200 30, 200 42" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M194 36l6 12 6-12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className={styles.beamMerge} aria-hidden="true" />
    </div>
  );
}

/* ---- Close-up helpers (keep existing feel) ---- */

function closeStatus(beat: CloseBeat, role: "worker" | "validator" | "user"): Status {
  if (role === "worker") {
    if (beat === "workersLoad") return "loading";
    if (
      beat === "workersDone" ||
      beat === "beamVal" ||
      beat === "valsLoad" ||
      beat === "valsDone" ||
      beat === "beamUser" ||
      beat === "userLit"
    )
      return "done";
  }
  if (role === "validator") {
    if (beat === "valsLoad") return "loading";
    if (beat === "valsDone" || beat === "beamUser" || beat === "userLit") return "done";
  }
  if (role === "user" && beat === "userLit") return "done";
  return "idle";
}

function closeLit(beat: CloseBeat, role: "orch" | "worker" | "validator" | "user"): boolean {
  if (role === "orch") return beat === "idle" || beat === "beamHire";
  if (role === "worker") {
    return (
      beat === "beamHire" ||
      beat === "workersLoad" ||
      beat === "workersDone" ||
      beat === "beamVal" ||
      beat === "valsLoad" ||
      beat === "valsDone" ||
      beat === "beamUser" ||
      beat === "userLit"
    );
  }
  if (role === "validator") {
    return (
      beat === "beamVal" ||
      beat === "valsLoad" ||
      beat === "valsDone" ||
      beat === "beamUser" ||
      beat === "userLit"
    );
  }
  if (role === "user") return beat === "beamUser" || beat === "userLit";
  return false;
}

/* ---- Wide helpers: upper rows freeze once done ---- */

const AFTER_FLEET_DONE: WideBeat[] = [
  "fleetDone",
  "fleetValBeam",
  "fleetValLoad",
  "fleetValDone",
  "gatherBeam",
  "gatherLoad",
  "gatherDone",
  "gatherValBeam",
  "gatherValLoad",
  "gatherValDone",
  "userBeam",
  "userLit",
];

const AFTER_FLEET_VAL_DONE: WideBeat[] = [
  "fleetValDone",
  "gatherBeam",
  "gatherLoad",
  "gatherDone",
  "gatherValBeam",
  "gatherValLoad",
  "gatherValDone",
  "userBeam",
  "userLit",
];

const AFTER_GATHER_DONE: WideBeat[] = [
  "gatherDone",
  "gatherValBeam",
  "gatherValLoad",
  "gatherValDone",
  "userBeam",
  "userLit",
];

const AFTER_GATHER_VAL_DONE: WideBeat[] = [
  "gatherValDone",
  "userBeam",
  "userLit",
];

function wideStatus(
  beat: WideBeat,
  role: "fleet" | "fleetVal" | "gather" | "gatherVal" | "user",
): Status {
  if (role === "fleet") {
    if (beat === "fleetLoad") return "loading";
    if (AFTER_FLEET_DONE.includes(beat)) return "done";
  }
  if (role === "fleetVal") {
    if (beat === "fleetValLoad") return "loading";
    if (AFTER_FLEET_VAL_DONE.includes(beat)) return "done";
  }
  if (role === "gather") {
    if (beat === "gatherLoad") return "loading";
    if (AFTER_GATHER_DONE.includes(beat)) return "done";
  }
  if (role === "gatherVal") {
    if (beat === "gatherValLoad") return "loading";
    if (AFTER_GATHER_VAL_DONE.includes(beat)) return "done";
  }
  if (role === "user" && beat === "userLit") return "done";
  return "idle";
}

function wideLit(
  beat: WideBeat,
  role: "orch" | "fleet" | "fleetVal" | "gather" | "gatherVal" | "user",
): boolean {
  if (role === "orch") return beat === "orchBeam";
  if (role === "fleet") {
    return beat === "orchBeam" || beat === "fleetLoad" || AFTER_FLEET_DONE.includes(beat);
  }
  if (role === "fleetVal") {
    return (
      beat === "fleetValBeam" ||
      beat === "fleetValLoad" ||
      AFTER_FLEET_VAL_DONE.includes(beat)
    );
  }
  if (role === "gather") {
    return beat === "gatherBeam" || beat === "gatherLoad" || AFTER_GATHER_DONE.includes(beat);
  }
  if (role === "gatherVal") {
    return (
      beat === "gatherValBeam" ||
      beat === "gatherValLoad" ||
      AFTER_GATHER_VAL_DONE.includes(beat)
    );
  }
  if (role === "user") return beat === "userBeam" || beat === "userLit";
  return false;
}

export function OrchestrationDiagram() {
  const [phase, setPhase] = useState<Phase>("closeup");
  const [closeBeat, setCloseBeat] = useState<CloseBeat>("idle");
  const [wideBeat, setWideBeat] = useState<WideBeat>("idle");
  const timersRef = useRef<number[]>([]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");

    const clearTimers = () => {
      timersRef.current.forEach((id) => window.clearTimeout(id));
      timersRef.current = [];
    };

    const later = (fn: () => void, ms: number) => {
      timersRef.current.push(window.setTimeout(fn, ms));
    };

    if (mq.matches) {
      setPhase("deliver");
      setCloseBeat("userLit");
      setWideBeat("userLit");
      return;
    }

    let cancelled = false;

    const run = () => {
      if (cancelled) return;
      clearTimers();
      setPhase("closeup");
      setCloseBeat("idle");
      setWideBeat("idle");

      // Close-up (unchanged)
      const closeSteps: Array<[CloseBeat, number]> = [
        ["beamHire", 0],
        ["workersLoad", 450],
        ["workersDone", 1100],
        ["beamVal", 1450],
        ["valsLoad", 1850],
        ["valsDone", 2500],
        ["beamUser", 2850],
        ["userLit", 3300],
      ];
      closeSteps.forEach(([b, t]) => {
        later(() => {
          if (!cancelled) setCloseBeat(b);
        }, t);
      });

      // Wide view — orchestrator emits once, then light only descends
      later(() => {
        if (cancelled) return;
        setPhase("fleet");
        setWideBeat("idle");
      }, 4000);

      const wideSteps: Array<[WideBeat, number, Phase?]> = [
        ["orchBeam", 4200],
        ["fleetLoad", 4600],
        ["fleetDone", 5200],
        ["fleetValBeam", 5550], // no new orch light
        ["fleetValLoad", 5900],
        ["fleetValDone", 6500],
        ["gatherBeam", 6900, "gather"], // beam from fleet vals → gather
        ["gatherLoad", 7300],
        ["gatherDone", 7900],
        ["gatherValBeam", 8250],
        ["gatherValLoad", 8600],
        ["gatherValDone", 9200],
        ["userBeam", 9600, "deliver"],
        ["userLit", 10000],
      ];

      wideSteps.forEach(([b, t, nextPhase]) => {
        later(() => {
          if (cancelled) return;
          if (nextPhase) setPhase(nextPhase);
          setWideBeat(b);
        }, t);
      });

      later(() => {
        if (!cancelled) run();
      }, 11500);
    };

    run();

    const onMotion = () => {
      if (mq.matches) {
        cancelled = true;
        clearTimers();
        setPhase("deliver");
        setWideBeat("userLit");
      }
    };
    mq.addEventListener("change", onMotion);

    return () => {
      cancelled = true;
      clearTimers();
      mq.removeEventListener("change", onMotion);
    };
  }, []);

  const isClose = phase === "closeup";

  // Close-up bindings
  const cWorker = closeStatus(closeBeat, "worker");
  const cVal = closeStatus(closeBeat, "validator");
  const cUser = closeStatus(closeBeat, "user");

  // Wide bindings — independent layers
  const wFleet = wideStatus(wideBeat, "fleet");
  const wFleetVal = wideStatus(wideBeat, "fleetVal");
  const wGather = wideStatus(wideBeat, "gather");
  const wGatherVal = wideStatus(wideBeat, "gatherVal");
  const wUser = wideStatus(wideBeat, "user");

  const orchLit = isClose ? closeLit(closeBeat, "orch") : wideLit(wideBeat, "orch");
  const orchBeam = isClose ? closeBeat === "beamHire" : wideBeat === "orchBeam";
  const orchArrowLit = isClose ? closeBeat !== "idle" : wideBeat !== "idle";

  return (
    <figure
      className={styles.diagram}
      data-phase={phase}
      data-beat={isClose ? closeBeat : wideBeat}
      aria-label="Light beam flowing from orchestrator through agents and validators to the user"
    >
      <div className={styles.stage}>
        <div className={styles.flow}>
          <Node title="Orchestrator" sub="Plans & hires" tone="orch" lit={orchLit} />

          <ArrowDown lit={orchArrowLit} beam={orchBeam} />

          <div className={styles.registry}>
            <header className={styles.registryHead}>
              <span className={styles.registryLabel}>Registry</span>
            </header>

            <div className={styles.registryBody}>
              <div className={styles.closeup} aria-hidden={!isClose}>
                <div className={styles.lane}>
                  <Node
                    title="Agent A"
                    sub="Worker"
                    tone="agent"
                    lit={closeLit(closeBeat, "worker")}
                    status={cWorker}
                  />
                  <ArrowDown
                    lit={["beamVal", "valsLoad", "valsDone", "beamUser", "userLit"].includes(closeBeat)}
                    beam={closeBeat === "beamVal"}
                  />
                  <Node
                    title="Agent C"
                    sub="Validator"
                    tone="validator"
                    lit={closeLit(closeBeat, "validator")}
                    status={cVal}
                  />
                </div>

                <div className={styles.lane}>
                  <Node
                    title="Agent B"
                    sub="Worker"
                    tone="agent"
                    lit={closeLit(closeBeat, "worker")}
                    status={cWorker}
                  />
                  <ArrowDown
                    lit={["beamVal", "valsLoad", "valsDone", "beamUser", "userLit"].includes(closeBeat)}
                    beam={closeBeat === "beamVal"}
                  />
                  <Node
                    title="Agent D"
                    sub="Validator"
                    tone="validator"
                    lit={closeLit(closeBeat, "validator")}
                    status={cVal}
                  />
                </div>
              </div>

              <div className={styles.wideStack} aria-hidden={isClose}>
                <div className={styles.fleetScroll}>
                  <div className={styles.fleet}>
                    {FLEET.map((n) => (
                      <div key={n} className={styles.fleetPair} style={{ ["--i" as string]: n }}>
                        <Node
                          title={`A${n}`}
                          sub="Worker"
                          tone="agent"
                          compact
                          lit={wideLit(wideBeat, "fleet")}
                          status={wFleet}
                        />
                        <ArrowDown
                          lit={
                            wideBeat === "fleetValBeam" ||
                            wideBeat === "fleetValLoad" ||
                            AFTER_FLEET_VAL_DONE.includes(wideBeat)
                          }
                          beam={wideBeat === "fleetValBeam"}
                        />
                        <Node
                          title={`V${n}`}
                          sub="Validator"
                          tone="validator"
                          compact
                          lit={wideLit(wideBeat, "fleetVal")}
                          status={wFleetVal}
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <div className={styles.gatherBlock}>
                  <ArrowDown
                    lit={
                      wideBeat === "gatherBeam" ||
                      wideBeat === "gatherLoad" ||
                      AFTER_GATHER_DONE.includes(wideBeat)
                    }
                    beam={wideBeat === "gatherBeam"}
                  />
                  <div className={styles.gatherRow}>
                    {GATHER.map((id, i) => (
                      <div key={id} className={styles.gatherPair} style={{ ["--i" as string]: i }}>
                        <Node
                          title={`Agent ${id}`}
                          sub="Process"
                          tone="gather"
                          compact
                          lit={wideLit(wideBeat, "gather")}
                          status={wGather}
                        />
                        <ArrowDown
                          lit={
                            wideBeat === "gatherValBeam" ||
                            wideBeat === "gatherValLoad" ||
                            AFTER_GATHER_VAL_DONE.includes(wideBeat)
                          }
                          beam={wideBeat === "gatherValBeam"}
                        />
                        <Node
                          title={`Val ${id}`}
                          sub="Validate"
                          tone="validator"
                          compact
                          lit={wideLit(wideBeat, "gatherVal")}
                          status={wGatherVal}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className={styles.outroStack}>
            <div className={styles.closeupOutro} aria-hidden={!isClose}>
              <MergeBeam
                active={closeBeat === "beamUser"}
                lit={closeBeat === "beamUser" || closeBeat === "userLit"}
              />
              <Node
                title="User"
                sub="Combined result"
                tone="user"
                lit={closeLit(closeBeat, "user")}
                status={cUser}
              />
            </div>

            <div className={styles.deliverOutro} aria-hidden={isClose}>
              <div
                className={`${styles.mergeWrap} ${
                  wideBeat === "userBeam" || wideBeat === "userLit" ? styles.beamTrackLit : ""
                } ${wideBeat === "userBeam" ? styles.beamTrackActive : ""}`}
              >
                <svg className={styles.mergeArrows} viewBox="0 0 400 56" aria-hidden="true">
                  <path d="M50 6 C50 30, 200 30, 200 42" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <path d="M150 6 C150 30, 200 30, 200 42" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <path d="M250 6 C250 30, 200 30, 200 42" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <path d="M350 6 C350 30, 200 30, 200 42" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <path d="M194 36l6 12 6-12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span className={styles.beamMerge} aria-hidden="true" />
              </div>
              <Node
                title="User"
                sub="Combined result"
                tone="user"
                lit={wideLit(wideBeat, "user")}
                status={wUser}
              />
            </div>
          </div>
        </div>
      </div>
    </figure>
  );
}
