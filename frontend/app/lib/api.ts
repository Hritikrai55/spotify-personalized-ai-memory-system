const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Memory = {
  memory_id: string;
  subject_id: string;
  memory_type: string;
  fact_text: string;
  confidence: number;
  status: string;
  valid_from: string;
};

export async function sendMessage(subjectId: string, message: string): Promise<string> {
  const res = await fetch(`${API_URL}/v1/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject_id: subjectId, message }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const data = await res.json();
  return data.response;
}

export async function listMemories(subjectId: string): Promise<Memory[]> {
  const res = await fetch(`${API_URL}/v1/memories?subject_id=${encodeURIComponent(subjectId)}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function deleteMemory(memoryId: string): Promise<void> {
  const res = await fetch(`${API_URL}/v1/memories/${memoryId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}
