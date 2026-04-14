/**
 * RuntimeResolver — Runtime 选择与管理
 *
 * 根据用户配置选择合适的 RuntimeAdapter 实例。
 * 默认使用 Hermes Runtime，仅在显式指定时使用 OpenClaw。
 */

import type {
  RuntimeAdapter,
  RuntimeResolverOptions,
  RuntimeType,
  RuntimeHealthCheck,
  RuntimeInvokeRequest,
  RuntimeInvokeResult,
  RuntimeStreamChunk,
  RuntimeCapabilities,
} from "./types.js";

import { DEFAULT_RUNTIME } from "./types.js";

// ---------------------------------------------------------------------------
// Resolver
// ---------------------------------------------------------------------------

export class RuntimeResolver {
  private readonly options: RuntimeResolverOptions;
  private activeAdapter: RuntimeAdapter | null = null;
  private adapters: Map<RuntimeType, RuntimeAdapter> = new Map();

  constructor(options: RuntimeResolverOptions = {}) {
    this.options = options;
  }

  /**
   * 注册一个 RuntimeAdapter 实例。
   * 允许在运行时动态注册不同的 adapter 实现。
   */
  registerAdapter(adapter: RuntimeAdapter): void {
    this.adapters.set(adapter.type, adapter);
  }

  /**
   * 获取当前应该使用的 runtime 类型。
   * 优先级：用户配置 > 环境变量 > 默认值 (hermes)
   */
  getPreferredRuntime(): RuntimeType {
    // 1. 用户显式配置
    if (this.options.preferredRuntime) {
      return this.options.preferredRuntime;
    }

    // 2. 环境变量
    if (typeof process !== "undefined" && process.env?.QEECLAW_RUNTIME) {
      const envRuntime = process.env.QEECLAW_RUNTIME.toLowerCase().trim();
      if (envRuntime === "hermes" || envRuntime === "openclaw") {
        return envRuntime;
      }
    }

    // 3. 默认值
    return DEFAULT_RUNTIME;
  }

  /**
   * 获取指定类型的 adapter。
   * 如果未注册对应类型的 adapter，抛出错误。
   */
  getAdapter(type?: RuntimeType): RuntimeAdapter {
    const targetType = type ?? this.getPreferredRuntime();
    const adapter = this.adapters.get(targetType);

    if (!adapter) {
      const available = [...this.adapters.keys()].join(", ") || "none";
      throw new Error(
        `Runtime "${targetType}" is not registered. ` +
        `Available runtimes: ${available}. ` +
        (targetType === "openclaw"
          ? `OpenClaw runtime is optional — install with --with-openclaw flag.`
          : `Ensure the ${targetType} adapter is properly initialized.`),
      );
    }

    return adapter;
  }

  /**
   * 获取当前活跃的 adapter（已启动的）。
   * 如果尚未启动，会自动启动默认 adapter。
   */
  async getActiveAdapter(): Promise<RuntimeAdapter> {
    if (this.activeAdapter) {
      return this.activeAdapter;
    }

    const adapter = this.getAdapter();
    await adapter.start();
    this.activeAdapter = adapter;
    return adapter;
  }

  /**
   * 切换到指定的 runtime 类型。
   * 会停止当前活跃的 adapter 并启动新的。
   */
  async switchRuntime(type: RuntimeType): Promise<RuntimeAdapter> {
    const newAdapter = this.getAdapter(type);

    if (this.activeAdapter && this.activeAdapter.type !== type) {
      await this.activeAdapter.stop();
    }

    await newAdapter.start();
    this.activeAdapter = newAdapter;
    return newAdapter;
  }

  /** 便捷方法：健康检查 */
  async healthCheck(): Promise<RuntimeHealthCheck> {
    const adapter = await this.getActiveAdapter();
    return adapter.healthCheck();
  }

  /** 便捷方法：模型调用 */
  async invoke(request: RuntimeInvokeRequest): Promise<RuntimeInvokeResult> {
    const adapter = await this.getActiveAdapter();
    return adapter.invoke(request);
  }

  /** 便捷方法：流式调用（如果支持） */
  async *invokeStream(request: RuntimeInvokeRequest): AsyncIterable<RuntimeStreamChunk> {
    const adapter = await this.getActiveAdapter();
    if (!adapter.invokeStream) {
      throw new Error(`Runtime "${adapter.type}" does not support streaming.`);
    }
    yield* adapter.invokeStream(request);
  }

  /** 获取当前 runtime 的能力声明 */
  getCapabilities(): RuntimeCapabilities {
    const adapter = this.getAdapter();
    return adapter.getCapabilities();
  }

  /** 列出所有已注册的 runtime 类型 */
  listRegisteredRuntimes(): RuntimeType[] {
    return [...this.adapters.keys()];
  }

  /** 检查指定 runtime 是否已注册 */
  isRegistered(type: RuntimeType): boolean {
    return this.adapters.has(type);
  }

  /** 停止所有活跃 adapter 并清理资源 */
  async shutdown(): Promise<void> {
    if (this.activeAdapter) {
      await this.activeAdapter.stop();
      this.activeAdapter = null;
    }
  }
}
