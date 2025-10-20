// src/hooks/useChatStream.ts
import { useState, useRef } from "react";

type OnToken = (t: any) => void;
type OnError = (e: any) => void;
type OnDone = () => void;

const useChatStream = ({
  onToken,
  onError,
  onDone,
}: {
  onToken?: OnToken;
  onError?: OnError;
  onDone?: OnDone;
}) => {
  const controllerRef = useRef<AbortController | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const startStream = async (params: { query: string }) => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    controllerRef.current = new AbortController();
    setIsStreaming(true);

    try {
      // Simulate streaming from your original App.tsx
      const words = params.query.split(" ");
      for (let i = 0; i < words.length; i++) {
        if (controllerRef.current.signal.aborted) {
          throw new DOMException("Aborted", "AbortError");
        }
        await new Promise(resolve => setTimeout(resolve, 100));
        onToken?.(words[i] + " ");
      }
      onDone?.();
    } catch (err: any) {
      if (err?.name !== "AbortError") onError?.(err);
    } finally {
      setIsStreaming(false);
      controllerRef.current = null;
    }
  };

  const stopStream = () => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setIsStreaming(false);
  };

  return { startStream, stopStream, isStreaming };
};

export default useChatStream;