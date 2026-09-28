"use client";

import { useState, useEffect, useCallback } from "react";
import ChatPanel from "./components/ChatPanel";
import MemoryPanel from "./components/MemoryPanel";
import { Memory, listMemories } from "./lib/api";

const SUBJECT_ID = "user_demo_001";

export default function Home() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshMemories = useCallback(async () => {
    try {
      const data = await listMemories(SUBJECT_ID);
      setMemories(data.filter((m) => m.status === "active"));
    } catch {
      // backend not reachable yet — leave list as-is
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshMemories();
  }, [refreshMemories]);

  return (
    <div className="layout">
      <ChatPanel subjectId={SUBJECT_ID} onMemoryUpdate={refreshMemories} />
      <MemoryPanel memories={memories} loading={loading} onChanged={refreshMemories} />
    </div>
  );
}
