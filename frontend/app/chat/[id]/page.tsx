"use client";

import {useState, useRef, useEffect, use} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {Send, Loader2, CheckCircle2} from "lucide-react";
import {useChatStore} from "@/store/useChatStore";

export default function ChatPage({params}: {params: Promise<{id: string}>}) {
	const resolvedParams = use(params);
	const threadId = parseInt(resolvedParams.id, 10);

	const [query, setQuery] = useState("");
	const bottomRef = useRef<HTMLDivElement>(null);

	const {messages, fetchMessages, addMessage, updateAgentMessage, isStreaming, setStreaming, fetchThreads, settings} = useChatStore();

	// Load history when thread changes
	useEffect(() => {
		fetchMessages(threadId);
	}, [threadId, fetchMessages]);

	// Auto-scroll
	useEffect(() => {
		bottomRef.current?.scrollIntoView({behavior: "smooth"});
	}, [messages]);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!query.trim() || isStreaming) return;

		const userQuery = query;
		const tempAgentId = `temp-${Date.now()}`;

		// Just add the new messages - don't clear history
		addMessage({id: Date.now().toString(), role: "user", content: userQuery});
		addMessage({id: tempAgentId, role: "agent", content: "", statuses: []});

		setQuery("");
		setStreaming(true);

		try {
			const response = await fetch(
				`http://localhost:8000/api/v1/research/stream?thread_id=${threadId}&query=${encodeURIComponent(userQuery)}&depth=${settings.searchDepth}&strictness=${settings.strictness}`,
			);

			const body = response.body;
			if (!body) {
				throw new Error("No response body returned from backend");
			}

			const reader = response.body.getReader();
			const decoder = new TextDecoder();

			let buffer = ""; // Add a buffer to catch fragmented packets

			while (true) {
				const {done, value} = await reader.read();
				if (done) break;

				// Append new data to whatever was left over from the last read
				buffer += decoder.decode(value, {stream: true});

				// Split by the SSE terminator
				const lines = buffer.split("\n\n");

				// The last element is either an incomplete chunk or an empty string.
				// Pop it off and keep it in the buffer for the next loop iteration.
				buffer = lines.pop() || "";

				for (const line of lines) {
					if (line.startsWith("data: ")) {
						const dataStr = line.replace("data: ", "");
						if (!dataStr) continue;

						try {
							const data = JSON.parse(dataStr);
							if (data.type === "status") {
								updateAgentMessage(tempAgentId, "", {node: data.node, message: data.message});
							} else if (data.type === "delta") {
								updateAgentMessage(tempAgentId, data.content);
							} else if (data.type === "error") {
								updateAgentMessage(tempAgentId, `\n\n**System Error:** ${data.message}`);
							}
						} catch (err) {
							console.error("Failed to parse JSON chunk. Data:", dataStr);
						}
					}
				}
			}

			// Refresh sidebar to update thread title based on the backend processing
			fetchThreads();
		} catch (error) {
			console.error("Stream error:", error);
		} finally {
			setStreaming(false);
			// Re-fetch to replace temp IDs with actual DB IDs
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
					{messages.map((msg) => (
						<div key={msg.id} className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
							{msg.role === "user" && (
								<div className="bg-neutral-800 px-6 py-4 rounded-2xl max-w-[80%] text-neutral-200 shadow-sm">{msg.content}</div>
							)}

							{msg.role === "agent" && (
								<div className="w-full space-y-4">
									{msg.statuses && msg.statuses.length > 0 && (
										<div className="flex flex-col space-y-2 border-l-2 border-neutral-800 pl-4 py-2">
											{msg.statuses.map((status, idx) => (
												<div key={idx} className="flex items-center space-x-3 text-sm text-neutral-400 font-mono">
													{idx === msg.statuses!.length - 1 && isStreaming ? (
														<Loader2 className="w-4 h-4 animate-spin text-blue-500" />
													) : (
														<CheckCircle2 className="w-4 h-4 text-emerald-500" />
													)}
													<span>{status.message}</span>
												</div>
											))}
										</div>
									)}

									{msg.content && (
										<div className="prose prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-neutral-900 prose-pre:border prose-pre:border-neutral-800 bg-neutral-900/30 p-6 rounded-xl border border-neutral-800/50">
											<ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
										</div>
									)}
								</div>
							)}
						</div>
					))}
					<div ref={bottomRef} />
				</div>
			</main>

			<footer className="p-4 md:p-6 bg-neutral-950 border-t border-neutral-900">
				<form onSubmit={handleSubmit} className="max-w-3xl mx-auto relative flex items-center">
					<input
						type="text"
						value={query}
						onChange={(e) => setQuery(e.target.value)}
						disabled={isStreaming}
						placeholder="Deploy research agent..."
						className="w-full bg-neutral-900 border border-neutral-800 rounded-xl px-4 py-4 pr-14 text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:ring-1 focus:ring-neutral-700 disabled:opacity-50 transition-all"
					/>
					<button
						type="submit"
						disabled={!query.trim() || isStreaming}
						className="absolute right-2 p-2 bg-neutral-100 hover:bg-white text-neutral-950 rounded-lg disabled:opacity-50 transition-colors">
						<Send className="w-5 h-5" />
					</button>
				</form>
			</footer>
		</div>
	);
}
