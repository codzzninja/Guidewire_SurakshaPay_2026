import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.devtrails.surakshapay",
  appName: "SurakshaPay",
  webDir: "dist",
  server: {
    // Needed for Android emulator calling backend on host machine.
    cleartext: true,
    // Avoid mixed-content blocking when API is plain HTTP on local/dev.
    androidScheme: "http",
  },
};

export default config;
