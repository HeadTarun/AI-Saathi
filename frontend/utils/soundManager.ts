"use client";

export type SoundName = "click" | "success" | "error" | "levelup" | "streak";

type SoundState = {
  isMuted: boolean;
  volume: number;
  isInitialized: boolean;
};

const soundSources: Record<SoundName, string> = {
  click: "/sounds/click.mp3",
  success: "/sounds/success.mp3",
  error: "/sounds/error.mp3",
  levelup: "/sounds/levelup.mp3",
  streak: "/sounds/streak.mp3",
};

const synthSettings: Record<SoundName, { frequency: number; duration: number; type: OscillatorType }> = {
  click: { frequency: 330, duration: 0.075, type: "square" },
  success: { frequency: 740, duration: 0.12, type: "triangle" },
  error: { frequency: 180, duration: 0.16, type: "sawtooth" },
  levelup: { frequency: 920, duration: 0.22, type: "triangle" },
  streak: { frequency: 660, duration: 0.18, type: "square" },
};

class SoundManager {
  private sounds: Partial<Record<SoundName, HTMLAudioElement>> = {};
  private isMuted = false;
  private volume = 0.72;
  private isInitialized = false;
  private audioContext: AudioContext | null = null;

  init() {
    if (this.isInitialized || typeof window === "undefined") {
      return;
    }

    const storedMuted = window.localStorage.getItem("aiTutorSoundMuted");
    const storedVolume = window.localStorage.getItem("aiTutorSoundVolume");

    this.isMuted = storedMuted === "true";
    this.volume = storedVolume ? this.clampVolume(Number(storedVolume)) : this.volume;

    this.sounds = Object.entries(soundSources).reduce<Partial<Record<SoundName, HTMLAudioElement>>>(
      (registry, [name, source]) => {
        const audio = new Audio(source);
        audio.preload = "auto";
        audio.volume = this.volume;
        registry[name as SoundName] = audio;
        return registry;
      },
      {},
    );

    this.isInitialized = true;
    this.emitStateChange();
  }

  play(name: SoundName) {
    if (this.isMuted || typeof window === "undefined") {
      return;
    }

    if (!this.isInitialized) {
      this.init();
    }

    const sound = this.sounds[name];

    if (!sound) {
      this.playSynth(name);
      return;
    }

    sound.currentTime = 0;
    sound.volume = this.volume;
    void sound.play().catch(() => {
      this.playSynth(name);
    });
  }

  stop(name: SoundName) {
    const sound = this.sounds[name];

    if (!sound) {
      return;
    }

    sound.pause();
    sound.currentTime = 0;
  }

  mute() {
    this.isMuted = true;
    this.persist();
    this.emitStateChange();
  }

  unmute() {
    this.isMuted = false;
    this.persist();
    this.emitStateChange();
  }

  toggleMute() {
    if (this.isMuted) {
      this.unmute();
      return;
    }

    this.mute();
  }

  setVolume(value: number) {
    this.volume = this.clampVolume(value);

    Object.values(this.sounds).forEach((sound) => {
      if (sound) {
        sound.volume = this.volume;
      }
    });

    this.persist();
    this.emitStateChange();
  }

  getState(): SoundState {
    return {
      isMuted: this.isMuted,
      volume: this.volume,
      isInitialized: this.isInitialized,
    };
  }

  subscribe(callback: (state: SoundState) => void) {
    if (typeof window === "undefined") {
      return () => undefined;
    }

    const handler = () => callback(this.getState());
    window.addEventListener("sound-manager-state", handler);
    return () => window.removeEventListener("sound-manager-state", handler);
  }

  private playSynth(name: SoundName) {
    if (typeof window === "undefined") {
      return;
    }

    const AudioContextConstructor = window.AudioContext || window.webkitAudioContext;

    if (!AudioContextConstructor) {
      return;
    }

    this.audioContext ??= new AudioContextConstructor();

    const settings = synthSettings[name];
    const now = this.audioContext.currentTime;

    if (name === "click") {
      this.playBlockClick(now);
      return;
    }

    const oscillator = this.audioContext.createOscillator();
    const gain = this.audioContext.createGain();

    oscillator.type = settings.type;
    oscillator.frequency.setValueAtTime(settings.frequency, now);
    gain.gain.setValueAtTime(Math.max(this.volume * 0.18, 0.01), now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + settings.duration);

    oscillator.connect(gain);
    gain.connect(this.audioContext.destination);
    oscillator.start(now);
    oscillator.stop(now + settings.duration);
  }

  private playBlockClick(now: number) {
    if (!this.audioContext) {
      return;
    }

    [330, 220].forEach((frequency, index) => {
      const oscillator = this.audioContext!.createOscillator();
      const gain = this.audioContext!.createGain();
      const start = now + index * 0.028;
      const duration = 0.055;

      oscillator.type = "square";
      oscillator.frequency.setValueAtTime(frequency, start);
      oscillator.frequency.exponentialRampToValueAtTime(Math.max(frequency * 0.72, 1), start + duration);
      gain.gain.setValueAtTime(Math.max(this.volume * (index === 0 ? 0.16 : 0.1), 0.01), start);
      gain.gain.exponentialRampToValueAtTime(0.001, start + duration);

      oscillator.connect(gain);
      gain.connect(this.audioContext!.destination);
      oscillator.start(start);
      oscillator.stop(start + duration);
    });
  }

  private persist() {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem("aiTutorSoundMuted", String(this.isMuted));
    window.localStorage.setItem("aiTutorSoundVolume", String(this.volume));
  }

  private emitStateChange() {
    if (typeof window === "undefined") {
      return;
    }

    window.dispatchEvent(new Event("sound-manager-state"));
  }

  private clampVolume(value: number) {
    if (Number.isNaN(value)) {
      return 0.72;
    }

    return Math.min(1, Math.max(0, value));
  }
}

declare global {
  interface Window {
    webkitAudioContext?: typeof AudioContext;
  }
}

const soundManager = new SoundManager();

export default soundManager;
