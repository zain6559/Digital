const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}
export async function sendCommand(prompt: string) { return jsonRequest(`${API}/api/command`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }) }); }
export async function loadRealms() { return jsonRequest<Record<string, unknown[]>>(`${API}/api/memory/realms`); }
export async function loadHealth() { return jsonRequest<Record<string, unknown>>(`${API}/health`); }
export async function mobileDevices() { return jsonRequest(`${API}/api/mobile/devices`); }
export async function sendVisionFrame(source: string, canvas: HTMLCanvasElement) {
  const dataUrl = canvas.toDataURL('image/png');
  return jsonRequest(`${API}/api/vision/frame`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source, width: canvas.width, height: canvas.height, mime: 'image/png', data_base64: dataUrl.split(',')[1] ?? '' }) });
}
export { API };
