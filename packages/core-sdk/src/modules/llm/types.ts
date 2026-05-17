/**
 * OpenAI-compatible types for chat completions, image generation, and video generation.
 */

// ---------------------------------------------------------------------------
// Chat Completions
// ---------------------------------------------------------------------------

export interface ChatCompletionMessage {
  role: "system" | "user" | "assistant" | "tool";
  content?: string | ChatCompletionContentPart[];
  name?: string;
  tool_call_id?: string;
  tool_calls?: ChatCompletionToolCall[];
}

export interface ChatCompletionContentPart {
  type: "text" | "image_url";
  text?: string;
  image_url?: { url: string; detail?: "auto" | "low" | "high" };
}

export interface ChatCompletionToolCall {
  id: string;
  type: "function";
  function: { name: string; arguments: string };
}

export interface ChatCompletionCreateParams {
  model: string;
  messages: ChatCompletionMessage[];
  temperature?: number;
  top_p?: number;
  n?: number;
  stream?: boolean;
  stream_options?: { include_usage?: boolean };
  stop?: string | string[];
  max_tokens?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
  logit_bias?: Record<string, number>;
  user?: string;
  tools?: ChatCompletionTool[];
  tool_choice?: "none" | "auto" | "required" | { type: "function"; function: { name: string } };
  parallel_tool_calls?: boolean;
  response_format?: { type: "text" | "json_object" | "json_schema"; json_schema?: unknown };
  seed?: number;
  extra?: Record<string, unknown>;
}

export interface ChatCompletionTool {
  type: "function";
  function: { name: string; description?: string; parameters?: unknown };
}

export interface ChatCompletionChoice {
  index: number;
  message: ChatCompletionMessage;
  finish_reason: "stop" | "length" | "tool_calls" | "content_filter" | string;
  logprobs?: unknown;
}

export interface ChatCompletionUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatCompletion {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatCompletionChoice[];
  usage?: ChatCompletionUsage;
}

// ---------------------------------------------------------------------------
// Images
// ---------------------------------------------------------------------------

export interface ImageGenerateParams {
  model: string;
  prompt: string;
  n?: number;
  size?: string;
  quality?: string;
  response_format?: "url" | "b64_json";
  user?: string;
  stream?: boolean;
  extra?: Record<string, unknown>;
}

export interface ImageData {
  url?: string;
  b64_json?: string;
  revised_prompt?: string;
}

export interface ImageGenerateResult {
  created?: number;
  data: ImageData[];
  usage?: unknown;
}

// ---------------------------------------------------------------------------
// Videos
// ---------------------------------------------------------------------------

export interface VideoGenerateParams {
  model: string;
  prompt: string;
  n?: number;
  size?: string;
  duration?: number;
  fps?: number;
  response_format?: "url" | "b64_json";
  user?: string;
  extra?: Record<string, unknown>;
}

export interface VideoData {
  url?: string;
  b64_json?: string;
  duration?: number;
}

export interface VideoGenerateResult {
  created?: number;
  data: VideoData[];
  usage?: unknown;
}
