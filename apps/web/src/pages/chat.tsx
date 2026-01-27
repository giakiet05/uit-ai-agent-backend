"use client"

import { useState, useEffect, useRef } from "react"
import ChatSidebar from "@/components/chat-sidebar"
import ChatWindow from "@/components/chat-window"
import { useChatSessions, useDeleteSession } from "@/hooks/useChatSessions"
import { useChatMessages } from "@/hooks/useChatMessages"
import { useSendMessage } from "@/hooks/useChat"
import type { ChatMessageResponse } from "@/lib/api"

export default function ChatPage() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [isNewConversation, setIsNewConversation] = useState(false)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const { sessions, loading: sessionsLoading, refetch: refetchSessions } = useChatSessions()
  const { messages, loading: messagesLoading, addMessage, clearMessages, setMessages } = useChatMessages(activeSessionId)
  const { sendMessage, loading: sendingMessage } = useSendMessage()
  const { deleteSession } = useDeleteSession()

  // Set first session as active on load (but not when starting new conversation)
  useEffect(() => {
    if (sessions.length > 0 && !activeSessionId && !isNewConversation) {
      setActiveSessionId(sessions[0].id)
    }
  }, [sessions, activeSessionId, isNewConversation])

  const activeSession = sessions.find((s) => s.id === activeSessionId)

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return

    // Create optimistic user message
    const optimisticUserMessage: ChatMessageResponse = {
      id: `temp-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    }

    // Add user message to UI immediately
    addMessage(optimisticUserMessage)

    // Send to API
    const response = await sendMessage({
      message: content,
      session_id: activeSessionId || undefined,
    })

    if (response) {
      // If new session was created, update session ID
      if (!activeSessionId) {
        setActiveSessionId(response.session_id)
        setIsNewConversation(false) // Reset flag after creating new session
        await refetchSessions()
      }

      // Add assistant message
      addMessage(response.message)
    } else {
      // Remove optimistic message on error
      setMessages((prev) => prev.filter((m) => m.id !== optimisticUserMessage.id))
    }
  }

  const handleNewConversation = () => {
    console.log("handleNewConversation called")
    console.log("Current activeSessionId:", activeSessionId)
    setIsNewConversation(true)
    setActiveSessionId(null)
    clearMessages()
    console.log("Cleared messages, activeSessionId set to null")
  }

  const handleSelectConversation = (id: string) => {
    setIsNewConversation(false) // Reset flag when selecting existing conversation
    setActiveSessionId(id)
  }

  const handleDeleteConversation = async (id: string) => {
    const success = await deleteSession(id)
    if (success) {
      await refetchSessions()

      // If deleting active session, switch to first available or create new
      if (id === activeSessionId) {
        const remainingSessions = sessions.filter((s) => s.id !== id)
        if (remainingSessions.length > 0) {
          setActiveSessionId(remainingSessions[0].id)
        } else {
          handleNewConversation()
        }
      }
    }
  }

  // Convert API messages to component format
  const formattedMessages = messages.map((msg) => ({
    id: msg.id,
    role: msg.role,
    content: msg.content,
    timestamp: new Date(msg.created_at),
    metadata: msg.metadata, // Pass metadata including sources
  }))

  // Convert API sessions to component format
  const formattedSessions = sessions.map((session) => ({
    id: session.id,
    title: session.title,
    createdAt: new Date(session.created_at),
  }))

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <ChatSidebar
        conversations={formattedSessions}
        activeConversationId={activeSessionId || ""}
        onSelectConversation={(id) => {
          handleSelectConversation(id)
          setIsSidebarOpen(false) // Close sidebar on mobile after selection
        }}
        onNewConversation={() => {
          handleNewConversation()
          setIsSidebarOpen(false) // Close sidebar on mobile after creating new conversation
        }}
        onDeleteConversation={handleDeleteConversation}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />
      <ChatWindow
        messages={formattedMessages}
        conversationTitle={activeSession?.title || "Cuộc trò chuyện mới"}
        onSendMessage={handleSendMessage}
        isLoading={sendingMessage}
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
      />
    </div>
  )
}
