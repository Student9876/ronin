"use client";

import {useState, useRef, useEffect, use} from "react";
import {useChatStore} from "@/store/useChatStore";
import {MessageBubble} from "@/components/chat/MessageBubble";
import {ChatInput} from "@/components/chat/ChatInput";

export default function ChatPage({params}: {params: Promise<{id: string}>}) {
	const resolvedParams = use(params);
	const threadId = parseInt(resolvedParams.id, 10);

	const [query, setQuery] = useState("");
	const bottomRef = useRef<HTMLDivElement>(null);

	const {messages, fetchMessages, addMessage, updateAgentMessage, isStreaming, setStreaming, fetchThreads, settings, setSettings} = useChatStore();

	useEffect(() => {
		fetchMessages(threadId);
	}, [threadId, fetchMessages]);

	useEffect(() => {
		bottomRef.current?.scrollIntoView({behavior: "smooth"});
	}, [messages]);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!query.trim() || isStreaming) return;

		const userQuery = query;
		const tempAgentId = `temp-${Date.now()}`;

		addMessage({id: Date.now().toString(), role: "user", content: userQuery});
		addMessage({id: tempAgentId, role: "agent", content: "", statuses: []});

		setQuery("");
		setStreaming(true);

		try {
			const response = await fetch("http://localhost:8000/api/v1/agent/stream", {
				method: "POST",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					thread_id: threadId,
					query: userQuery,
					mode: settings.mode,
				}),
			});

			const body = response.body;
			if (!body) throw new Error("No response body returned from backend");

			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = "";

			while (true) {
				const {done, value} = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, {stream: true});
				const lines = buffer.split("\n\n");
				buffer = lines.pop() || "";

				for (const line of lines) {
					if (line.startsWith("data: ")) {
						const dataStr = line.replace("data: ", "").trim();
						if (!dataStr) continue;

						// Intercept termination token to protect parsing loop execution
						if (dataStr === "[DONE]") {
							console.log("Stream successfully concluded via backend signal.");
							setStreaming(false);
							continue;
						}

						try {
							const data = JSON.parse(dataStr);
							if (data.type === "status") {
								updateAgentMessage(tempAgentId, "", {node: data.node, message: data.message});
							} else if (data.type === "delta") {
								updateAgentMessage(tempAgentId, data.content);
							} else if (data.type === "error") {
								updateAgentMessage(tempAgentId, `\n\n**System Error:** ${data.message}`);
							}
						} catch {
							console.error("Failed to parse JSON chunk. Data:", dataStr);
						}
					}
				}
			}
			fetchThreads();
		} catch (error) {
			console.error("Stream error:", error);
		} finally {
			setStreaming(false);
			fetchMessages(threadId);
		}
	};

	return (
		<div className="flex flex-col h-full">
			<header className="flex items-center justify-center py-4 border-b border-neutral-800 bg-neutral-900/50">
				<h1 className="text-sm font-semibold tracking-widest text-neutral-400 uppercase">Research Session {threadId}</h1>
			</header>

			<main className="flex-1 overflow-y-auto p-4 md:p-8 space-y-8">
				<div className="max-w-3xl mx-auto space-y-8">
					{messages.map((msg, msgIndex) => (
						<MessageBubble key={msg.id} msg={msg} isLastMessage={msgIndex === messages.length - 1} isStreaming={isStreaming} />
					))}
					<div ref={bottomRef} />
				</div>
			</main>

			<ChatInput query={query} setQuery={setQuery} handleSubmit={handleSubmit} isStreaming={isStreaming} settings={settings} setSettings={setSettings} />
		</div>
	);
}
