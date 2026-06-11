"use client";

import {useState, useRef, useEffect, use} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {Send, Loader2, CheckCircle2, Cpu} from "lucide-react";
import {useChatStore} from "@/store/useChatStore";
import type {Components} from "react-markdown";

import {Prism as SyntaxHighlighter} from "react-syntax-highlighter";

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
			// Hit the new unified switchboard using a POST request
			const response = await fetch("http://localhost:8000/api/v1/agent/stream", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					thread_id: threadId,
					query: userQuery,
					mode: settings.mode, // "general" or "deep"
				}),
			});

			const body = response.body;
			if (!body) {
				throw new Error("No response body returned from backend");
			}

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
					{messages.map((msg, msgIndex) => {
						const isLastMessage = msgIndex === messages.length - 1;

						return (
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
														{idx === msg.statuses!.length - 1 && isStreaming && isLastMessage ? (
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
											<div className="prose prose-invert max-w-none prose-p:leading-relaxed prose-headings:text-neutral-200 prose-a:text-blue-400 prose-strong:text-neutral-200 bg-neutral-900/30 p-6 rounded-xl border border-neutral-800/50">
												<ReactMarkdown
													remarkPlugins={[remarkGfm]}
													components={
														{
															code({
																inline,
																className,
																children,
																style: _style,
																...props
															}: React.ComponentPropsWithoutRef<"code"> & {inline?: boolean}) {
																void _style;
																const match = /language-(\w+)/.exec(className || "");
																return !inline && match ? (
																	<div className="rounded-md overflow-hidden my-4 border border-neutral-800">
																		<div className="bg-neutral-900 px-4 py-2 text-xs text-neutral-400 font-mono border-b border-neutral-800 uppercase tracking-wider">
																			{match[1]}
																		</div>
																		<SyntaxHighlighter
																			language={match[1]}
																			PreTag="div"
																			customStyle={{margin: 0, padding: "1rem", background: "#0a0a0a"}}
																			{...props}>
																			{String(children).replace(/\n$/, "")}
																		</SyntaxHighlighter>
																	</div>
																) : (
																	<code
																		className="bg-neutral-800 text-neutral-300 px-1.5 py-0.5 rounded-md font-mono text-sm before:hidden after:hidden"
																		{...props}>
																		{children}
																	</code>
																);
															},

															a({children, ...props}: React.ComponentPropsWithoutRef<"a">) {
																const text = String(children);
																if (/^\[\d+\]$/.test(text)) {
																	return (
																		<a
																			{...props}
																			className="inline-flex items-center justify-center w-5 h-5 ml-1 text-[10px] font-medium text-neutral-400 bg-neutral-800 rounded-full hover:bg-neutral-700 hover:text-neutral-200 transition-colors no-underline align-super cursor-pointer"
																			target="_blank"
																			rel="noopener noreferrer">
																			{text.replace(/\[|\]/g, "")}
																		</a>
																	);
																}
																return (
																	<a
																		{...props}
																		className="text-blue-400 hover:text-blue-300 underline decoration-blue-400/30 underline-offset-2 transition-colors"
																		target="_blank"
																		rel="noopener noreferrer">
																		{children}
																	</a>
																);
															},

															table({...props}: React.ComponentPropsWithoutRef<"table">) {
																return (
																	<div className="overflow-x-auto my-6 rounded-lg border border-neutral-800">
																		<table className="w-full text-sm text-left m-0" {...props} />
																	</div>
																);
															},
															th({...props}: React.ComponentPropsWithoutRef<"th">) {
																return (
																	<th
																		className="bg-neutral-900 px-4 py-3 font-medium text-neutral-300 border-b border-neutral-800"
																		{...props}
																	/>
																);
															},
															td({...props}: React.ComponentPropsWithoutRef<"td">) {
																return <td className="px-4 py-3 border-b border-neutral-800/50 text-neutral-400" {...props} />;
															},
														} as Components
													}>
													{msg.content}
												</ReactMarkdown>
											</div>
										)}
									</div>
								)}
							</div>
						);
					})}
					<div ref={bottomRef} />
				</div>
			</main>

			<footer className="p-4 md:p-6 bg-neutral-950 border-t border-neutral-900">
				<form
					onSubmit={handleSubmit}
					className="max-w-3xl mx-auto relative flex items-center bg-neutral-900 border border-neutral-800 rounded-xl transition-all focus-within:ring-1 focus-within:ring-neutral-700">
					{/* Engine Mode Selector */}
					<div className="pl-3 pr-2 flex items-center border-r border-neutral-800">
						<Cpu className="w-4 h-4 text-neutral-500 mr-2" />
						<select
							value={settings.mode}
							onChange={(e) => setSettings({mode: e.target.value as "general" | "deep"})}
							disabled={isStreaming}
							className="bg-transparent text-sm text-neutral-300 focus:outline-none disabled:opacity-50 appearance-none cursor-pointer">
							<option value="general">General</option>
							<option value="deep">Deep Research</option>
						</select>
					</div>

					<input
						type="text"
						value={query}
						onChange={(e) => setQuery(e.target.value)}
						disabled={isStreaming}
						placeholder={settings.mode === "deep" ? "Deploy multi-agent research..." : "Ask a general question..."}
						className="w-full bg-transparent px-4 py-4 pr-14 text-neutral-200 placeholder:text-neutral-600 focus:outline-none disabled:opacity-50"
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
