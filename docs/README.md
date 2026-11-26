# EDITH Technical Documentation

These documents describe the major EDITH subsystems and their current
implementation. Repository source code and tests remain authoritative if
a document and the checked-out code differ.

## Subsystem guides

- [EDITH UI — Technical Architecture & Developer Guide](./EDITH_UI_Technical_Documentation.md)  
  React/Vite build, pywebview integration, JavaScript bridge, UI state
  lifecycle, spoken-phrase highlighting and scroll-follow, components,
  Canvas rendering, and troubleshooting.
- [EDITH Voice System — Technical Architecture & Developer Documentation](./EDITH_Voice_System_Technical_Documentation.md)  
  Microphone capture, wake-word flow, STT, conversation lifecycle, TTS
  coordination and playback progress, response timing, CPU denoising,
  wake-word noise gating, and troubleshooting.
- [EDITH Memory System — Technical Architecture, Data Flow & Debugging Guide](./EDITH_Memory_System_Technical_Documentation.md)  
  Conversation and structured memory, retrieval, persistence, and
  debugging guidance.

## Related UI package notes

- [`edith-ui/README.md`](../edith-ui/README.md) — quick build and preview
  instructions.
- [`edith-ui/INTEGRATION.md`](../edith-ui/INTEGRATION.md) — focused
  pywebview and overlay integration notes.

