"use client";

import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import { AdditiveBlending, BackSide, Color, DoubleSide, type Group, type Mesh, type MeshBasicMaterial, type MeshStandardMaterial } from "three";

/**
 * 3D droplet flame inside a simplified ISS droplet-combustion chamber (MDCA-style):
 * glass chamber, support needle, retractable hot-wire igniter and the main instruments.
 *
 * `flame` is the flame-shell radius, `intensity` (0-1) how strongly the flame burns (0 = out),
 * `heat` (0-1) how hot the droplet looks, `ignition` (0-1) how far the igniter has retracted.
 * `gravity` "earth" draws the buoyant, sooty, upward-stretched flame for comparison; it is an
 * illustration, not a model output (the model only covers microgravity).
 */
export type Gravity = "micro" | "earth";
type Props = {
  droplet: number; flame: number; intensity?: number; heat?: number; ignition?: number;
  gravity?: Gravity; labels?: boolean;
};

const HOT = new Color("#FFB27A");
const COLD = new Color("#8A8F99");
const BLUE = new Color("#5AA9FF");
const SOOT = new Color("#FF9A3C");

function Flame({ droplet, flame, intensity = 1, heat = 1, gravity = "micro" }: Props) {
  const group = useRef<Group>(null);
  const shell = useRef<Mesh>(null);
  const rim = useRef<Mesh>(null);
  const glow = useRef<Mesh>(null);
  const drop = useRef<MeshStandardMaterial>(null);
  const still = useMemo(() => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches, []);
  const earth = gravity === "earth";

  useFrame(({ clock }) => {
    const s = clock.getElapsedTime();
    // Flicker: a slow breath plus a faster tremor; Earth flames flicker more (buoyant eddies).
    const amp = earth ? 2.2 : 1;
    const f = still ? 1 : 1 + intensity * amp * (0.025 * Math.sin(s * 2.1) + 0.012 * Math.sin(s * 9.7));
    shell.current?.scale.setScalar(f);
    rim.current?.scale.setScalar(f * 1.04);
    const shellMat = shell.current?.material as MeshBasicMaterial | undefined;
    if (shellMat) {
      shellMat.opacity = (earth ? 0.32 : 0.22) * intensity;
      shellMat.color.copy(earth ? SOOT : BLUE);
    }
    (rim.current?.material as MeshBasicMaterial | undefined)?.setValues({ opacity: 0.1 * intensity });
    (glow.current?.material as MeshBasicMaterial | undefined)?.setValues({ opacity: (earth ? 0.3 : 0.16) * intensity });
    if (drop.current) {
      drop.current.color.copy(COLD).lerp(HOT, heat);
      drop.current.emissiveIntensity = 1.6 * heat;
    }
  });

  // On Earth, buoyancy pulls hot gas upward: a tall teardrop above the droplet instead of a sphere.
  const stretch: [number, number, number] = earth ? [0.45, 1.1, 0.45] : [1, 1, 1];
  const lift = earth ? flame * 0.5 : 0;

  return (
    <>
      <pointLight position={[0, lift, 0]} intensity={8 * Math.max(intensity, heat * 0.3)} color="#FF7A30" distance={6} />
      <mesh>
        <sphereGeometry args={[droplet, 48, 48]} />
        <meshStandardMaterial ref={drop} color="#FFB27A" emissive="#FF7A30" emissiveIntensity={1.6} roughness={0.3} />
      </mesh>
      <group ref={group} position={[0, lift, 0]} scale={stretch}>
        <mesh ref={glow}>
          <sphereGeometry args={[Math.max(droplet * 3.2, 0.05), 48, 48]} />
          <meshBasicMaterial color="#FF7A30" transparent opacity={0.16} blending={AdditiveBlending} depthWrite={false} />
        </mesh>
        <mesh ref={shell}>
          <sphereGeometry args={[flame, 64, 64]} />
          <meshBasicMaterial color="#5AA9FF" transparent opacity={0.22} blending={AdditiveBlending} side={BackSide} depthWrite={false} />
        </mesh>
        <mesh ref={rim}>
          <sphereGeometry args={[flame, 64, 64]} />
          <meshBasicMaterial color="#7FC0FF" transparent opacity={0.1} blending={AdditiveBlending} depthWrite={false} />
        </mesh>
      </group>
    </>
  );
}

function Label({ position, children, show }: { position: [number, number, number]; children: string; show: boolean }) {
  // Always mounted (unmounting drei's Html mid-render warns); hidden with CSS instead.
  return (
    <Html position={position} center distanceFactor={11} zIndexRange={[10, 0]}>
      <span className={`glass t-caps-s whitespace-nowrap rounded-full px-2.5 py-1 text-fg-2 select-none transition-opacity ${show ? "opacity-100" : "opacity-0"}`}>{children}</span>
    </Html>
  );
}

const METAL = "#3A3F4B";

/* Simplified MDCA chamber: glass cylinder, end rings, struts, needle, igniter, instruments. */
function Chamber({ droplet, ignition = 1, labels = true, flame }: Props) {
  const R = 2.3, H = 4.6;
  // The hot-wire igniter swings in next to the droplet, then retracts once the flame is lit.
  const igniterX = droplet + 0.12 + ignition * 1.2;
  return (
    <group>
      {/* Glass wall */}
      <mesh>
        <cylinderGeometry args={[R, R, H, 64, 1, true]} />
        <meshStandardMaterial color="#9FB7D9" transparent opacity={0.06} roughness={0.05} metalness={0.2} side={DoubleSide} depthWrite={false} />
      </mesh>
      {/* End rings and struts */}
      {[H / 2, -H / 2].map((y) => (
        <mesh key={y} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[R, 0.06, 12, 96]} />
          <meshStandardMaterial color={METAL} metalness={0.8} roughness={0.35} />
        </mesh>
      ))}
      {[0, 1, 2, 3].map((i) => {
        const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
        return (
          <mesh key={i} position={[Math.cos(a) * R, 0, Math.sin(a) * R]}>
            <cylinderGeometry args={[0.04, 0.04, H, 12]} />
            <meshStandardMaterial color={METAL} metalness={0.8} roughness={0.35} />
          </mesh>
        );
      })}
      {/* Base plate */}
      <mesh position={[0, -H / 2 - 0.05, 0]}>
        <cylinderGeometry args={[R + 0.15, R + 0.15, 0.1, 64]} />
        <meshStandardMaterial color="#2A2F3A" metalness={0.6} roughness={0.5} transparent opacity={0.55} />
      </mesh>
      {/* Support needle holding the droplet (deployment needles in FLEX) */}
      <mesh position={[0, (-H / 2 - droplet) / 2, 0]}>
        <cylinderGeometry args={[0.012, 0.02, H / 2 - droplet, 8]} />
        <meshStandardMaterial color="#C9CED8" metalness={0.9} roughness={0.2} />
      </mesh>
      {/* Hot-wire igniter: arm + glowing tip */}
      <group position={[igniterX, 0.05, 0]}>
        <mesh position={[0.8, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.015, 0.015, 1.6, 8]} />
          <meshStandardMaterial color="#9AA0AB" metalness={0.7} roughness={0.3} />
        </mesh>
        <mesh>
          <sphereGeometry args={[0.035, 12, 12]} />
          <meshStandardMaterial color="#FF7A30" emissive="#FF7A30" emissiveIntensity={ignition < 1 ? 2.5 : 0.2} />
        </mesh>
      </group>
      {/* Instruments on the chamber wall */}
      <mesh position={[0.9, 1.5, -R + 0.1]}>
        <boxGeometry args={[0.45, 0.32, 0.25]} />
        <meshStandardMaterial color="#20242D" metalness={0.5} roughness={0.4} />
      </mesh>
      <mesh position={[-R + 0.15, 0.9, 0.4]}>
        <boxGeometry args={[0.22, 0.22, 0.36]} />
        <meshStandardMaterial color="#20242D" metalness={0.5} roughness={0.4} />
      </mesh>
      {/* drei's first <Html> root gets torn down by React 19's double mount in dev; a hidden
          placeholder takes that hit so every real label renders. */}
      <Label show={false} position={[0, 0, 0]}>{" "}</Label>
      <Label show={labels} position={[-0.75, -0.45, 0.6]}>Fuel droplet</Label>
      <Label show={labels} position={[flame * 0.7, flame * 0.85, 0.3]}>Flame</Label>
      <Label show={labels} position={[Math.min(igniterX + 0.6, 1.6), -0.3, 0.4]}>Igniter</Label>
      <Label show={labels} position={[0.9, 1.9, -R + 0.1]}>Camera</Label>
      <Label show={labels} position={[-R + 0.9, 1.35, 0.4]}>Radiometer</Label>
      <Label show={labels} position={[0.55, -1.7, 0]}>Support needle</Label>
    </group>
  );
}

export default function DropletScene(props: Props) {
  return (
    <Canvas camera={{ position: [2.4, 0.9, 13], fov: 38 }} dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
      <ambientLight intensity={0.35} />
      <directionalLight position={[3, 4, 3]} intensity={0.7} />
      <Chamber {...props} />
      <Flame {...props} />
      <OrbitControls enablePan={false} minDistance={2.5} maxDistance={12} />
    </Canvas>
  );
}
