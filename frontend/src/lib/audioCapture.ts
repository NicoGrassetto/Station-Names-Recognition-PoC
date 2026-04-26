/**
 * PCM16 audio capture from the microphone using AudioWorklet.
 *
 * Sends Int16Array chunks via onAudioData callback.
 */

const WORKLET_CODE = `
class PCM16Processor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0]) {
      const float32 = input[0];
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(int16.buffer, [int16.buffer]);
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

    workletNode.port.onmessage = (e: MessageEvent) => {
      const int16 = new Int16Array(e.data as ArrayBuffer);
      onAudioData(Array.from(int16));
    };

    source.connect(workletNode);
    workletNode.connect(audioContext.destination);
    recording = true;
  }

  function stop() {
    recording = false;
    workletNode?.disconnect();
    source?.disconnect();
    stream?.getTracks().forEach((t) => t.stop());
    audioContext?.close();
    workletNode = null;
    source = null;
    stream = null;
    audioContext = null;
  }

  function isRecording() {
    return recording;
  }

  return { start, stop, isRecording };
}
