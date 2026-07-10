import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/global.css";
import App from "./App.jsx";

// Initialize TW-Elements interactive components (ripple on buttons)
import { initTWE, Ripple } from "tw-elements";
initTWE({ Ripple });

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
