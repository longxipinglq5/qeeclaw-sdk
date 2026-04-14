import type { HttpClient } from "../client/http-client.js";

export interface VoiceTranscriptionRequest {
  file: Blob | Uint8Array | ArrayBuffer;
  filename?: string;
  contentType?: string;
  language?: string;
  model?: string;
}

export interface VoiceTranscriptionResult {
  text: string;
  language: string;
  duration: number;
}

export interface VoiceSynthesisRequest {
  text: string;
  voice?: string;
  speed?: number;
}

export interface SpeechSynthesisRequest {
  text: string;
  voice?: string;
  model?: string;
  responseFormat?: "mp3" | "wav" | "opus" | "pcm";
}

export interface VoiceAudioPayload {
  audio: Uint8Array;
  contentType: string;
  filename: string;
}

function buildBlob(
  value: Blob | Uint8Array | ArrayBuffer,
  contentType?: string,
): Blob {
  if (typeof Blob !== "undefined" && value instanceof Blob) {
    return value;
  }
  return new Blob([value as unknown as BlobPart], {
    type: contentType ?? "application/octet-stream",
  });
}

function inferSpeechContentType(format: SpeechSynthesisRequest["responseFormat"]): string {
  switch (format) {
    case "wav":
      return "audio/wav";
    case "opus":
      return "audio/opus";
    case "pcm":
      return "audio/pcm";
    case "mp3":
    default:
      return "audio/mpeg";
  }
}

function inferExtension(contentType: string, fallback: string): string {
  if (contentType.includes("audio/wav")) {
    return "wav";
  }
  if (contentType.includes("audio/opus")) {
    return "opus";
  }
  if (contentType.includes("audio/ogg")) {
    return "ogg";
  }
  if (contentType.includes("audio/pcm")) {
    return "pcm";
  }
  if (contentType.includes("audio/mpeg")) {
    return "mp3";
  }
  return fallback;
}

function parseFilename(contentDisposition: string | null): string | undefined {
  if (!contentDisposition) {
    return undefined;
  }
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) {
    return decodeURIComponent(utf8Match[1]);
  }
  const quotedMatch = contentDisposition.match(/filename="([^"]+)"/i);
  if (quotedMatch) {
    return quotedMatch[1];
  }
  const plainMatch = contentDisposition.match(/filename=([^;]+)/i);
  if (plainMatch) {
    return plainMatch[1].trim();
  }
  return undefined;
}

export class VoiceModule {
  constructor(private readonly http: HttpClient) {}

  async transcribe(payload: VoiceTranscriptionRequest): Promise<VoiceTranscriptionResult> {
    const form = new FormData();
    form.set("file", buildBlob(payload.file, payload.contentType), payload.filename ?? "audio.wav");
    form.set("language", payload.language ?? "auto");
    if (payload.model) {
      form.set("model", payload.model);
    }

    return this.http.request<VoiceTranscriptionResult>({
      method: "POST",
      path: "/api/asr",
      body: form,
    });
  }

  async synthesize(payload: VoiceSynthesisRequest): Promise<VoiceAudioPayload> {
    const response = await this.http.requestBinaryResponse({
      method: "POST",
      path: "/api/tts",
      body: {
        text: payload.text,
        voice: payload.voice,
        speed: payload.speed ?? 1,
      },
    });
    const contentType = response.contentType || "audio/mpeg";
    return {
      audio: response.data,
      contentType,
      filename: parseFilename(response.contentDisposition) ?? `tts.${inferExtension(contentType, "mp3")}`,
    };
  }

  async speech(payload: SpeechSynthesisRequest): Promise<VoiceAudioPayload> {
    const responseFormat = payload.responseFormat ?? "mp3";
    const response = await this.http.requestBinaryResponse({
      method: "POST",
      path: "/api/audio/speech",
      body: {
        text: payload.text,
        voice: payload.voice,
        model: payload.model ?? "tts-1",
        response_format: responseFormat,
      },
    });
    const contentType = response.contentType || inferSpeechContentType(responseFormat);
    return {
      audio: response.data,
      contentType,
      filename:
        parseFilename(response.contentDisposition) ??
        `speech.${inferExtension(contentType, responseFormat)}`,
    };
  }
}
