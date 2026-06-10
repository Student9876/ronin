import { create } from "zustand";

export type Thread = { id: number; title: string; created_at: string };
export type Status = { node: string; message: string };
export type Message = {
    id: number | string;
    role: "user" | "agent";
    content: string;
    statuses?: Status[]
};
export type RawMessage = Omit<Message, "statuses"> & { statuses?: string | null };

export interface AgentSettings {
    searchDepth: "quick" | "comprehensive" | "exhaustive";
    strictness: "lenient" | "strict";
}

interface ChatState {
    threads: Thread[];
    messages: Message[];
    isStreaming: boolean;
    settings: AgentSettings;
    fetchThreads: () => Promise<void>;
    createThread: () => Promise<number>;
    fetchMessages: (threadId: number) => Promise<void>;
    addMessage: (msg: Message) => void;
    updateAgentMessage: (id: string, chunk: string, status?: Status) => void;
    setStreaming: (status: boolean) => void;
    setSettings: (newSettings: Partial<AgentSettings>) => void;
    clearMessages: () => void;
    deleteThread: (id: number) => Promise<void>;
    renameThread: (id: number, title: string) => Promise<void>;
}

const API_BASE = "http://localhost:8000/api/v1";

export const useChatStore = create<ChatState>((set) => ({
    threads: [],
    messages: [],
    isStreaming: false,
    settings: {
        searchDepth: "comprehensive",
        strictness: "strict",
    },

    fetchThreads: async () => {
        const res = await fetch(`${API_BASE}/threads/`);
        const data = await res.json();
        set({ threads: data });
    },

    createThread: async () => {
        const res = await fetch(`${API_BASE}/threads/`, { method: "POST" });
        const data = await res.json();
        set((state) => ({ threads: [data, ...state.threads] }));
        return data.id;
    },

    fetchMessages: async (threadId: number) => {
        set({ messages: [] });  // Clear first
        try {
            const res = await fetch(`${API_BASE}/threads/${threadId}/messages`);
            const data = await res.json();

            // Prevent the crash if the backend returns an error object instead of an array
            if (!Array.isArray(data)) {
                console.error("Backend did not return an array of messages:", data);
                set({ messages: [] });
                return;
            }

            // Parse the JSON string statuses coming from SQLite
            const parsedMessages = data.map((msg: RawMessage) => ({
                ...msg,
                statuses: msg.statuses ? JSON.parse(msg.statuses) : []
            }));
            set({ messages: parsedMessages });
        } catch (error) {
            console.error("Network error fetching messages:", error);
            set({ messages: [] });
        }
    },

    addMessage: (msg: Message) =>
        set((state) => {
            // Prevent adding duplicate IDs
            if (state.messages.find(m => m.id === msg.id)) {
                return state;
            }
            return { messages: [...state.messages, msg] };
        }),

    updateAgentMessage: (id: string, chunk: string, newStatus?: Status) =>
        set((state) => ({
            messages: state.messages.map((msg) => {
                if (msg.id !== id) return msg;
                return {
                    ...msg,
                    content: msg.content + chunk,
                    statuses: newStatus ? [...(msg.statuses || []), newStatus] : msg.statuses,
                };
            }),
        })),

    setStreaming: (status: boolean) => set({ isStreaming: status }),

    setSettings: (newSettings) =>
        set((state) => ({ settings: { ...state.settings, ...newSettings } })),
    clearMessages: () => set({ messages: [] }),

    deleteThread: async (threadId: number) => {
        try {
            await fetch(`${API_BASE}/threads/${threadId}`, { method: "DELETE" });
            set((state) => ({
                threads: state.threads.filter((t) => t.id !== threadId),
                // If the user deletes the active thread, clear the messages
                messages: state.messages.length > 0 && state.messages[0].id.toString().includes(threadId.toString()) ? [] : state.messages
            }));
        } catch (error) {
            console.error("Failed to delete thread:", error);
        }
    },

    renameThread: async (threadId: number, newTitle: string) => {
        try {
            const res = await fetch(`${API_BASE}/threads/${threadId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: newTitle }),
            });
            const updated = await res.json();
            set((state) => ({
                threads: state.threads.map((t) => (t.id === threadId ? updated : t)),
            }));
        } catch (error) {
            console.error("Failed to rename thread:", error);
        }
    },
}));