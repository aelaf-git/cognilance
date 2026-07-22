"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const EMBER = "#fd8925";
const EMBER_HOT = "#ff492c";
const EMBER_SOFT = "#ff8e5d";

function makeDigitTexture(digit: "0" | "1", color: string) {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return new THREE.Texture();

  ctx.clearRect(0, 0, size, size);
  ctx.font = "600 42px ui-monospace, SFMono-Regular, Menlo, monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 14;
  ctx.fillText(digit, size / 2, size / 2 + 1);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.needsUpdate = true;
  return texture;
}

function fibonacciSphere(count: number) {
  const points: THREE.Vector3[] = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / Math.max(count - 1, 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i;
    points.push(new THREE.Vector3(Math.cos(theta) * r, y, Math.sin(theta) * r));
  }
  return points;
}

type BitParticle = {
  theta: number;
  phi: number;
  speed: number;
  axis: "theta" | "phi";
  phase: number;
};

function WireShell({ radius = 1.35 }: { radius?: number }) {
  return (
    <mesh>
      <sphereGeometry args={[radius, 36, 28]} />
      <meshBasicMaterial
        color={EMBER}
        wireframe
        transparent
        opacity={0.2}
        depthWrite={false}
      />
    </mesh>
  );
}

function LatitudeArcs({ radius = 1.35 }: { radius?: number }) {
  const lines = useMemo(() => {
    const lats = [-0.72, -0.36, 0, 0.36, 0.72];
    return lats.map((yNorm, idx) => {
      const y = yNorm * radius;
      const r = Math.sqrt(Math.max(radius * radius - y * y, 0.01));
      const pts: THREE.Vector3[] = [];
      const segs = 96;
      for (let i = 0; i <= segs; i++) {
        const a = (i / segs) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r));
      }
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const mat = new THREE.LineBasicMaterial({
        color: EMBER_SOFT,
        transparent: true,
        opacity: 0.28 + (idx % 2) * 0.12,
        depthWrite: false,
      });
      return new THREE.Line(geo, mat);
    });
  }, [radius]);

  useEffect(() => {
    return () => {
      lines.forEach((line) => {
        line.geometry.dispose();
        (line.material as THREE.Material).dispose();
      });
    };
  }, [lines]);

  return (
    <group>
      {lines.map((line, i) => (
        <primitive key={`lat-${i}`} object={line} />
      ))}
    </group>
  );
}

function OrbitRing({
  radius,
  tilt,
  speed,
  reducedMotion,
}: {
  radius: number;
  tilt: [number, number, number];
  speed: number;
  reducedMotion: boolean;
}) {
  const ref = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (!ref.current || reducedMotion) return;
    ref.current.rotation.z += delta * speed;
  });

  return (
    <mesh ref={ref} rotation={tilt}>
      <torusGeometry args={[radius, 0.007, 8, 160]} />
      <meshBasicMaterial
        color={EMBER_HOT}
        transparent
        opacity={0.55}
        depthWrite={false}
      />
    </mesh>
  );
}

function DigitCloud({
  digit,
  count,
  radius,
  reducedMotion,
  color,
}: {
  digit: "0" | "1";
  count: number;
  radius: number;
  reducedMotion: boolean;
  color: string;
}) {
  const pointsRef = useRef<THREE.Points>(null);
  const positions = useMemo(() => new Float32Array(count * 3), [count]);

  const { particles, texture } = useMemo(() => {
    const seeds = fibonacciSphere(count * 2);
    const offset = digit === "0" ? 0 : 1;
    const particles: BitParticle[] = [];
    for (let i = 0; i < count; i++) {
      const seed = seeds[i * 2 + offset] ?? seeds[i];
      particles.push({
        theta: Math.atan2(seed.z, seed.x),
        phi: Math.acos(THREE.MathUtils.clamp(seed.y, -1, 1)),
        speed: 0.18 + (i % 7) * 0.045,
        axis: i % 2 === 0 ? "theta" : "phi",
        phase: (i * 0.41 + (digit === "1" ? 1.2 : 0)) % Math.PI,
      });
    }
    return { particles, texture: makeDigitTexture(digit, color) };
  }, [count, digit, color]);

  useEffect(() => {
    return () => {
      texture.dispose();
    };
  }, [texture]);

  useFrame((state) => {
    const t = reducedMotion ? 0 : state.clock.elapsedTime;
    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      let theta = p.theta;
      let phi = p.phi;
      if (!reducedMotion) {
        if (p.axis === "theta") {
          theta = p.theta + t * p.speed + p.phase;
        } else {
          phi = p.phi + Math.sin(t * p.speed + p.phase) * 0.4;
        }
      }
      const sinPhi = Math.sin(phi);
      positions[i * 3] = radius * sinPhi * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.cos(phi);
      positions[i * 3 + 2] = radius * sinPhi * Math.sin(theta);
    }
    const attr = pointsRef.current?.geometry.getAttribute("position") as
      | THREE.BufferAttribute
      | undefined;
    if (attr) attr.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        map={texture}
        transparent
        depthWrite={false}
        size={0.15}
        sizeAttenuation
        opacity={0.92}
        color={color}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

function CoreGlow() {
  return (
    <mesh>
      <sphereGeometry args={[0.07, 16, 16]} />
      <meshBasicMaterial color="#fff6e8" transparent opacity={0.95} />
    </mesh>
  );
}

function EnergyBubble({
  reducedMotion,
  particleCount,
}: {
  reducedMotion: boolean;
  particleCount: number;
}) {
  const group = useRef<THREE.Group>(null);
  const half = Math.floor(particleCount / 2);

  useFrame((state) => {
    if (!group.current) return;
    if (reducedMotion) {
      group.current.rotation.set(0.15, 0.45, 0);
      group.current.position.y = 0;
      return;
    }
    const t = state.clock.elapsedTime;
    group.current.rotation.y = t * 0.18;
    group.current.rotation.x = Math.sin(t * 0.22) * 0.12;
    group.current.position.y = Math.sin(t * 0.7) * 0.08;
  });

  return (
    <group ref={group}>
      <WireShell />
      <LatitudeArcs />
      <OrbitRing
        radius={1.42}
        tilt={[0.6, 0.2, 0.1]}
        speed={0.35}
        reducedMotion={reducedMotion}
      />
      <OrbitRing
        radius={1.28}
        tilt={[-0.4, 0.8, -0.2]}
        speed={-0.28}
        reducedMotion={reducedMotion}
      />
      <OrbitRing
        radius={1.55}
        tilt={[1.1, -0.3, 0.5]}
        speed={0.22}
        reducedMotion={reducedMotion}
      />
      <DigitCloud
        digit="0"
        count={half}
        radius={1.35}
        reducedMotion={reducedMotion}
        color={EMBER_SOFT}
      />
      <DigitCloud
        digit="1"
        count={particleCount - half}
        radius={1.35}
        reducedMotion={reducedMotion}
        color={EMBER}
      />
      <CoreGlow />
      <pointLight color={EMBER} intensity={2.4} distance={6} />
      <pointLight
        color={EMBER_HOT}
        intensity={1.3}
        distance={4}
        position={[0.45, 0.25, 0.35]}
      />
    </group>
  );
}

export default function BinarySphere() {
  const [reducedMotion, setReducedMotion] = useState(false);
  const [particleCount, setParticleCount] = useState(140);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const applyMotion = () => setReducedMotion(mq.matches);
    applyMotion();
    mq.addEventListener("change", applyMotion);

    const narrow = window.matchMedia("(max-width: 640px)");
    const applyCount = () => setParticleCount(narrow.matches ? 80 : 160);
    applyCount();
    narrow.addEventListener("change", applyCount);

    return () => {
      mq.removeEventListener("change", applyMotion);
      narrow.removeEventListener("change", applyCount);
    };
  }, []);

  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [0, 0.12, 4.15], fov: 42 }}
      gl={{
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
      }}
      onCreated={({ gl }) => {
        gl.setClearColor(0x000000, 0);
      }}
      style={{ width: "100%", height: "100%", display: "block" }}
    >
      <ambientLight intensity={0.12} />
      <EnergyBubble
        reducedMotion={reducedMotion}
        particleCount={particleCount}
      />
      {!reducedMotion && (
        <EffectComposer>
          <Bloom
            intensity={1.2}
            luminanceThreshold={0.18}
            luminanceSmoothing={0.45}
            mipmapBlur
          />
        </EffectComposer>
      )}
    </Canvas>
  );
}
