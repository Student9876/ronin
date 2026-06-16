import { useState, useCallback } from "react";

// Types matching our UI components
export type Message = {
    id: string;
    role: "user" | "agent";
    content: string;
    isStreaming?: boolean;
};

export type AgentEvent = {
    id: string;
    node: string;
    msg: string;
    time: string;
};

export function useAgentStream() {
    // Initialize with a welcome message
    const [messages, setMessages] = useState<Message[]>([
        {
            id: "init",
            role: "agent",
            content: "Ronin Engine initialized. I am ready to execute deep research or code analysis tasks. What is our objective?",
        }
    ]);

    const [events, setEvents] = useState<AgentEvent[]>([]);
    const [agentState, setAgentState] = useState<any>(null);
    const [tools, setTools] = useState<any[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);

    const submitQuery = useCallback(async (query: string, mode: string = "deep", threadId: number = 104) => {
        if (!query.trim() || isStreaming) return;

        // 1. Immediately inject the user's message into the UI
        const userMsg: Message = { id: Date.now().toString(), role: "user", content: query };

        // 2. Prepare a blank agent message that we will stream the tokens into
        const agentMsgId = `agent-${Date.now()}`;
        const initialAgentMsg: Message = { id: agentMsgId, role: "agent", content: "", isStreaming: true };

        setMessages(prev => [...prev, userMsg, initialAgentMsg]);
        setEvents([]); // Clear the dev inspector events for the new run
        setAgentState(null);
        setTools([]);
        setIsStreaming(true);

        try {
            // POST request to our FastAPI stream endpoint
            const response = await fetch("http://localhost:8000/api/v1/agent/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ thread_id: threadId, query, mode }),
            });

            if (!response.ok || !response.body) {
                throw new Error(`HTTP Error: ${response.status}`);
            }

            // Read the Server-Sent Events stream chunk by chunk
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let done = false;
            let buffer = ""; // Buffer to catch split JSON chunks

            while (!done) {
                const { value, done: readerDone } = await reader.read();
                done = readerDone;

                if (value) {
                    buffer += decoder.decode(value, { stream: true });
                    // Split by the double newline that SSE uses to separate messages
                    const lines = buffer.split("\n\n");

                    // Keep the last incomplete chunk in the buffer to be combined with the next stream chunk
                    buffer = lines.pop() || "";

                    for (const line of lines) {
                        if (line.startsWith("data: ")) {
                            const dataStr = line.substring(6).trim();

                            // Backend sent the kill signal
                            if (dataStr === "[DONE]") {
                                done = true;
                                break;
                            }

                            try {
                                const parsed = JSON.parse(dataStr);

                                // Route the data payload based on its type
                                if (parsed.type === "delta") {
                                    // Text chunk for the ChatPane
                                    setMessages(prev => prev.map(msg =>
                                        msg.id === agentMsgId
                                            ? { ...msg, content: msg.content + parsed.content }
                                            : msg
                                    ));
                                } else if (parsed.type === "status") {
                                    // Telemetry chunk for the InspectorPane
                                    setEvents(prev => [...prev, {
                                        id: Date.now().toString() + Math.random(),
                                        node: parsed.node,
                                        msg: parsed.message,
                                        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                                    }]);
                                } else if (parsed.type === "state") {
                                    // Catch live LangGraph state dumps
                                    setAgentState(parsed.data);
                                } else if (parsed.type === "tool") {
                                    // Catch tool execution payloads
                                    setTools(prev => [...prev, parsed.data]);
                                } else if (parsed.type === "error") {
                                    // Error handling
                                    setMessages(prev => prev.map(msg =>
                                        msg.id === agentMsgId
                                            ? { ...msg, content: msg.content + `\n\n**Error:** ${parsed.message}` }
                                            : msg
                                    ));
                                }
                            } catch (e) {
                                console.warn("Failed to parse SSE chunk:", dataStr);
                            }
                        }
                    }
                }
            }
        } catch (error) {
            console.error("Stream connection failed:", error);
            setMessages(prev => prev.map(msg =>
                msg.id === agentMsgId
                    ? { ...msg, content: msg.content + "\n\n**Connection Error:** Could not reach the Ronin backend. Ensure FastAPI is running on port 8000." }
                    : msg
            ));
        } finally {
            // Clean up UI states when the stream finishes or errors out
            setIsStreaming(false);
            setMessages(prev => prev.map(msg =>
                msg.id === agentMsgId ? { ...msg, isStreaming: false } : msg
            ));
        }
    }, [isStreaming]);

    return { messages, events, agentState, tools, isStreaming, submitQuery };
}