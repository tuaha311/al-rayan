"use client"
import "@mux/mux-video"
import { useEffect, useRef } from "react"
import { PulsingBorder } from "@paper-design/shaders-react"
import { motion } from "framer-motion"
import Navbar from "./Navbar"

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "mux-video": React.DetailedHTMLProps<React.VideoHTMLAttributes<HTMLVideoElement> & {
        "playback-id"?: string
        "env-key"?: string
        "stream-type"?: string
        "preload"?: string
        "playsinline"?: boolean
      }, HTMLElement>
    }
  }
}

export default function Hero() {
  const videoRef = useRef<HTMLVideoElement | null>(null)

  useEffect(() => {
    const el = videoRef.current
    if (!el) return

    // Muted autoplay is allowed by browsers, but the Mux web component does
    // not reliably start on its own, so force it once the media is ready.
    const startPlayback = () => {
      el.muted = true
      const attempt = el.play()
      if (attempt) attempt.catch(() => { })
    }

    startPlayback()
    el.addEventListener("loadedmetadata", startPlayback)
    el.addEventListener("canplay", startPlayback)
    return () => {
      el.removeEventListener("loadedmetadata", startPlayback)
      el.removeEventListener("canplay", startPlayback)
    }
  }, [])

  return (
    // min-h-screen is 100vh, which on mobile browsers is the *expanded* height:
    // the hero ends up taller than the visible area until the URL bar hides.
    // dvh tracks the real viewport, with vh kept as the fallback.
    <div className="min-h-screen min-h-[100dvh] bg-black relative overflow-hidden">
      <svg className="absolute inset-0 w-0 h-0">
        <defs>
          <filter id="glass-effect" x="-50%" y="-50%" width="200%" height="200%">
            <feTurbulence baseFrequency="0.005" numOctaves="1" result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="0.3" />
            <feColorMatrix
              type="matrix"
              values="1 0 0 0 0.02
                      0 1 0 0 0.02
                      0 0 1 0 0.05
                      0 0 0 0.9 0"
              result="tint"
            />
          </filter>
          <filter id="gooey-filter" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur" />
            <feColorMatrix
              in="blur"
              mode="matrix"
              values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 19 -9"
              result="gooey"
            />
            <feComposite in="SourceGraphic" in2="gooey" operator="atop" />
          </filter>
          <filter id="logo-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="logo-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#06b6d4" />
            <stop offset="50%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#0891b2" />
          </linearGradient>
          <linearGradient id="hero-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="30%" stopColor="#06b6d4" />
            <stop offset="70%" stopColor="#f97316" />
            <stop offset="100%" stopColor="#ffffff" />
          </linearGradient>
          <filter id="text-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
      </svg>

      {/* Background video via Mux */}
      <mux-video
        ref={videoRef as React.Ref<HTMLVideoElement>}
        class="absolute inset-0 w-full h-full z-0"
        playback-id="2GYtfHlR5hdTtDfbGSoR9CFRCz302MoC83bRE00UYZxjQ"
        env-key="12c5bppfmqsecd3d1jjc5umt6"
        stream-type="on-demand"
        preload="auto"
        loop
        muted
        playsinline
        style={{ display: "block", "--media-object-fit": "cover" } as React.CSSProperties}
      />
      {/* Scrim for text legibility */}
      <div className="absolute inset-0 z-0 bg-black/40" />

      <Navbar />

      <main className="absolute bottom-4 left-4 sm:bottom-8 sm:left-8 z-20 max-w-2xl">

      </main>

      <div className="absolute bottom-4 right-4 sm:bottom-8 sm:right-8 z-30">
        <div className="relative w-16 h-16 sm:w-20 sm:h-20 flex items-center justify-center">
          <PulsingBorder
            colors={["#06b6d4", "#0891b2", "#f97316", "#00FF88", "#FFD700", "#FF6B35", "#ffffff"]}
            colorBack="#00000000"
            speed={1.5}
            roundness={1}
            thickness={0.1}
            softness={0.2}
            intensity={5}
            spotsPerColor={5}
            spotSize={0.1}
            pulse={0.1}
            smoke={0.5}
            smokeSize={4}
            scale={0.65}
            rotation={0}
            frame={9161408.251009725}
            style={{
              width: "60px",
              height: "60px",
              borderRadius: "50%",
            }}
          />

          {/* Rotating Text Around the Pulsing Border */}
          <motion.svg
            className="absolute inset-0 w-full h-full"
            viewBox="0 0 100 100"
            animate={{ rotate: 360 }}
            transition={{
              duration: 20,
              repeat: Number.POSITIVE_INFINITY,
              ease: "linear",
            }}
            style={{ transform: "scale(1.6)" }}
          >
            <defs>
              <path id="circle" d="M 50, 50 m -38, 0 a 38,38 0 1,1 76,0 a 38,38 0 1,1 -76,0" />
            </defs>
            <text className="text-sm fill-white/80 font-medium">
              <textPath href="#circle" startOffset="0%">
                • XECOTECH • Smart • Swift • Secure • Smart • Swift • Secure • XECOTECH •
              </textPath>
            </text>
          </motion.svg>
        </div>
      </div>

    </div>
  )
}
