"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { AdditiveBlending, BackSide } from "three";

/**
 * 3D droplet flame: fuel droplet (ember core) inside a spherical blue flame shell,
 * as seen in microgravity droplet tests. Sizes are in scene units.
 */
export default function DropletScene({ droplet, flame }: { droplet: number; flame: number }) {
  return (
    <Canvas camera={{ position: [0, 0.6, 5.2], fov: 45 }} dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
      <ambientLight intensity={0.25} />
      <pointLight position={[0, 0, 0]} intensity={8} color="#FF7A30" distance={6} />
      <directionalLight position={[3, 3, 3]} intensity={0.6} />

      {/* Fuel droplet */}
      <mesh>
        <sphereGeometry args={[droplet, 48, 48]} />
        <meshStandardMaterial color="#FFB27A" emissive="#FF7A30" emissiveIntensity={1.6} roughness={0.3} />
      </mesh>
      {/* Soot / inner glow */}
      <mesh>
        <sphereGeometry args={[Math.max(droplet * 3.2, 0.05), 48, 48]} />
        <meshBasicMaterial color="#FF7A30" transparent opacity={0.16} blending={AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* Flame shell: bright rim, see-through center */}
      <mesh>
        <sphereGeometry args={[flame, 64, 64]} />
        <meshBasicMaterial color="#5AA9FF" transparent opacity={0.22} blending={AdditiveBlending} side={BackSide} depthWrite={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[flame * 1.04, 64, 64]} />
        <meshBasicMaterial color="#7FC0FF" transparent opacity={0.1} blending={AdditiveBlending} depthWrite={false} />
      </mesh>
      {/* Orbit ring for scale/orientation */}
      <mesh rotation={[Math.PI / 2.3, 0, 0.25]}>
        <torusGeometry args={[2.4, 0.004, 8, 160]} />
        <meshBasicMaterial color="#E6E8EE" transparent opacity={0.18} />
      </mesh>

      <OrbitControls enablePan={false} minDistance={2.5} maxDistance={10} />
    </Canvas>
  );
}
