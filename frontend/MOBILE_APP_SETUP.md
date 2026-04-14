# Mobile App Setup (Capacitor)

This project is now wrapped as a real installable mobile app shell using Capacitor.

## 1) Build web bundle + sync native projects

```powershell
cd frontend
npm run mobile:sync
```

## 2) Android (Windows-friendly)

```powershell
cd frontend
npm run mobile:android
```

This opens Android Studio. Then:
- wait for Gradle sync
- choose emulator/device
- click Run

## 3) iOS (Mac only)

```bash
cd frontend
npm run mobile:ios
```

Open in Xcode and run on simulator/device.

## API base URL in mobile app

- Web uses `/api` proxy.
- Native app uses `http://10.0.2.2:8000` by default (Android emulator to host backend).
- Override anytime with:

```env
VITE_API_BASE=http://<your-ip>:8000
```

For real phones on same Wi-Fi, use your laptop LAN IP (not localhost).
