/**
 * PCM16 audio capture from the microphone using AudioWorklet.
 *
 * Sends Int16Array chunks via onAudioData callback.
 */

const WORKLET_CODE = `
class PCM16Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.activeFrames = 0;
    this.silenceFrames = 0;
    this.threshold = 0.012;
    this.hangoverFrames = 10;
  }

  process(inputs) {
    const input = inputs[0];
    if (input && input[0]) {
      const float32 = input[0];
      let sumSquares = 0;
      for (let i = 0; i < float32.length; i++) {
        sumSquares += float32[i] * float32[i];
      }
      const rms = Math.sqrt(sumSquares / float32.length);
      if (rms >= this.threshold) {
        this.activeFrames = this.hangoverFrames;
      } else if (this.activeFrames > 0) {
        this.activeFrames--;
      } else {
        this.silenceFrames++;
        if (this.silenceFrames % 50 === 0) {
          this.port.postMessage({ type: "silence", rms });
        }
        return true;
      }
      this.silenceFrames = 0;
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage({ type: "audio", buffer: int16.buffer, rms }, [int16.buffer]);
    }
    return true;
  }
}
registerProcessor("pcm16-processor", PCM16Processor);
`;

export interface AudioCapture {
  start: () => Promise<void>;
  stop: () => void;
  isRecording: () => boolean;
}

export function createAudioCapture(
  onAudioData: (samples: number[]) => void
): AudioCapture {
  let audioContext: AudioContext | null = null;
  let workletNode: AudioWorkletNode | null = null;
  let silentGain: GainNode | null = null;
  let source: MediaStreamAudioSourceNode | null = null;
  let stream: MediaStream | null = null;
  let recording = false;

  async function start() {
    if (recording) return;

    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 24000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });

    audioContext = new AudioContext({ sampleRate: 24000 });

    const blob = new Blob([WORKLET_CODE], { type: "application/javascript" });
    const url = URL.createObjectURL(blob);
    await audioContext.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);

    source = audioContext.createMediaStreamSource(stream);
    workletNode = new AudioWorkletNode(audioContext, "pcm16-processor");
    silentGain = audioContext.createGain();
    silentGain.gain.value = 0;

    workletNode.port.onmessage = (e: MessageEvent) => {
      const message = e.data as { type?: string; buffer?: ArrayBuffer };
      if (message.type !== "audio" || !message.buffer) return;
      const int16 = new Int16Array(message.buffer);
      onAudioData(Array.from(int16));
    };

    source.connect(workletNode);
    workletNode.connect(silentGain);
    silentGain.connect(audioContext.destination);
    recording = true;
  }

  function stop() {
    recording = false;
    workletNode?.disconnect();
    silentGain?.disconnect();
    source?.disconnect();
    stream?.getTracks().forEach((t) => t.stop());
    audioContext?.close();
    workletNode = null;
    silentGain = null;
    source = null;
    stream = null;
    audioContext = null;
  }

  function isRecording() {
    return recording;
  }

  return { start, stop, isRecording };
}
