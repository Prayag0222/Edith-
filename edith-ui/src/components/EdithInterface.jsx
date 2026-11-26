import AudioVisualizer from "./AudioVisualizer.jsx";
import EdithOrb from "./EdithOrb.jsx";
import ResponseDisplay from "./ResponseDisplay.jsx";
import StatusIndicator from "./StatusIndicator.jsx";

export default function EdithInterface({ state, response, visible }) {
  return (
    <main
      className={`presence relative isolate flex h-full w-full items-center justify-between overflow-hidden px-6
        ${state.toLowerCase()}
        ${visible ? "is-visible" : "is-sleeping"}`}
    >
      {/* LEFT: Intelligence & Communication */}
      <section className="presence-copy z-10 flex flex-col justify-center">
        <StatusIndicator state={state} />
        <ResponseDisplay response={response} state={state} />
        <AudioVisualizer state={state} />
      </section>

      {/* RIGHT: Holographic Intelligence Core */}
      <section className="core-section z-10 flex flex-col items-center justify-center">
        <div className="core-wrap">
          <EdithOrb state={state} />
        </div>

        <div className="core-identity">
          <span className="core-identity-line" />
          <span>E.D.I.T.H</span>
          <span className="core-identity-line" />
        </div>
      </section>
    </main>
  );
}