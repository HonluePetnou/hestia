"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import { AdditiveBlending, BackSide, Color, type Mesh, type MeshBasicMaterial, type MeshStandardMaterial } from "three";

/**
 * 3D droplet flame: fuel droplet (ember core) inside a spherical blue flame shell,
 * as seen in microgravity droplet tests. Sizes are in scene units.
 *
 * `flame` is the flame-shell radius, `intensity` (0-1) how strongly the flame burns (0 = out),
 * `heat` (0-1) how hot the droplet surface looks (it cools to grey once the flame is out).
 */
type Props = { droplet: number; flame: number; intensity?: number; heat?: number };

const HOT = new Color("#FFB27A");
const COLD = new Color("#8A8F99");

function Flame({ droplet, flame, intensity = 1, heat = 1 }: Props) {
  const shell = useRef<Mesh>(null);
  const rim = useRef<Mesh>(null);
  const glow = useRef<Mesh>(null);
  const drop = useRef<MeshStandardMaterial>(null);
  const still = useMemo(() => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches, []);

  useFrame(({ clock }) => {
    const s = clock.getElapsedTime();
    // Flicker: a slow breath plus a faster tremor, only while the flame burns.
    const f = still ? 1 : 1 + intensity * (0.025 * Math.sin(s * 2.1) + 0.012 * Math.sin(s * 9.7));
    shell.current?.scale.setScalar(f);
    rim.current?.scale.setScalar(f * 1.04);
    (shell.current?.material as MeshBasicMaterial | undefined)?.setValues({ opacity: 0.22 * intensity });
    (rim.current?.material as MeshBasicMaterial | undefined)?.setValues({ opacity: 0.1 * intensity });
    (glow.current?.material as MeshBasicMaterial | undefined)?.setValues({ opacity: 0.16 * intensity });
    if (drop.current) {
      drop.current.color.copy(COLD).lerp(HOT, heat);
      drop.current.emissiveIntensity = 1.6 * heat;
    }
  });

  return (
    <>
      <pointLight position={[0, 0, 0]} intensity={8 * Math.max(intensity, heat * 0.3)} color="#FF7A30" distance={6} />
      {/* Fuel droplet */}
      <mesh>
        <sphereGeometry args={[droplet, 48, 48]} />
        <meshStandardMaterial ref={drop} color="#FFB27A" emissive="#FF7A30" emissiveIntensity={1.6} roughness={0.3} />
      </mesh>
      {/* Soot / inner glow */}
      <mesh ref={glow}>
        <sphereGeometry args={[Math.max(droplet * 3.2, 0.05), 48, 48]} />
        <meshBasicMaterial color="#FF7A30" transparent opacity={0.16} blending={AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* Flame shell: bright rim, see-through center */}
      <mesh ref={shell}>
        <sphereGeometry args={[flame, 64, 64]} />
        <meshBasicMaterial color="#5AA9FF" transparent opacity={0.22} blending={AdditiveBlending} side={BackSide} depthWrite={false} />
      </mesh>
      <mesh ref={rim}>
        <sphereGeometry args={[flame, 64, 64]} />
        <meshBasicMaterial color="#7FC0FF" transparent opacity={0.1} blending={AdditiveBlending} depthWrite={false} />
      </mesh>
    </>
  );
}

export default function DropletScene(props: Props) {
  return (
    <Canvas camera={{ position: [0, 0.6, 5.2], fov: 45 }} dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
      <ambientLight intensity={0.25} />
      <directionalLight position={[3, 3, 3]} intensity={0.6} />
      <Flame {...props} />
      {/* Orbit ring for scale/orientation */}
      <mesh rotation={[Math.PI / 2.3, 0, 0.25]}>
        <torusGeometry args={[2.4, 0.004, 8, 160]} />
        <meshBasicMaterial color="#E6E8EE" transparent opacity={0.18} />
      </mesh>
      <OrbitControls enablePan={false} minDistance={2.5} maxDistance={10} />
    </Canvas>
  );
}
