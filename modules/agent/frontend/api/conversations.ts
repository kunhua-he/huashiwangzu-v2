import { apiFetch } from '../api'
import type { ConvItem, MsgItem } from '../types'

export function listConversations(): Promise<ConvItem[]> {
  return apiFetch<ConvItem[]>('/agent/conversations')
}

export function createConversation(title: string): Promise<ConvItem> {
  return apiFetch<ConvItem>('/agent/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export function renameConversationRequest(id: number, title: string): Promise<unknown> {
  return apiFetch(`/agent/conversations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
}

export function deleteConversationRequest(id: number): Promise<unknown> {
  return apiFetch(`/agent/conversations/${id}`, { method: 'DELETE' })
}

export function listMessages(conversationId: number): Promise<MsgItem[]> {
  return apiFetch<MsgItem[]>(`/agent/conversations/${conversationId}/messages`)
}
