export const platform = {
  modules: {
    async call(targetModule: string, action: string, parameters: Record<string, unknown> = {}): Promise<unknown> {
      const r = await fetch('/api/modules/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_module: targetModule, action, parameters }),
      })
      const body = await r.json()
      if (!body.success) throw new Error(body.error ?? 'API error')
      return body.data
    },
  },
  docs: {
    async open(fileId: number, mode: string = 'view'): Promise<any> {
      const r = await fetch('/api/docs/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: fileId, mode }),
      })
      const body = await r.json()
      if (!body.success) throw new Error(body.error ?? 'Failed to open document')
      return body.data
    },
    async getContent(fileId: number): Promise<any> {
      const r = await fetch(`/api/docs/${fileId}/content`)
      const body = await r.json()
      if (!body.success) throw new Error(body.error ?? 'Failed to get content')
      return body.data
    },
  },
}
