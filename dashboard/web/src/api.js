export async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export function fmtPct(x) {
  if (x == null || Number.isNaN(x)) return "—";
  return `${(Number(x) * 100).toFixed(3)}%`;
}

export function fmtNum(x, d = 2) {
  if (x == null || Number.isNaN(x)) return "—";
  return Number(x).toFixed(d);
}
