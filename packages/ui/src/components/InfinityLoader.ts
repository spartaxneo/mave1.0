import * as THREE from "three";

const TUBULAR_SEGMENTS = 260;
const RADIAL_SEGMENTS = 10;

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const smoothstep = (a: number, b: number, x: number) => {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};
const smootherstep = (a: number, b: number, x: number) => {
  const t = clamp01((x - a) / (b - a));
  return t * t * t * (t * (t * 6 - 15) + 10);
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const easeInOutQuad01 = (x: number) => {
  const t = clamp01(x);
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
};

const VERTEX_SHADER = /* glsl */ `
  varying vec3 vNormalView;
  varying vec3 vViewPos;
  varying float vU;
  varying float vDepth;

  void main() {
    vU = uv.x;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vViewPos = -mvPosition.xyz;
    vNormalView = normalize(normalMatrix * normal);
    // Normalized depth along the curve relative to group center (front > 0, back < 0)
    vDepth = clamp((-mvPosition.z - 105.0) / 55.0, -1.0, 1.0);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const CORE_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  uniform float uEnergy;
  uniform float uMorph;
  uniform float uTime;

  varying vec3 vNormalView;
  varying vec3 vViewPos;
  varying float vU;
  varying float vDepth;

  void main() {
    vec3 N = normalize(vNormalView);
    vec3 V = normalize(vViewPos);
    float ndotv = clamp(abs(dot(N, V)), 0.0, 1.0);

    // Optical core with silky anti-aliased edge softness (35mm filmic falloff).
    float edge = smoothstep(0.06, 0.58, ndotv);
    float coreHot = pow(ndotv, 1.4);

    // Subtle depth cue during 3D helix spin: near strand crisp warm-white, far strand softer.
    float depthShade = mix(1.0, mix(1.0, 0.62, smoothstep(-0.35, 0.75, vDepth)), 1.0 - uMorph * 0.85);

    // Subtle travelling luminous pulse along the ribbon driven by audio energy.
    float shimmer = 0.92 + 0.08 * sin(vU * 12.56637 - uTime * 3.8) + uEnergy * 0.16;

    vec3 col = uColor * (0.94 + 0.12 * coreHot) * shimmer;
    float alpha = uOpacity * edge * depthShade;
    gl_FragColor = vec4(col, clamp(alpha, 0.0, 1.0));
  }
`;

const GLOW_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  uniform float uEnergy;

  varying vec3 vNormalView;
  varying vec3 vViewPos;
  varying float vDepth;

  void main() {
    vec3 N = normalize(vNormalView);
    vec3 V = normalize(vViewPos);
    float ndotv = clamp(abs(dot(N, V)), 0.0, 1.0);

    // Wide soft incandescent halo around the filament.
    float halo = pow(ndotv, 2.6);
    float depthFade = mix(1.0, 0.55, smoothstep(-0.35, 0.75, vDepth));
    float alpha = uOpacity * halo * depthFade * (0.85 + uEnergy * 0.75);
    gl_FragColor = vec4(uColor, clamp(alpha, 0.0, 1.0));
  }
`;

interface TubeLayer {
  geometry: THREE.BufferGeometry;
  material: THREE.ShaderMaterial;
  mesh: THREE.Mesh<THREE.BufferGeometry, THREE.ShaderMaterial>;
  positions: Float32Array;
  normals: Float32Array;
}

function createTubeLayer(material: THREE.ShaderMaterial): TubeLayer {
  const segs = TUBULAR_SEGMENTS;
  const rads = RADIAL_SEGMENTS;
  const vertCount = (segs + 1) * (rads + 1);

  const positions = new Float32Array(vertCount * 3);
  const normals = new Float32Array(vertCount * 3);
  const uvs = new Float32Array(vertCount * 2);
  const indices: number[] = [];

  for (let i = 0; i <= segs; i++) {
    const u = i / segs;
    for (let j = 0; j <= rads; j++) {
      const idx = i * (rads + 1) + j;
      uvs[idx * 2] = u;
      uvs[idx * 2 + 1] = j / rads;
    }
  }

  for (let i = 0; i < segs; i++) {
    for (let j = 0; j < rads; j++) {
      const a = i * (rads + 1) + j;
      const b = (i + 1) * (rads + 1) + j;
      const c = (i + 1) * (rads + 1) + (j + 1);
      const d = i * (rads + 1) + (j + 1);
      indices.push(a, b, d, b, c, d);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
  geometry.setAttribute("uv", new THREE.BufferAttribute(uvs, 2));
  geometry.setIndex(indices);

  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;

  return { geometry, material, mesh, positions, normals };
}

/**
 * Reusable scratch buffers for zero-allocation parallel-transport (Bishop) closed tube updates.
 * Bishop frames completely eliminate the 180-degree Frenet-frame pinching twist at figure-8 inflection points.
 */
class TubeBuilder {
  private readonly pts = new Float32Array((TUBULAR_SEGMENTS + 1) * 3);
  private readonly tangents = new Float32Array((TUBULAR_SEGMENTS + 1) * 3);
  private readonly normals = new Float32Array((TUBULAR_SEGMENTS + 1) * 3);
  private readonly binormals = new Float32Array((TUBULAR_SEGMENTS + 1) * 3);
  private readonly cosTable = new Float32Array(RADIAL_SEGMENTS + 1);
  private readonly sinTable = new Float32Array(RADIAL_SEGMENTS + 1);

  constructor() {
    for (let j = 0; j <= RADIAL_SEGMENTS; j++) {
      const a = (j / RADIAL_SEGMENTS) * Math.PI * 2;
      this.cosTable[j] = Math.cos(a);
      this.sinTable[j] = Math.sin(a);
    }
  }

  /**
   * Evaluate the continuous 3D infinity-helix → circle curve into `pts`, then build a
   * closed rotation-minimizing (Bishop) frame and fill one or more tube layers.
   */
  evaluateCurve(
    spinAngle: number,
    morph: number,
    waveAmp: number,
    wavePhase: number,
    ringRadius: number,
    scale: number,
    offsetZ = 0,
  ): void {
    const N = TUBULAR_SEGMENTS;
    const pts = this.pts;

    // Helix dimensions: graceful wide infinity double-helix that weaves continuously
    // between the iconic 3-lobe DNA ribbon (cos 3θ) and 2-lobe ∞ figure-8 (sin 2θ) —
    // never flattening into a plain oval at any spin angle!
    const L = 34.0;
    const R = 7.4;

    const cosSpin = Math.cos(spinAngle);
    const sinSpin = Math.sin(spinAngle);

    // Pre-morph easing: horizontal extent compresses while the twisted helix unfolds cleanly into a circle.
    const mPos = smootherstep(0, 1, morph);
    const harmonicRipple = waveAmp * Math.sin(Math.PI * mPos) * (1 - mPos * 0.65);

    for (let i = 0; i <= N; i++) {
      const u = i === N ? 0 : i / N;
      const theta = u * Math.PI * 2;
      const sinT = Math.sin(theta);
      const cosT = Math.cos(theta);

      // 1) True 3D OS1 double-helix / infinity curve, spinning around X.
      const hx = L * sinT;
      const hyRaw = R * Math.cos(3 * theta);
      const hzRaw = R * Math.sin(2 * theta);
      const hy = hyRaw * cosSpin - hzRaw * sinSpin;
      const hz = hyRaw * sinSpin + hzRaw * cosSpin;

      // 2) Target perfect circle in the YZ plane (faces camera dead-on after group.rotation.y = -PI/2).
      const cx = 0;
      const cy = ringRadius * cosT;
      const cz = ringRadius * sinT;

      // 3) Organic damped harmonic traveling wave during coalescence (like a plucked luminous filament settling).
      const w1 = Math.sin(theta * 2 + wavePhase) * 2.2 + Math.cos(theta * 3 - wavePhase * 1.3) * 1.0;
      const w2 = Math.cos(theta * 2 - wavePhase * 0.85) * 1.7;

      const x = (mix(hx, cx, mPos) + w2 * harmonicRipple) * scale;
      const y = (mix(hy, cy, mPos) + w1 * harmonicRipple) * scale;
      const z = (mix(hz, cz, mPos) + w2 * 0.7 * harmonicRipple) * scale + offsetZ;

      const idx = i * 3;
      pts[idx] = x;
      pts[idx + 1] = y;
      pts[idx + 2] = z;
    }

    this.computeBishopFrames();
  }

  private computeBishopFrames(): void {
    const N = TUBULAR_SEGMENTS;
    const pts = this.pts;
    const T = this.tangents;
    const Nm = this.normals;
    const B = this.binormals;

    // Central-difference tangents around the closed loop.
    for (let i = 0; i < N; i++) {
      const prev = ((i - 1 + N) % N) * 3;
      const next = ((i + 1) % N) * 3;
      let tx = pts[next] - pts[prev];
      let ty = pts[next + 1] - pts[prev + 1];
      let tz = pts[next + 2] - pts[prev + 2];
      const len = Math.hypot(tx, ty, tz) || 1;
      tx /= len;
      ty /= len;
      tz /= len;
      const idx = i * 3;
      T[idx] = tx;
      T[idx + 1] = ty;
      T[idx + 2] = tz;
    }
    T[N * 3] = T[0];
    T[N * 3 + 1] = T[1];
    T[N * 3 + 2] = T[2];

    // Initial normal N0 perpendicular to T0.
    const t0x = T[0];
    const t0y = T[1];
    const t0z = T[2];
    let rx = 0;
    let ry = 0;
    let rz = 1;
    if (Math.abs(t0z) > 0.88) {
      rx = 0;
      ry = 1;
      rz = 0;
    }
    const dot0 = rx * t0x + ry * t0y + rz * t0z;
    let nx = rx - dot0 * t0x;
    let ny = ry - dot0 * t0y;
    let nz = rz - dot0 * t0z;
    const nLen0 = Math.hypot(nx, ny, nz) || 1;
    nx /= nLen0;
    ny /= nLen0;
    nz /= nLen0;

    Nm[0] = nx;
    Nm[1] = ny;
    Nm[2] = nz;
    B[0] = t0y * nz - t0z * ny;
    B[1] = t0z * nx - t0x * nz;
    B[2] = t0x * ny - t0y * nx;

    // Parallel transport along i = 1..N.
    for (let i = 1; i <= N; i++) {
      const pIdx = (i - 1) * 3;
      const cIdx = i * 3;
      const ptx = T[pIdx];
      const pty = T[pIdx + 1];
      const ptz = T[pIdx + 2];
      const ctx = T[cIdx];
      const cty = T[cIdx + 1];
      const ctz = T[cIdx + 2];

      let pnx = Nm[pIdx];
      let pny = Nm[pIdx + 1];
      let pnz = Nm[pIdx + 2];

      // Axis of minimal rotation: cross(T_prev, T_curr)
      let ax = pty * ctz - ptz * cty;
      let ay = ptz * ctx - ptx * ctz;
      let az = ptx * cty - pty * ctx;
      const sinA = Math.hypot(ax, ay, az);
      if (sinA > 1e-6) {
        ax /= sinA;
        ay /= sinA;
        az /= sinA;
        const cosA = Math.max(-1, Math.min(1, ptx * ctx + pty * cty + ptz * ctz));
        const oneMinusC = 1 - cosA;
        // Rodrigues rotation of (pnx, pny, pnz) around unit axis (ax, ay, az)
        const kDotV = ax * pnx + ay * pny + az * pnz;
        const cxvX = ay * pnz - az * pny;
        const cxvY = az * pnx - ax * pnz;
        const cxvZ = ax * pny - ay * pnx;
        const rnx = pnx * cosA + cxvX * sinA + ax * kDotV * oneMinusC;
        const rny = pny * cosA + cxvY * sinA + ay * kDotV * oneMinusC;
        const rnz = pnz * cosA + cxvZ * sinA + az * kDotV * oneMinusC;
        pnx = rnx;
        pny = rny;
        pnz = rnz;
      }

      // Re-orthonormalize against T_curr.
      const d = pnx * ctx + pny * cty + pnz * ctz;
      pnx -= d * ctx;
      pny -= d * cty;
      pnz -= d * ctz;
      const l = Math.hypot(pnx, pny, pnz) || 1;
      pnx /= l;
      pny /= l;
      pnz /= l;

      Nm[cIdx] = pnx;
      Nm[cIdx + 1] = pny;
      Nm[cIdx + 2] = pnz;
      B[cIdx] = cty * pnz - ctz * pny;
      B[cIdx + 1] = ctz * pnx - ctx * pnz;
      B[cIdx + 2] = ctx * pny - cty * pnx;
    }

    // Close the tiny holonomy twist linearly so seam at i=0 / i=N is invisible.
    const endIdx = N * 3;
    const dotN = Nm[endIdx] * Nm[0] + Nm[endIdx + 1] * Nm[1] + Nm[endIdx + 2] * Nm[2];
    const dotB = Nm[endIdx] * B[0] + Nm[endIdx + 1] * B[1] + Nm[endIdx + 2] * B[2];
    const twistErr = Math.atan2(dotB, dotN);

    if (Math.abs(twistErr) > 1e-5) {
      for (let i = 1; i <= N; i++) {
        const idx = i * 3;
        const a = -twistErr * (i / N);
        const ca = Math.cos(a);
        const sa = Math.sin(a);
        const nx1 = Nm[idx] * ca + B[idx] * sa;
        const ny1 = Nm[idx + 1] * ca + B[idx + 1] * sa;
        const nz1 = Nm[idx + 2] * ca + B[idx + 2] * sa;
        const bx1 = -Nm[idx] * sa + B[idx] * ca;
        const by1 = -Nm[idx + 1] * sa + B[idx + 1] * ca;
        const bz1 = -Nm[idx + 2] * sa + B[idx + 2] * ca;
        Nm[idx] = nx1;
        Nm[idx + 1] = ny1;
        Nm[idx + 2] = nz1;
        B[idx] = bx1;
        B[idx + 1] = by1;
        B[idx + 2] = bz1;
      }
    }
  }

  writeToLayer(layer: TubeLayer, radius: number): void {
    const N = TUBULAR_SEGMENTS;
    const R = RADIAL_SEGMENTS;
    const pts = this.pts;
    const Nm = this.normals;
    const B = this.binormals;
    const outP = layer.positions;
    const outN = layer.normals;
    const cosT = this.cosTable;
    const sinT = this.sinTable;

    let v = 0;
    for (let i = 0; i <= N; i++) {
      const cIdx = i * 3;
      const px = pts[cIdx];
      const py = pts[cIdx + 1];
      const pz = pts[cIdx + 2];
      const nx = Nm[cIdx];
      const ny = Nm[cIdx + 1];
      const nz = Nm[cIdx + 2];
      const bx = B[cIdx];
      const by = B[cIdx + 1];
      const bz = B[cIdx + 2];

      for (let j = 0; j <= R; j++) {
        const c = cosT[j];
        const s = sinT[j];
        const vx = nx * c + bx * s;
        const vy = ny * c + by * s;
        const vz = nz * c + bz * s;

        outN[v] = vx;
        outN[v + 1] = vy;
        outN[v + 2] = vz;
        outP[v] = px + vx * radius;
        outP[v + 1] = py + vy * radius;
        outP[v + 2] = pz + vz * radius;
        v += 3;
      }
    }

    (layer.geometry.attributes.position as THREE.BufferAttribute).needsUpdate = true;
    (layer.geometry.attributes.normal as THREE.BufferAttribute).needsUpdate = true;
  }
}

export interface InfinityLoaderOptions {
  /**
   * "startup" = full audio-locked 14.16 s choreography (helix → turn → morph → lock → hold → dot → dissolve).
   * "waking"  = ~5.5 s continuous morph from infinity helix into a gently breathing ring (for Paper 03 Waking).
   */
  mode?: "startup" | "waking";
  /** Fixed square canvas size in CSS px; if omitted, scales responsively to viewport. */
  fixedSize?: number;
  /** Filament tint hex (defaults to OS1 warm white #fffdf9). */
  color?: number;
  /** Optional hook to read live playback time (in seconds from audio start) for 0ms drift sync. */
  getAudioTime?: () => number | null;
  /** Optional hook to read live normalized audio energy (0..1) from an AnalyserNode. */
  getAudioEnergy?: () => number;
  /** Optional callback receiving ambient glow intensity (0..1) so the coral backdrop can breathe with the ring. */
  onGlowChange?: (intensity: number) => void;
}

/**
 * Cinema-grade 3D OS1 infinity-helix → ring WebGL renderer.
 *
 * Uses a single continuous closed 3D parametric curve with rotation-minimizing (Bishop)
 * frames, custom filmic Fresnel/depth shaders, a volumetric glow halo, and a gossamer
 * harmonic echo filament that fuses seamlessly into the crisp white circle on the resolving chord.
 */
export class InfinityLoader {
  private readonly canvas: HTMLCanvasElement;
  private readonly mode: "startup" | "waking";
  private readonly fixedSize?: number;
  private readonly getAudioTime?: () => number | null;
  private readonly getAudioEnergy?: () => number;
  private readonly onGlowChange?: (intensity: number) => void;

  private readonly scene = new THREE.Scene();
  private readonly group = new THREE.Group();
  private readonly camera: THREE.PerspectiveCamera;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly builder = new TubeBuilder();

  private readonly coreLayer: TubeLayer;
  private readonly glowLayer: TubeLayer;
  private readonly echoLayer: TubeLayer;

  private isAnimating = false;
  private destroyed = false;
  private rafId: number | null = null;
  private transitionStartMs: number | null = null;
  private lastNowMs: number | null = null;
  private spinAngle = 0;
  private smoothEnergy = 0;
  private visualCompleteFired = false;
  private ringLockedFired = false;

  /** Fires once the ring locks on the resolving chord (startup: ~10.75 s into audio; waking: ~5.4 s). */
  public onRingLocked: (() => void) | null = null;
  /** Fires once the full visual sequence (collapse to dot + dissolve) finishes in startup mode. */
  public onComplete: (() => void) | null = null;

  constructor(canvas: HTMLCanvasElement, options: InfinityLoaderOptions = {}) {
    this.canvas = canvas;
    this.mode = options.mode ?? "startup";
    this.fixedSize = options.fixedSize;
    this.getAudioTime = options.getAudioTime;
    this.getAudioEnergy = options.getAudioEnergy;
    this.onGlowChange = options.onGlowChange;

    const tint = new THREE.Color(options.color ?? 0xfffdf9);
    const warmGlow = new THREE.Color(0xffefe2);

    this.scene.add(this.group);
    this.camera = new THREE.PerspectiveCamera(42, 1, 1, 2000);
    this.camera.position.z = 148;

    this.coreLayer = createTubeLayer(
      new THREE.ShaderMaterial({
        vertexShader: VERTEX_SHADER,
        fragmentShader: CORE_FRAGMENT_SHADER,
        transparent: true,
        depthWrite: false,
        uniforms: {
          uColor: { value: tint },
          uOpacity: { value: 1 },
          uEnergy: { value: 0 },
          uMorph: { value: 0 },
          uTime: { value: 0 },
        },
      }),
    );

    this.glowLayer = createTubeLayer(
      new THREE.ShaderMaterial({
        vertexShader: VERTEX_SHADER,
        fragmentShader: GLOW_FRAGMENT_SHADER,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: {
          uColor: { value: warmGlow },
          uOpacity: { value: 0.34 },
          uEnergy: { value: 0 },
        },
      }),
    );

    this.echoLayer = createTubeLayer(
      new THREE.ShaderMaterial({
        vertexShader: VERTEX_SHADER,
        fragmentShader: CORE_FRAGMENT_SHADER,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: {
          uColor: { value: warmGlow },
          uOpacity: { value: 0.28 },
          uEnergy: { value: 0 },
          uMorph: { value: 0 },
          uTime: { value: 0 },
        },
      }),
    );

    this.group.add(this.glowLayer.mesh);
    this.group.add(this.echoLayer.mesh);
    this.group.add(this.coreLayer.mesh);

    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setClearColor(0x000000, 0);

    this.canvas.style.opacity = "0";
    this.resize();
    window.addEventListener("resize", this.handleResize);
  }

  private readonly handleResize = (): void => {
    this.resize();
  };

  resize(): void {
    if (this.destroyed) return;
    const size =
      this.fixedSize
        ? Math.min(this.fixedSize, Math.floor(window.innerWidth * 0.9))
        : Math.min(760, Math.max(260, Math.floor(Math.min(window.innerWidth * 0.92, window.innerHeight * 0.85))));
    this.canvas.style.width = `${size}px`;
    this.canvas.style.height = `${size}px`;
    this.renderer.setSize(size, size, false);
  }

  start(): void {
    if (this.isAnimating || this.destroyed) return;
    this.isAnimating = true;
    this.lastNowMs = null;
    this.canvas.style.transition = "opacity 0.6s cubic-bezier(0.22, 0.61, 0.36, 1)";
    this.canvas.style.opacity = "1";
    this.rafId = requestAnimationFrame(this.animate);
  }

  /** Begin the timed morph synced to audio t = 0 (or wall clock if no audio hook). */
  triggerTransition(): void {
    if (this.transitionStartMs === null) {
      this.transitionStartMs = performance.now();
    }
  }

  private readonly animate = (now: number): void => {
    if (!this.isAnimating || this.destroyed) return;

    const dt = this.lastNowMs === null ? 1 / 60 : Math.min(0.05, Math.max(0.001, (now - this.lastNowMs) / 1000));
    this.lastNowMs = now;

    // Smooth live audio energy (or synthetic breath when muted/waking).
    const rawEnergy = this.getAudioEnergy?.() ?? 0;
    this.smoothEnergy += (rawEnergy - this.smoothEnergy) * Math.min(1, dt * 10);

    if (this.mode === "waking") {
      this.stepWaking(now, dt);
    } else {
      this.stepStartup(now, dt);
    }

    this.renderer.render(this.scene, this.camera);
    this.rafId = requestAnimationFrame(this.animate);
  };

  /**
   * Startup choreography locked to `init_sound.mp3` (14.16 s), matching the original
   * OS-1 pacing & fast hypnotic twirl while keeping our smooth Bishop-frame continuous morph:
   *   pre-roll (< 0 s)   calm luminous infinity helix spinning (~2.1 rad/s)
   *   0.00 – 5.60 s      pure horizontal twirl accelerating steadily into high-speed spin (~2.1 → 34 rad/s)
   *   5.00 – 11.15 s     90° yaw into profile while spinning even faster (peaking ~44 rad/s),
   *                      then surging continuously ∞ → O and snapping dead-still on the resolving chord
   *   11.15 – 11.85 s    sudden calm: crisp luminous white ring holds across the chord climax
   *   11.85 – 12.60 s    graceful contraction to a luminous point of light as the chord drops
   *   12.50 – 13.25 s    silky dissolve into the coral field; reverb tail finishes at 14.16 s
   */
  private stepStartup(now: number, dt: number): void {
    const t =
      this.transitionStartMs === null
        ? -1
        : (this.getAudioTime?.() ?? (now - this.transitionStartMs) / 1000);

    // Original easeInOutQuad acceleration curve across the ~11.4 s build (hits 0.99 right at 11.15 s).
    const accel = t < 0 ? 0 : easeInOutQuad01(t / 11.4);

    // 1) Spin velocity: starts at 2.1 rad/s (0.035 rad/frame @ 60Hz), accelerates thrillingly up to
    //    ~44 rad/s during the fast twirl, and only damps cleanly right at the final ring lock (9.6–11.15 s).
    const spinDamp = t < 0 ? 1 : 1 - smootherstep(9.55, 11.12, t);
    const angularSpeed = (2.1 + 43.0 * accel) * spinDamp;
    this.spinAngle += angularSpeed * dt;

    // 2) Hold pure twirling helix longer (0–5.6 s), then surge decisively into the circle (5.6–11.15 s).
    const morphLinear = t < 0 ? 0 : smoothstep(5.6, 11.15, t);
    const morph = morphLinear ** 1.35;

    // 3) 90° Y-turn begins at ~5.0 s (original accel > 0.35) and completes right on the lock at 11.15 s.
    const yawProgress = t < 0 ? 0 : smootherstep(5.0, 11.05, t);
    const orbitChaos = t < 0 ? 0 : Math.sin(Math.PI * morphLinear) * (1 - morph * 0.85);
    this.group.rotation.y = (-Math.PI / 2) * yawProgress;
    this.group.rotation.x = Math.sin(t * 4.2 + this.spinAngle * 0.06) * 0.32 * orbitChaos;
    this.group.rotation.z = Math.cos(t * 3.4 + this.spinAngle * 0.04) * 0.24 * orbitChaos;

    // Dolly forward smoothly during the turn so the resolved ring matches Presence scale.
    const dolly = t < 0 ? 0 : smootherstep(5.0, 11.15, t);
    this.group.position.z = 24 * dolly;

    // 4) Sudden luminous stillness on the chord peak (11.15–11.85 s), then morphToDot (11.85–12.60 s) & fadeOut.
    const holdBreath =
      t >= 11.1 && t < 12.1
        ? 1 + 0.015 * Math.sin((t - 11.15) * 3.6) * smoothstep(11.1, 11.35, t) * (1 - smoothstep(11.8, 12.1, t))
        : 1;
    const collapse = t < 0 ? 0 : smootherstep(11.85, 12.62, t);
    const fadeOut = t < 0 ? 0 : smoothstep(12.5, 13.25, t);

    const ringRadius = 11.4;
    const scale = mix(1, 0.035, collapse) * holdBreath;
    const masterOpacity = 1 - fadeOut;

    // Filament thickness: delicate filmic infinity ribbon → crisp Presence-matched ring → luminous pinpoint.
    const coreRadius = mix(0.52, 0.44, morph) * mix(1, 0.48, collapse);
    const glowRadius =
      coreRadius * (3.0 + this.smoothEnergy * 0.95 + smoothstep(10.5, 11.4, t) * (1 - fadeOut) * 1.15);

    // Energetic harmonic ripple during the fast morph that damps cleanly into absolute stillness at 11.15 s.
    const waveAmp = 1.45 + this.smoothEnergy * 0.7;
    const wavePhase = Math.max(0, t) * 7.2;

    // Primary luminous filament + volumetric glow halo.
    this.builder.evaluateCurve(this.spinAngle, morph, waveAmp, wavePhase, ringRadius, scale);
    this.builder.writeToLayer(this.coreLayer, coreRadius);
    this.builder.writeToLayer(this.glowLayer, glowRadius);

    // Gossamer motion-trail echo filament: fans wider as the twirl speeds up (creating silky 35mm
    // persistence during the high-speed spin), then fuses cleanly into the pure circle at 11.15 s.
    const echoStrength = (1 - smoothstep(9.6, 11.12, t)) * masterOpacity;
    this.echoLayer.mesh.visible = echoStrength > 0.01;
    if (this.echoLayer.mesh.visible) {
      const lag = 0.2 + 0.58 * accel;
      const echoMorph = clamp01(morph * 0.9);
      this.builder.evaluateCurve(
        this.spinAngle - lag,
        echoMorph,
        waveAmp * 1.4,
        wavePhase - 0.6,
        ringRadius * (1 + 0.045 * (1 - morph)),
        scale,
      );
      this.builder.writeToLayer(this.echoLayer, coreRadius * 0.56);
    }

    // Update shader uniforms.
    const timeSec = now * 0.001;
    const energy = Math.max(this.smoothEnergy, t >= 10.6 && t <= 12.1 ? 0.58 : 0);

    this.coreLayer.material.uniforms.uOpacity.value = masterOpacity;
    this.coreLayer.material.uniforms.uEnergy.value = energy;
    this.coreLayer.material.uniforms.uMorph.value = morph;
    this.coreLayer.material.uniforms.uTime.value = timeSec;

    // Bloom surges warmly on the resolving chord climax and softly during collapse.
    const peakBloom = smoothstep(10.0, 11.25, t) * (1 - smoothstep(12.0, 13.15, t));
    this.glowLayer.material.uniforms.uOpacity.value = (0.3 + 0.28 * peakBloom) * masterOpacity;
    this.glowLayer.material.uniforms.uEnergy.value = energy;

    this.echoLayer.material.uniforms.uOpacity.value = (0.28 + 0.16 * accel) * echoStrength;
    this.echoLayer.material.uniforms.uEnergy.value = energy;
    this.echoLayer.material.uniforms.uMorph.value = morph;
    this.echoLayer.material.uniforms.uTime.value = timeSec;

    // Subtle sunlit coral aura swells into the chord climax.
    const backdropGlow =
      t < 0
        ? 0.06
        : (0.08 + 0.26 * smoothstep(2.5, 11.15, t) + 0.34 * peakBloom + 0.22 * energy) * masterOpacity;
    this.onGlowChange?.(clamp01(backdropGlow));

    if (t >= 11.15 && !this.ringLockedFired) {
      this.ringLockedFired = true;
      this.onRingLocked?.();
    }

    if (t >= 13.35 && !this.visualCompleteFired) {
      this.visualCompleteFired = true;
      this.onComplete?.();
    }
  }

  /**
   * Waking screen choreography (~5.5 s continuous morph from 3D infinity helix into
   * a calmly breathing luminous ring, matching Paper 03 Waking — Loop).
   */
  private stepWaking(now: number, dt: number): void {
    const t = this.transitionStartMs === null ? 0 : (now - this.transitionStartMs) / 1000;

    const accelBuild = smoothstep(0, 4.2, t);
    const spinDamp = 1 - smootherstep(3.6, 5.4, t);
    this.spinAngle += (1.5 + 6.5 * accelBuild * accelBuild) * spinDamp * dt;

    const morph = smootherstep(1.2, 5.4, t);
    const yawProgress = smootherstep(1.0, 5.2, t);
    const orbitTilt = Math.sin(Math.PI * yawProgress) * (1 - morph * 0.85);

    this.group.rotation.y = (-Math.PI / 2) * yawProgress;
    this.group.rotation.x = Math.sin(t * 2.2) * 0.2 * orbitTilt;
    this.group.rotation.z = Math.cos(t * 1.8) * 0.14 * orbitTilt;
    this.group.position.z = 18 * smootherstep(1.2, 5.4, t);

    const breathe = morph > 0.95 ? 1 + 0.022 * Math.sin((t - 5.4) * 2.2) : 1;
    const ringRadius = 11.4;

    this.builder.evaluateCurve(this.spinAngle, morph, 1.0, t * 4.2, ringRadius, breathe);
    this.builder.writeToLayer(this.coreLayer, mix(0.52, 0.44, morph));
    this.builder.writeToLayer(this.glowLayer, mix(1.55, 1.65, morph));

    const echoStrength = 1 - smoothstep(3.8, 5.3, t);
    this.echoLayer.mesh.visible = echoStrength > 0.01;
    if (this.echoLayer.mesh.visible) {
      this.builder.evaluateCurve(this.spinAngle - 0.3, clamp01(morph * 0.9), 1.3, t * 4.2 - 0.5, ringRadius, breathe);
      this.builder.writeToLayer(this.echoLayer, 0.26);
    }

    const timeSec = now * 0.001;
    this.coreLayer.material.uniforms.uOpacity.value = 1;
    this.coreLayer.material.uniforms.uEnergy.value = 0.2 + 0.18 * morph;
    this.coreLayer.material.uniforms.uMorph.value = morph;
    this.coreLayer.material.uniforms.uTime.value = timeSec;

    this.glowLayer.material.uniforms.uOpacity.value = 0.32 + 0.16 * morph;
    this.glowLayer.material.uniforms.uEnergy.value = 0.25;

    this.echoLayer.material.uniforms.uOpacity.value = 0.3 * echoStrength;
    this.echoLayer.material.uniforms.uMorph.value = morph;
    this.echoLayer.material.uniforms.uTime.value = timeSec;

    if (t >= 5.4 && !this.ringLockedFired) {
      this.ringLockedFired = true;
      this.onRingLocked?.();
    }
  }

  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.isAnimating = false;
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    window.removeEventListener("resize", this.handleResize);
    for (const layer of [this.coreLayer, this.glowLayer, this.echoLayer]) {
      layer.geometry.dispose();
      layer.material.dispose();
    }
    this.renderer.dispose();
    this.scene.clear();
  }
}
