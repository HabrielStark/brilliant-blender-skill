// GSAP ScrollTrigger camera timeline (scrubbed). Requires gsap + ScrollTrigger.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import cameraPath from './camera_path.json';
gsap.registerPlugin(ScrollTrigger);

export function initScrollScene(canvas, { glb = 'scene.glb' } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 100);
  camera.position.set(0, 1, 4);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x222233, 1.0));
  new GLTFLoader().load(glb, (g) => scene.add(g.scene));
  const proxy = { t: 0 };
  gsap.to(proxy, { t: 1, ease: 'none',
    scrollTrigger: { trigger: '#hero', start: 'top top', end: 'bottom bottom', scrub: true },
    onUpdate() {
      const s = cameraPath.samples;
      if (!s.length) return;
      const k = s[Math.min(s.length - 1, Math.floor(proxy.t * (s.length - 1)))];
      if (k.position) camera.position.set(...k.position);
      if (k.target) camera.lookAt(...k.target);
    } });
  function resize() { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight); }
  addEventListener('resize', resize); resize();
  (function loop() { requestAnimationFrame(loop); renderer.render(scene, camera); })();
}
