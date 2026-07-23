"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import * as THREE from "three";

const EMBER = "#fd8925";
const EMBER_HOT = "#ff492c";
const EMBER_SOFT = "#ff8e5d";

let tex0: THREE.CanvasTexture | null = null;
let tex1: THREE.CanvasTexture | null = null;

function digitTexture(digit: "0" | "1") {
  if (digit === "0" && tex0) return tex0;
  if (digit === "1" && tex1) return tex1;

  const size = 48;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, size, size);
  ctx.font = "700 36px ui-monospace, Menlo, monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = digit === "0" ? EMBER_SOFT : EMBER;
  ctx.fillText(digit, size / 2, size / 2 + 1);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.generateMipmaps = false;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  if (digit === "0") tex0 = texture;
  else tex1 = texture;
  return texture;
}

type Bit = {
  theta: number;
  phi: number;
  speed: number;
  axis: 0 | 1;
  phase: number;
  digit: 0 | 1;
};

function fibSphere(count: number) {
  const out: { theta: number; phi: number }[] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / Math.max(count - 1, 1)) * 2;
    const phi = Math.acos(THREE.MathUtils.clamp(y, -1, 1));
    const theta = golden * i;
    out.push({ theta, phi });
  }
  return out;
}

const BASE_R = 1.15;

/** Mild bubble radius: mostly solid, slight organic flex. */
function bubbleRadius(
  ux: number,
  uy: number,
  uz: number,
  t: number,
  leanX: number,
  leanY: number,
) {
  const wave =
    0.022 * Math.sin(t * 1.1 + uy * 2.4) +
    0.016 * Math.sin(t * 1.45 + ux * 2.1 + 0.7) +
    0.012 * Math.cos(t * 0.9 + uz * 2.2 + 1.3);
  const press = leanX * uy * 0.035 + leanY * ux * 0.04;
  return BASE_R * (1 + wave - press);
}

function triangleWave(x: number) {
  const p = x - Math.floor(x);
  return 1 - 4 * Math.abs(p - 0.5);
}

/** Zigzag energy path on the unit sphere (local equator); tilt via parent group. */
function makeZigzagOrbit(
  zigAmp = 0.14,
  zigCount = 16,
  tube = 0.015,
  segs = 100,
) {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= segs; i++) {
    const a = (i / segs) * Math.PI * 2;
    const elev = zigAmp * triangleWave((a / (Math.PI * 2)) * zigCount);
    const x = Math.cos(elev) * Math.cos(a);
    const y = Math.sin(elev);
    const z = Math.cos(elev) * Math.sin(a);
    pts.push(new THREE.Vector3(x, y, z).multiplyScalar(BASE_R));
  }
  const path = new THREE.CatmullRomCurve3(pts, true);
  return new THREE.TubeGeometry(path, segs, tube, 5, true);
}

/** Short zigzag streak in local space; tilt + spin via parent. */
function makeZigzagStreak(
  start = 0.15,
  span = 1.8,
  zigAmp = 0.18,
  zigCount = 9,
  tube = 0.012,
  segs = 40,
) {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= segs; i++) {
    const u = i / segs;
    const a = start + u * span;
    const elev = zigAmp * triangleWave(u * zigCount);
    const x = Math.cos(elev) * Math.cos(a);
    const y = Math.sin(elev);
    const z = Math.cos(elev) * Math.sin(a);
    pts.push(new THREE.Vector3(x, y, z).multiplyScalar(BASE_R));
  }
  const path = new THREE.CatmullRomCurve3(pts, false);
  return new THREE.TubeGeometry(path, segs, tube, 5, false);
}

const ORBIT_TILTS: [number, number, number][] = [
  [0.85, 0.35, 0.2],
  [-0.55, 1.1, -0.4],
  [1.25, -0.6, 0.7],
  [0.25, -1.35, 0.9],
  [-1.05, 0.45, -1.1],
];

const STREAK_TILTS: [number, number, number][] = [
  [0.4, 0.8, 1.2],
  [-0.9, -0.3, 0.5],
  [1.4, 0.2, -0.8],
  [-0.2, 1.5, 0.3],
];

function EnergyLattice({ reducedMotion }: { reducedMotion: boolean }) {
  const spinRefs = useRef<(THREE.Mesh | null)[]>([]);

  const geos = useMemo(() => {
    const orbits = [
      makeZigzagOrbit(0.16, 18, 0.016),
      makeZigzagOrbit(0.13, 14, 0.014),
      makeZigzagOrbit(0.15, 20, 0.015),
      makeZigzagOrbit(0.11, 12, 0.013),
      makeZigzagOrbit(0.17, 16, 0.014),
    ];
    const streaks = [
      makeZigzagStreak(0.2, 2.1, 0.2, 10, 0.011),
      makeZigzagStreak(1.0, 1.7, 0.18, 8, 0.012),
      makeZigzagStreak(0.5, 2.4, 0.22, 11, 0.01),
      makeZigzagStreak(2.0, 1.9, 0.15, 9, 0.011),
    ];
    return { orbits, streaks };
  }, []);

  const speeds = useMemo(
    () => [0.08, -0.06, 0.1, -0.05, 0.07, 0.12, -0.09, 0.08, -0.11],
    [],
  );

  useEffect(() => {
    return () => {
      geos.orbits.forEach((g) => g.dispose());
      geos.streaks.forEach((g) => g.dispose());
    };
  }, [geos]);

  useFrame((_, delta) => {
    if (reducedMotion) return;
    for (let i = 0; i < spinRefs.current.length; i++) {
      const mesh = spinRefs.current[i];
      if (!mesh) continue;
      // Spin around local Y = travel along the zigzag orbit
      mesh.rotation.y += delta * speeds[i];
    }
  });

  return (
    <group>
      {geos.orbits.map((geo, i) => (
        <group key={`orbit-${i}`} rotation={ORBIT_TILTS[i]}>
          <mesh
            ref={(el) => {
              spinRefs.current[i] = el;
            }}
            geometry={geo}
          >
            <meshBasicMaterial
              color={i % 2 === 0 ? EMBER : EMBER_SOFT}
              transparent
              opacity={0.78}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </mesh>
        </group>
      ))}
      {geos.streaks.map((geo, i) => (
        <group key={`streak-${i}`} rotation={STREAK_TILTS[i]}>
          <mesh
            ref={(el) => {
              spinRefs.current[ORBIT_TILTS.length + i] = el;
            }}
            geometry={geo}
          >
            <meshBasicMaterial
              color={EMBER_HOT}
              transparent
              opacity={0.55}
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function Scene({
  reducedMotion,
  count,
  pointer,
}: {
  reducedMotion: boolean;
  count: number;
  pointer: MutableRefObject<{ x: number; y: number; strength: number }>;
}) {
  const group = useRef<THREE.Group>(null);
  const pts0 = useRef<THREE.Points>(null);
  const pts1 = useRef<THREE.Points>(null);
  const ringRefs = useRef<(THREE.Mesh | null)[]>([]);
  const lean = useRef({ x: 0, y: 0 });

  const half = (count / 2) | 0;
  const pos0 = useMemo(() => new Float32Array(half * 3), [half]);
  const pos1 = useMemo(() => new Float32Array((count - half) * 3), [count, half]);

  const bits = useMemo(() => {
    const seeds = fibSphere(count);
    const list: Bit[] = seeds.map((s, i) => ({
      theta: s.theta,
      phi: s.phi,
      speed: 0.2 + (i % 5) * 0.05,
      axis: (i % 2) as 0 | 1,
      phase: i * 0.37,
      digit: (i % 2) as 0 | 1,
    }));
    return list;
  }, [count]);

  const map0 = useMemo(() => digitTexture("0"), []);
  const map1 = useMemo(() => digitTexture("1"), []);

  useFrame((state, delta) => {
    if (!group.current) return;

    const t = reducedMotion ? 0 : state.clock.elapsedTime;

    if (reducedMotion) {
      group.current.rotation.set(0.12, 0.4, 0);
      group.current.position.set(0, 0, 0);
      group.current.scale.setScalar(0.92);
      lean.current.x = 0;
      lean.current.y = 0;
    } else {
      const p = pointer.current;
      const targetX = p.y * 0.14 * p.strength;
      const targetY = p.x * 0.18 * p.strength;
      const ease = 1 - Math.exp(-delta * 2.4);
      lean.current.x += (targetX - lean.current.x) * ease;
      lean.current.y += (targetY - lean.current.y) * ease;

      group.current.rotation.y = t * 0.09 + lean.current.y;
      group.current.rotation.x = Math.sin(t * 0.12) * 0.08 + lean.current.x;
      group.current.position.y = Math.sin(t * 0.45) * 0.05;
      group.current.position.x = lean.current.y * 0.12;

      // Subtle squash: mostly solid
      const sx = 0.92 * (1 + 0.014 * Math.sin(t * 1.0));
      const sy = 0.92 * (1 - 0.012 * Math.sin(t * 1.0 + 0.4));
      const sz = 0.92 * (1 + 0.01 * Math.cos(t * 0.85));
      group.current.scale.set(sx, sy, sz);

      for (let i = 0; i < ringRefs.current.length; i++) {
        const ring = ringRefs.current[i];
        if (ring) ring.rotation.z += delta * (0.08 - i * 0.02) * (i % 2 ? -1 : 1);
      }
    }

    let i0 = 0;
    let i1 = 0;
    const lx = lean.current.x;
    const ly = lean.current.y;
    for (let i = 0; i < bits.length; i++) {
      const b = bits[i];
      let theta = b.theta;
      let phi = b.phi;
      if (!reducedMotion) {
        if (b.axis === 0) theta = b.theta + t * b.speed + b.phase;
        else phi = b.phi + Math.sin(t * b.speed + b.phase) * 0.32;
      }
      const sp = Math.sin(phi);
      const ux = sp * Math.cos(theta);
      const uy = Math.cos(phi);
      const uz = sp * Math.sin(theta);
      const r = reducedMotion
        ? BASE_R
        : bubbleRadius(ux, uy, uz, t, lx, ly);
      const x = ux * r;
      const y = uy * r;
      const z = uz * r;
      if (b.digit === 0) {
        pos0[i0++] = x;
        pos0[i0++] = y;
        pos0[i0++] = z;
      } else {
        pos1[i1++] = x;
        pos1[i1++] = y;
        pos1[i1++] = z;
      }
    }
    const a0 = pts0.current?.geometry.getAttribute("position") as
      | THREE.BufferAttribute
      | undefined;
    const a1 = pts1.current?.geometry.getAttribute("position") as
      | THREE.BufferAttribute
      | undefined;
    if (a0) a0.needsUpdate = true;
    if (a1) a1.needsUpdate = true;
  });

  const rings: [number, [number, number, number]][] = [
    [1.22, [0.55, 0.15, 0.08]],
    [1.1, [-0.35, 0.7, -0.15]],
    [1.32, [0.95, -0.25, 0.4]],
  ];

  return (
    <group ref={group} scale={0.92}>
      <EnergyLattice reducedMotion={reducedMotion} />

      {rings.map(([r, tilt], i) => (
        <mesh
          key={i}
          ref={(el) => {
            ringRefs.current[i] = el;
          }}
          rotation={tilt}
        >
          <torusGeometry args={[r, 0.014, 8, 80]} />
          <meshBasicMaterial
            color={EMBER_HOT}
            transparent
            opacity={0.65}
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      ))}

      <points ref={pts0}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[pos0, 3]} />
        </bufferGeometry>
        <pointsMaterial
          map={map0}
          transparent
          depthWrite={false}
          size={0.24}
          sizeAttenuation
          opacity={0.9}
          color={EMBER_SOFT}
          blending={THREE.AdditiveBlending}
        />
      </points>

      <points ref={pts1}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[pos1, 3]} />
        </bufferGeometry>
        <pointsMaterial
          map={map1}
          transparent
          depthWrite={false}
          size={0.24}
          sizeAttenuation
          opacity={0.95}
          color={EMBER}
          blending={THREE.AdditiveBlending}
        />
      </points>

      <mesh>
        <sphereGeometry args={[0.06, 8, 8]} />
        <meshBasicMaterial color="#fff6e8" />
      </mesh>
    </group>
  );
}

export default function BinarySphereCanvas() {
  const [ready, setReady] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [count, setCount] = useState(56);
  const hostRef = useRef<HTMLDivElement>(null);
  const pointer = useRef({ x: 0, y: 0, strength: 0 });

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const applyMotion = () => setReducedMotion(mq.matches);
    applyMotion();
    mq.addEventListener("change", applyMotion);

    const narrow = window.matchMedia("(max-width: 640px)");
    const applyCount = () => setCount(narrow.matches ? 40 : 64);
    applyCount();
    narrow.addEventListener("change", applyCount);

    return () => {
      mq.removeEventListener("change", applyMotion);
      narrow.removeEventListener("change", applyCount);
    };
  }, []);

  useEffect(() => {
    if (reducedMotion) {
      pointer.current = { x: 0, y: 0, strength: 0 };
      return;
    }

    const onMove = (e: PointerEvent) => {
      const el = hostRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const nx = (e.clientX - cx) / (rect.width * 0.5);
      const ny = (e.clientY - cy) / (rect.height * 0.5);
      const dist = Math.hypot(nx, ny);
      // Influence only when near (~1.6× stage radius); soft falloff
      const raw = Math.max(0, 1 - dist / 1.6);
      pointer.current.x = THREE.MathUtils.clamp(nx, -1.25, 1.25);
      pointer.current.y = THREE.MathUtils.clamp(ny, -1.25, 1.25);
      pointer.current.strength = raw * raw;
    };

    const onLeave = () => {
      pointer.current.strength = 0;
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("blur", onLeave);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("blur", onLeave);
    };
  }, [reducedMotion]);

  // Defer WebGL until the hero is near viewport + browser is idle
  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;

    let cancelled = false;
    let idleHandle: number | null = null;
    let timeoutHandle: ReturnType<typeof setTimeout> | null = null;

    const start = () => {
      if (cancelled) return;
      if ("requestIdleCallback" in window) {
        idleHandle = window.requestIdleCallback(() => setReady(true), {
          timeout: 500,
        });
      } else {
        timeoutHandle = setTimeout(() => setReady(true), 80);
      }
    };

    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          start();
          io.disconnect();
        }
      },
      { rootMargin: "160px" },
    );
    io.observe(el);

    return () => {
      cancelled = true;
      io.disconnect();
      if (idleHandle != null && "cancelIdleCallback" in window) {
        window.cancelIdleCallback(idleHandle);
      }
      if (timeoutHandle != null) clearTimeout(timeoutHandle);
    };
  }, []);

  return (
    <div ref={hostRef} style={{ width: "100%", height: "100%" }}>
      {ready ? (
        <Canvas
          dpr={[1, 1.25]}
          camera={{ position: [0, 0.08, 5.1], fov: 38 }}
          frameloop={reducedMotion ? "demand" : "always"}
          gl={{
            antialias: false,
            alpha: true,
            powerPreference: "high-performance",
            stencil: false,
            depth: true,
          }}
          onCreated={({ gl }) => {
            gl.setClearColor(0x000000, 0);
          }}
          style={{ width: "100%", height: "100%", display: "block" }}
        >
          <Scene
            reducedMotion={reducedMotion}
            count={count}
            pointer={pointer}
          />
        </Canvas>
      ) : null}
    </div>
  );
}
