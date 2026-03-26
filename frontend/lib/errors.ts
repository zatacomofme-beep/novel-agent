"use client";

export type AppErrorCategory =
  | "network"
  | "auth"
  | "validation"
  | "not_found"
  | "conflict"
  | "permission"
  | "server"
  | "unknown";

export interface ClassifiedError {
  category: AppErrorCategory;
  userMessage: string;
  technicalMessage: string;
  isRetryable: boolean;
}

export function classifyError(error: unknown): ClassifiedError {
  const technicalMessage =
    error instanceof Error ? error.message : String(error);

  if (error instanceof TypeError && technicalMessage.includes("fetch")) {
    return {
      category: "network",
      userMessage: "网络连接失败，请检查您的网络设置后重试。",
      technicalMessage,
      isRetryable: true,
    };
  }

  if (technicalMessage.includes("Authentication required")) {
    return {
      category: "auth",
      userMessage: "登录已过期，请重新登录后继续。",
      technicalMessage,
      isRetryable: false,
    };
  }

  if (technicalMessage.includes("401")) {
    return {
      category: "auth",
      userMessage: "登录已过期，请重新登录后继续。",
      technicalMessage,
      isRetryable: false,
    };
  }

  if (technicalMessage.includes("403")) {
    return {
      category: "permission",
      userMessage: "您没有权限执行此操作。",
      technicalMessage,
      isRetryable: false,
    };
  }

  if (technicalMessage.includes("404") || technicalMessage.includes("not found")) {
    return {
      category: "not_found",
      userMessage: "请求的资源不存在或已被删除。",
      technicalMessage,
      isRetryable: false,
    };
  }

  if (technicalMessage.includes("409") || technicalMessage.includes("conflict")) {
    return {
      category: "conflict",
      userMessage: "操作冲突，请刷新页面后重试。",
      technicalMessage,
      isRetryable: true,
    };
  }

  if (technicalMessage.includes("422") || technicalMessage.includes("validation")) {
    return {
      category: "validation",
      userMessage: technicalMessage.replace(/^.*?: /, "").slice(0, 100),
      technicalMessage,
      isRetryable: false,
    };
  }

  if (technicalMessage.includes("500") || technicalMessage.includes("server error")) {
    return {
      category: "server",
      userMessage: "服务器内部错误，请稍后重试。",
      technicalMessage,
      isRetryable: true,
    };
  }

  if (technicalMessage.includes("ECONNREFUSED") || technicalMessage.includes("ENOTFOUND")) {
    return {
      category: "network",
      userMessage: "无法连接服务器，请检查网络或稍后重试。",
      technicalMessage,
      isRetryable: true,
    };
  }

  return {
    category: "unknown",
    userMessage: technicalMessage.slice(0, 100) || "发生未知错误，请刷新页面后重试。",
    technicalMessage,
    isRetryable: true,
  };
}

export function buildUserFriendlyError(error: unknown): string {
  const classified = classifyError(error);
  return classified.userMessage;
}