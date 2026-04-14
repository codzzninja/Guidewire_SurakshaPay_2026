import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";
import { AuthProvider } from "./lib/AuthContext";
import { NotificationProvider } from "./lib/NotificationContext";
import { ToastProvider } from "./lib/Toast";
import App from "./App";
import "./index.css";

registerSW({ immediate: true });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <NotificationProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </NotificationProvider>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>
);
