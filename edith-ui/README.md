# EDITH Presence UI v3

A transparent-first holographic presence concept: 70% precision JARVIS engineering core, 30% organic energy intelligence.

## Preview
```powershell
npm install
npm run dev
```
Open the Vite URL with `?preview` to cycle through Listening, Thinking, Speaking and Sleeping. Preview mode uses simulated audio levels and does not connect to the Python voice engine.

## Production build
```powershell
npm run build
```
The build writes to `edith-ui/dist`. The Python host loads `dist/index.html` from this package directory, so no separate copy step is needed in the standard repository layout.

Read `INTEGRATION.md` before changing the existing pywebview host or Python stream loop. The frontend preserves the existing `window.edithSetState` bridge and adds response/audio-level bridges.

For the complete architecture, state lifecycle, component, bridge, build, and troubleshooting guide, see [`docs/EDITH_UI_Technical_Documentation.md`](../docs/EDITH_UI_Technical_Documentation.md). The subsystem document index is [`docs/README.md`](../docs/README.md).
