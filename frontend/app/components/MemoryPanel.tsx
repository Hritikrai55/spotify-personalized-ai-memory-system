"use client";

import { Memory, deleteMemory } from "../lib/api";

export default function MemoryPanel({
  memories,
  loading,
  onChanged,
}: {
  memories: Memory[];
  loading: boolean;
  onChanged: () => void;
}) {
  const handleDelete = async (memoryId: string) => {
    await deleteMemory(memoryId);
    onChanged();
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>Remembered so far</h2>
      </div>
      <div className="memory-list">
        {loading && <div className="empty-state">Loading memory…</div>}
        {!loading && memories.length === 0 && (
          <div className="empty-state">
            Nothing remembered yet. Say something like "I always want lo-fi
            instrumental music while I work."
          </div>
        )}
        {memories.map((m) => (
          <div className="memory-card" key={m.memory_id}>
            <div className="fact">{m.fact_text}</div>
            <div className="meta">
              <span className={`memory-type ${m.memory_type}`}>
                {m.memory_type.replace("_", " ")}
              </span>
              <button className="delete-btn" onClick={() => handleDelete(m.memory_id)}>
                remove
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
