"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";

export default function DropletScene() {
  return (
    <Canvas camera={{ position: [0, 0, 4], fov: 50 }}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[3, 3, 3]} intensity={1} />
      <mesh>
        <sphereGeometry args={[1, 64, 64]} />
        <meshStandardMaterial color="gray" />
      </mesh>
      <OrbitControls enablePan={false} />
    </Canvas>
  );
}
