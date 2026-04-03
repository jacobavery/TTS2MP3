/**
 * SSE EventSource wrapper with typed events.
 */
export function connectSSE(url, handlers = {}) {
  const source = new EventSource(url);

  source.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data);
    if (handlers.onProgress) handlers.onProgress(data);
  });

  source.addEventListener('done', (e) => {
    const data = JSON.parse(e.data);
    if (handlers.onDone) handlers.onDone(data);
    source.close();
  });

  source.addEventListener('error', (e) => {
    if (e.data) {
      const data = JSON.parse(e.data);
      if (handlers.onError) handlers.onError(data);
    } else if (handlers.onError) {
      handlers.onError({ error: 'Connection lost' });
    }
    source.close();
  });

  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) return;
    source.close();
    if (handlers.onError) handlers.onError({ error: 'Connection lost' });
  };

  return source;
}
