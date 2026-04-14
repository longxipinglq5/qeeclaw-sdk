declare namespace NodeJS {
  interface ProcessEnv {
    [key: string]: string | undefined;
  }
}

declare class Buffer {
  toString(encoding?: string): string;
  static from(data: string | ArrayBuffer | ArrayLike<number> | null | undefined): Buffer;
  static concat(chunks: readonly Buffer[]): Buffer;
  static isBuffer(value: unknown): value is Buffer;
}

declare const process: {
  argv: string[];
  env: NodeJS.ProcessEnv;
  execPath: string;
  exitCode?: number;
  cwd(): string;
  kill(pid: number, signal?: string | number): void;
  stdout: {
    write(chunk: string): void;
  };
  stderr: {
    write(chunk: string): void;
  };
};

declare module "node:fs" {
  export function existsSync(path: string): boolean;
}

declare module "node:os" {
  const os: {
    homedir(): string;
    hostname(): string;
    platform(): string;
    release(): string;
  };
  export default os;
}

declare module "node:path" {
  const path: {
    resolve(...parts: string[]): string;
    join(...parts: string[]): string;
    dirname(input: string): string;
    relative(from: string, to: string): string;
    extname(input: string): string;
  };
  export default path;
}

declare module "node:crypto" {
  const crypto: {
    randomUUID(): string;
    randomBytes(size: number): {
      toString(encoding?: string): string;
    };
  };
  export default crypto;
}

declare module "node:child_process" {
  export function spawn(
    command: string,
    args?: readonly string[],
    options?: {
      detached?: boolean;
      stdio?: unknown;
      env?: Record<string, string | undefined>;
    },
  ): {
    pid?: number;
    unref(): void;
  };
}

declare module "node:fs/promises" {
  export interface Dirent {
    name: string;
    isDirectory(): boolean;
    isFile(): boolean;
  }

  export interface FileStat {
    size: number;
    mtime: Date;
  }

  export function access(path: string): Promise<void>;
  export function mkdir(path: string, options?: { recursive?: boolean }): Promise<void>;
  export function readFile(path: string, encoding: "utf8"): Promise<string>;
  export function writeFile(path: string, content: string): Promise<void>;
  export function rm(path: string, options?: { force?: boolean }): Promise<void>;
  export function stat(path: string): Promise<FileStat>;
  export function readdir(path: string, options: { withFileTypes: true }): Promise<Dirent[]>;
}

declare module "node:http" {
  namespace http {
    interface IncomingMessage extends AsyncIterable<unknown> {
      method?: string;
      url?: string;
      headers: Record<string, string | undefined>;
    }

    interface ServerResponse {
      statusCode: number;
      setHeader(name: string, value: string): void;
      end(chunk?: string): void;
    }

    interface Server {
      listen(port: number, host: string, callback?: () => void): void;
      close(callback: (error?: Error | null) => void): void;
      once(event: string, listener: (error: Error) => void): void;
      removeListener(event: string, listener: (error: Error) => void): void;
    }
  }

  function createServer(
    handler: (request: http.IncomingMessage, response: http.ServerResponse) => void | Promise<void>,
  ): http.Server;

  const http: {
    createServer: typeof createServer;
  };

  export default http;
}
