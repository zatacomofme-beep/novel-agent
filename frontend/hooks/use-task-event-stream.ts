"use client";

import { useEffect, useMemo, useRef } from "react";

import { buildApiWebSocketUrl } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { TaskState } from "@/types/api";

type TaskEventStreamMessage =
  | {
      type: "subscribed";
      task_ids: string[];
      project_ids: string[];
    }
  | {
      type: "task_state";
      task: TaskState;
    };

type UseTaskEventStreamOptions = {
  enabled?: boolean;
  projectIds?: Array<string | null | undefined>;
  taskIds?: Array<string | null | undefined>;
  onTaskState: (task: TaskState) => void;
};

function normalizeSubscriptionIds(values: Array<string | null | undefined>): string[] {
  const uniqueValues = new Set<string>();
  for (const value of values) {
    const normalized = value?.trim();
    if (!normalized) {
      continue;
    }
    uniqueValues.add(normalized);
  }
  return Array.from(uniqueValues);
}

export function useTaskEventStream({
  enabled = true,
  projectIds = [],
  taskIds = [],
  onTaskState,
}: UseTaskEventStreamOptions) {
  const onTaskStateRef = useRef(onTaskState);
  const projectIdsKey = JSON.stringify(projectIds);
  const taskIdsKey = JSON.stringify(taskIds);

  useEffect(() => {
    onTaskStateRef.current = onTaskState;
  }, [onTaskState]);

  const normalizedProjectIds = useMemo(
    () => normalizeSubscriptionIds(projectIds),
    [projectIdsKey],
  );
  const normalizedTaskIds = useMemo(
    () => normalizeSubscriptionIds(taskIds),
    [taskIdsKey],
  );
  const subscriptionKey = useMemo(
    () =>
      JSON.stringify({
        enabled,
        projectIds: normalizedProjectIds,
        taskIds: normalizedTaskIds,
      }),
    [enabled, normalizedProjectIds, normalizedTaskIds],
  );

  useEffect(() => {
    if (!enabled) {
      return;
    }
    if (normalizedProjectIds.length === 0 && normalizedTaskIds.length === 0) {
      return;
    }

    let disposed = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let reconnectAttempt = 0;

    const connect = () => {
      const socketUrl = buildApiWebSocketUrl("/ws/task-events", {
        project_id: normalizedProjectIds,
        task_id: normalizedTaskIds,
      });
      socket = new WebSocket(socketUrl);

      socket.onopen = () => {
        reconnectAttempt = 0;
        const accessToken = getAccessToken();
        if (accessToken) {
          socket?.send(JSON.stringify({ type: "auth", token: accessToken }));
        }
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as TaskEventStreamMessage;
          if (payload.type === "task_state" && payload.task) {
            onTaskStateRef.current(payload.task);
          }
        } catch {
          // 忽略无法识别的订阅消息，避免打断工作台主流程。
        }
      };

      socket.onerror = () => {
        socket?.close();
      };

      socket.onclose = () => {
        if (disposed) {
          return;
        }
        reconnectAttempt += 1;
        const baseDelay = 600 * reconnectAttempt;
        const maxDelay = 30_000;
        const jitter = Math.random() * 600;
        const reconnectDelay = Math.min(maxDelay, baseDelay) + jitter;
        reconnectTimer = window.setTimeout(() => {
          connect();
        }, reconnectDelay);
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [enabled, subscriptionKey]);
}
