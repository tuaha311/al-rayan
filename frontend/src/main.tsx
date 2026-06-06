import { createRoot } from "react-dom/client";
import Hero from "./Hero";

const heroEl = document.getElementById("hero-root");
if (heroEl) {
  createRoot(heroEl).render(<Hero />);
}
