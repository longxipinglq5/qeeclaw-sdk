export interface QeeClawErrorOptions {
  status?: number;
  code?: number | string;
  details?: unknown;
  cause?: unknown;
}

export class QeeClawError extends Error {
  readonly status?: number;
  readonly code?: number | string;
  readonly details?: unknown;

  constructor(message: string, options: QeeClawErrorOptions = {}) {
    super(message);
    this.name = "QeeClawError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
    if (options.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = options.cause;
    }
  }
}

export class QeeClawApiError extends QeeClawError {
  constructor(message: string, options: QeeClawErrorOptions = {}) {
    super(message, options);
    this.name = "QeeClawApiError";
  }
}

export class QeeClawTimeoutError extends QeeClawError {
  constructor(message: string, options: QeeClawErrorOptions = {}) {
    super(message, options);
    this.name = "QeeClawTimeoutError";
  }
}

export class QeeClawNotImplementedError extends QeeClawError {
  constructor(message: string, options: QeeClawErrorOptions = {}) {
    super(message, options);
    this.name = "QeeClawNotImplementedError";
  }
}
