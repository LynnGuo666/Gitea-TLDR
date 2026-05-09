function getApiOrigin(): string {
  return process.env.NEXT_PUBLIC_API_ORIGIN || '';
}

export function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  if (input.startsWith('http://') || input.startsWith('https://')) {
    return fetch(input, init);
  }

  const [path, query = ''] = input.split('?');
  const querySuffix = query ? `?${query}` : '';
  const mappedPath =
    path === '/api/stats'
      ? '/api/v2/usage'
      : path === '/api/repositories'
      ? '/api/v2/repos'
      : path === '/api/my/reviews' || path === '/api/reviews'
      ? '/api/v2/runs'
      : path === '/api/my/issues' || path === '/api/issues'
      ? '/api/v2/runs'
      : path.startsWith('/api/my/reviews/')
      ? path.replace('/api/my/reviews/', '/api/v2/runs/')
      : path.startsWith('/api/reviews/')
      ? path.replace('/api/reviews/', '/api/v2/runs/')
      : path.startsWith('/api/my/issues/')
      ? path.replace('/api/my/issues/', '/api/v2/runs/')
      : path.startsWith('/api/issues/')
      ? path.replace('/api/issues/', '/api/v2/runs/')
      : path === '/api/forge/sessions'
      ? '/api/v2/provider-runs'
      : path.startsWith('/api/forge/sessions/')
      ? path.replace('/api/forge/sessions/', '/api/v2/provider-runs/')
      : path;
  const enrichedQuery =
    (path === '/api/my/reviews' || path === '/api/reviews') && !query.includes('kind=')
      ? `${query ? `${query}&` : ''}kind=review`
      : (path === '/api/my/issues' || path === '/api/issues') && !query.includes('kind=')
      ? `${query ? `${query}&` : ''}kind=issue`
      : query;
  const mappedInput = `${mappedPath}${enrichedQuery ? `?${enrichedQuery}` : querySuffix}`;
  const origin = getApiOrigin();
  const normalizedInput =
    mappedInput.startsWith('/api/') && !mappedInput.startsWith('/api/v2/')
      ? mappedInput.replace(/^\/api\//, '/api/v2/')
      : mappedInput;
  const url = origin ? `${origin}${normalizedInput}` : normalizedInput;

  return fetch(url, init);
}
