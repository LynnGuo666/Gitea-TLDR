function getApiOrigin(): string {
  return process.env.NEXT_PUBLIC_API_ORIGIN || '';
}

export function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  if (input.startsWith('http://') || input.startsWith('https://')) {
    return fetch(input, init);
  }

  const origin = getApiOrigin();
  const url = origin ? `${origin}${input}` : input;

  return fetch(url, init);
}
