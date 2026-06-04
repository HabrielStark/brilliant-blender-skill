import { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { useGLTF, ScrollControls, useScroll } from '@react-three/drei';
import cameraPath from './camera_path.json';

function sampleCamera(t) {
  const segs = cameraPath.samples;
  if (!segs.length) return null;
  const i = Math.min(segs.length - 1, Math.floor(t * (segs.length - 1)));
  return segs[i];
}

function Rig({ children }) {
  const scroll = useScroll();
  useFrame((state) => {
    const t = scroll.offset; // 0..1 (respects reduced-motion via prefers-reduced-motion)
    const s = sampleCamera(t);
    if (s && s.position) state.camera.position.set(...s.position);
    if (s && s.target) state.camera.lookAt(...s.target);
  });
  return children;
}

function Model() { const { scene } = useGLTF('/scene.glb'); return <primitive object={scene} />; }
useGLTF.preload('/scene.glb');

export default function ScrollHero() {
  const reduced = typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  return (
    <Canvas dpr={[1, 2]} camera={{ position: [0, 1, 4], fov: 50 }}>
      <ambientLight intensity={0.6} />
      <Suspense fallback={null}>
        <ScrollControls pages={4.0} damping={reduced ? 0 : 0.2}>
          <Rig><Model /></Rig>
        </ScrollControls>
      </Suspense>
    </Canvas>
  );
}
