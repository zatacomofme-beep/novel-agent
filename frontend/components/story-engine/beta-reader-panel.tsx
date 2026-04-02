"use client";

import { useState } from "react";

interface BetaFeedback {
  overall_reaction: string;
  pacing_issues: string[];
  emotional_response: string;
  engagement_score: number;
  dialogue_issues: string[];
  confusion_points: string[];
  strengths: string[];
  suggestions: string[];
}

interface BetaReaderPanelProps {
  chapterId: string;
  content: string;
  genre?: string;
  onClose?: () => void;
}

export function BetaReaderPanel({
  chapterId,
  content,
  genre = "fantasy",
  onClose,
}: BetaReaderPanelProps) {
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<BetaFeedback | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/v1/chapters/${chapterId}/beta-reader`,
        {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({content, genre}),
        }
      );
      if (!response.ok) throw new Error("Failed to generate beta feedback");
      const data = await response.json();
      setFeedback(data.beta_feedback);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border rounded-lg p-4 bg-white dark:bg-gray-800 max-w-2xl">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Beta Reader Feedback</h3>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        >
          ✕
        </button>
      </div>

      {!feedback && !loading && (
        <div className="text-center py-8">
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Get simulated beta reader feedback on this chapter.
          </p>
          <button
            onClick={handleGenerate}
            className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700"
          >
            Generate Beta Feedback
          </button>
        </div>
      )}

      {loading && (
        <div className="text-center py-8">
          <div className="animate-spin w-8 h-8 border-4 border-purple-600 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">
            Simulating beta reader reaction...
          </p>
        </div>
      )}

      {error && (
        <div className="p-4 mb-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded">
          {error}
        </div>
      )}

      {feedback && (
        <div className="space-y-4">
          <div>
            <h4 className="font-medium text-purple-700 dark:text-purple-300">
              Overall Reaction
            </h4>
            <p className="mt-1 text-gray-700 dark:text-gray-300">
              {feedback.overall_reaction}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="font-medium text-sm">Engagement Score</h4>
              <div className="mt-1 flex items-center gap-2">
                <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded">
                  <div
                    className="h-2 bg-purple-600 rounded"
                    style={{width: `${(feedback.engagement_score || 0.5) * 100}%`}}
                  />
                </div>
                <span className="text-sm">
                  {Math.round((feedback.engagement_score || 0.5) * 100)}%
                </span>
              </div>
            </div>
          </div>

          {feedback.strengths.length > 0 && (
            <div>
              <h4 className="font-medium text-green-700 dark:text-green-300">
                Strengths
              </h4>
              <ul className="mt-1 list-disc list-inside text-gray-700 dark:text-gray-300">
                {feedback.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {feedback.pacing_issues.length > 0 && (
            <div>
              <h4 className="font-medium text-amber-700 dark:text-amber-300">
                Pacing Issues
              </h4>
              <ul className="mt-1 list-disc list-inside text-gray-700 dark:text-gray-300">
                {feedback.pacing_issues.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </div>
          )}

          {feedback.dialogue_issues.length > 0 && (
            <div>
              <h4 className="font-medium text-red-700 dark:text-red-300">
                Dialogue Issues
              </h4>
              <ul className="mt-1 list-disc list-inside text-gray-700 dark:text-gray-300">
                {feedback.dialogue_issues.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </div>
          )}

          {feedback.suggestions.length > 0 && (
            <div>
              <h4 className="font-medium text-blue-700 dark:text-blue-300">
                Suggestions
              </h4>
              <ul className="mt-1 list-disc list-inside text-gray-700 dark:text-gray-300">
                {feedback.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          <button
            onClick={handleGenerate}
            className="mt-4 px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            Regenerate Feedback
          </button>
        </div>
      )}
    </div>
  );
}
