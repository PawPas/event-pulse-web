export async function apiFetch(path: string, options: RequestInit = {}): Promise<unknown> {
  const token = localStorage.getItem("token");

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(path, { ...options, headers });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw { status: response.status, detail: body.detail ?? response.statusText };
  }

  return response.json();
}
