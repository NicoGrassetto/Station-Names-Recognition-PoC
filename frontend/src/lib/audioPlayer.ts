/**
 * PCM16 audio playback via Web Audio API.
 *
 * Accepts base64-encoded PCM16 chunks and queues them for gapless playback.
 */

export interface AudioPlayer {
  enqueue: (base64Audio: string) => void;
  interrupt: () => void;
  isPlaying: () => boolean;
}

export function createAudioPlayer(sampleRate = 24000): AudioPlayer {
  let audioContext: AudioContext | null = null;
  let nextStartTime = 0;
  let playing = false;
  const scheduledSources: AudioBufferSourceNode[] = [];

  function getContext(): AudioContext {
    if (!audioContext) {
      audioContext = new AudioContext({ sampleRate });
    }
    return audioContext;
  }

  function enqueue(base64Audio: string) {
    const ctx = getContext();
    const binaryStr = atob(base64Audio);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }
    const int16 = new Int16Array(bytes.buffer);

    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / (int16[i] < 0 ? 0x8000 : 0x7fff);
    }

    const buffer = ctx.createBuffer(1, float32.length, sampleRate);
    buffer.getChannelData(0).set(float32);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    const now = ctx.currentTime;
    const startAt = Math.max(now, nextStartTime);
    source.start(startAt);
    nextStartTime = startAt + buffer.duration;
    playing = true;
    scheduledSources.push(source);

    source.onended = () => {
      const idx = scheduledSources.indexOf(source);
      if (idx !== -1) scheduledSources.splice(idx, 1);
      if (scheduledSources.length === 0) playing = false;
    };
  }

  function interrupt() {
    for (const src of scheduledSources) {
      try {
        src.stop();
      } catch {
        // already stopped
      }
    }
    scheduledSources.length = 0;
    nextStartTime = 0;
    playing = false;
  }

  function isPlaying() {
    return playing;
  }

  return { enqueue, interrupt, isPlaying };
}
