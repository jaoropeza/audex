import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/global.css";
import App from "./App.jsx";
import { AuthProvider } from "./contexts/AuthContext.jsx";

import { initTWE, Ripple } from "tw-elements";
initTWE({ Ripple });

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>
);
