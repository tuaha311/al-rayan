"use client"
import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"

const LINKS = [
  { label: "Shop All", href: "/shop/" },
  { label: "Wash n Wear", href: "/shop/?fabric=wash-wear" },
  { label: "Cotton", href: "/shop/?fabric=cotton" },
  { label: "Boski", href: "/shop/?fabric=boski" },
  { label: "Latha", href: "/shop/?fabric=latha" },
  { label: "Karandi", href: "/shop/?fabric=karandi" },
  { label: "Embroidered", href: "/shop/?fabric=embroidered" },
  { label: "Sale", href: "/shop/?on_sale=1" },
]

function Logo() {
  return (
    <motion.a
      href="/"
      className="flex items-center gap-3 group cursor-pointer"
      whileHover={{ scale: 1.05 }}
      transition={{ type: "spring", stiffness: 400, damping: 10 }}
    >
      <img
        src="/images/logo-transparent.png"
        alt="XECOTECH logo"
        className="size-10 group-hover:drop-shadow-lg transition-all duration-300"
        style={{ filter: "url(#logo-glow)" }}
      />
      <span className="text-white font-semibold text-lg tracking-[0.2em] uppercase select-none">
        XECOTECH
      </span>
    </motion.a>
  )
}

function LoginButton() {
  return (
    <div id="gooey-btn" className="hidden relative flex items-center group" style={{ filter: "url(#gooey-filter)" }}>
      <button className="absolute right-0 px-2.5 py-2 rounded-full bg-white text-black font-normal text-xs transition-all duration-300 hover:bg-white/90 cursor-pointer h-8 flex items-center justify-center -translate-x-10 group-hover:-translate-x-19 z-0">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 17L17 7M17 7H7M17 7V17" />
        </svg>
      </button>
      <button className="px-6 py-2 rounded-full bg-white text-black font-normal text-xs transition-all duration-300 hover:bg-white/90 cursor-pointer h-8 flex items-center z-10">
        Login
      </button>
    </div>
  )
}

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80)
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <>
      <header
        className={`fixed top-0 left-0 right-0 w-full z-30 flex items-center justify-between p-6 transition-all duration-300 ${
          scrolled
            ? "bg-black/40 backdrop-blur-md border-b border-white/10"
            : "bg-transparent"
        }`}
      >
      <Logo />

      {/* Desktop navigation */}
      <nav className="hidden md:flex items-center space-x-2">
        {LINKS.map((link) => (
          <a
            key={link.label}
            href={link.href}
            className="text-white/80 hover:text-white text-xs font-light px-3 py-2 rounded-full hover:bg-white/10 transition-all duration-200"
          >
            {link.label}
          </a>
        ))}
      </nav>

      {/* Desktop login */}
      <div className="hidden md:block">
        <LoginButton />
      </div>

      {/* Mobile menu toggle */}
      <button
        type="button"
        className="md:hidden relative z-30 flex h-10 w-10 items-center justify-center rounded-full text-white hover:bg-white/10 transition-colors duration-200"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.8}>
          {open ? (
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 6l12 12M18 6L6 18" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M4 12h16M4 17h16" />
          )}
        </svg>
      </button>

      {/* Mobile dropdown */}
      <AnimatePresence>
        {open && (
          <motion.nav
            key="mobile-menu"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            // Capped and scrollable: eight links plus the login row overflow a
            // landscape phone otherwise.
            className="md:hidden absolute top-full right-4 left-4 mt-2 z-30 flex max-h-[calc(100dvh-6rem)] flex-col gap-1 overflow-y-auto rounded-2xl border border-white/10 bg-black/80 p-3 backdrop-blur-md"
          >
            {LINKS.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={() => setOpen(false)}
                className="rounded-xl px-4 py-3 text-sm font-light text-white/80 hover:bg-white/10 hover:text-white transition-all duration-200"
              >
                {link.label}
              </a>
            ))}
            <a
              href="#"
              onClick={() => setOpen(false)}
              className="hidden mt-1 rounded-full bg-white px-4 py-3 text-center text-sm font-medium text-black hover:bg-white/90 transition-colors duration-200"
            >
              Login
            </a>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
    </>
  )
}
