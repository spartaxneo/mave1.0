import { App, type Os1Config } from "@os1/ui";
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

declare global {
  interface Window {
    os1?: {
      config?: Os1Config;
      getConfig?: () => Promise<Os1Config>;
    };
  }
}

const FALLBACK_CONFIG: Os1Config = { orchestratorUrl: "http://127.0.0.1:3008" };

function Root() {
  const [config, setConfig] = useState<Os1Config | null>(() => window.os1?.config ?? (window.os1?.getConfig ? null : FALLBACK_CONFIG));

  useEffect(() => {
    if (config || !window.os1?.getConfig) return;
    let alive = true;
    void window.os1
      .getConfig()
      .then((c) => {
        if (alive) setConfig(c);
      })
      .catch(() => {
        if (alive) setConfig(FALLBACK_CONFIG);
      });
    return () => {
      alive = false;
    };
  }, [config]);

  if (!config) return null;
  return <App config={config} />;
}

// biome-ignore lint/style/noNonNullAssertion: root exists in index.html
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
