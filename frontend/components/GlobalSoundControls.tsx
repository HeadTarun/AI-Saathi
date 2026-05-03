"use client";

import { useEffect, useState } from "react";
import soundManager, { SoundName } from "@/utils/soundManager";

export default function GlobalSoundControls() {
  const [soundState, setSoundState] = useState(soundManager.getState());

  useEffect(() => {
    const unsubscribe = soundManager.subscribe(setSoundState);
    soundManager.init();

    return unsubscribe;
  }, []);

  useEffect(() => {
    function handleSoundClick(event: MouseEvent) {
      const target = event.target;

      if (!(target instanceof Element)) {
        return;
      }

      const soundTarget = target.closest<HTMLElement>("[data-sound], button, a");

      if (!soundTarget) {
        return;
      }

      const soundName = (soundTarget.dataset.sound as SoundName | undefined) ?? "click";

      if (!soundName) {
        return;
      }

      soundManager.play(soundName);
    }

    window.addEventListener("click", handleSoundClick);
    return () => window.removeEventListener("click", handleSoundClick);
  }, []);

  return (
    <aside className="sound-controls" aria-label="Global sound controls">
      <button
        className="sound-toggle"
        type="button"
        aria-pressed={soundState.isMuted}
        aria-label={soundState.isMuted ? "Unmute sounds" : "Mute sounds"}
        onClick={() => soundManager.toggleMute()}
      >
        <span aria-hidden="true">{soundState.isMuted ? "OFF" : "ON"}</span>
      </button>
      <label className="sound-volume">
        <span>Sound</span>
        <input
          aria-label="Sound volume"
          max="1"
          min="0"
          step="0.05"
          type="range"
          value={soundState.volume}
          onChange={(event) => soundManager.setVolume(Number(event.target.value))}
        />
      </label>
    </aside>
  );
}
