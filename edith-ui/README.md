# EDITH Presence UI v3

A transparent-first holographic presence concept: 70% precision JARVIS engineering core, 30% organic energy intelligence.

## Preview
```powershell
npm install
npm run dev
```
Open the Vite URL with `?preview` to cycle through Listening, Thinking, Speaking and Sleeping.

## Production build
```powershell
npm run build
```
Copy the built `dist` into the existing EDITH UI deployment path.

Read `INTEGRATION.md` before changing the existing pywebview host or Python stream loop. The frontend preserves the existing `window.edithSetState` bridge and adds response/audio-level bridges.
