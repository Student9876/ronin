"use client";

import {useState, useRef, useEffect, use} from "react";
import {useChatStore} from "@/store/useChatStore";
import {ChatPane} from "@/components/chat/ChatPane";
import {PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen} from "lucide-react";
import {useSearchParams, useRouter} from "next/navigation";
import {InspectorPane} from "@/components/chat/InspectorPane";
import {Sidebar} from "@/components/chat/Sidebar";

export default function ChatPage({params}: {params: Promise<{id: string}>}) {
	const resolvedParams = use(params);
	const threadId = parseInt(resolvedParams.id, 10);

	const [isSidebarOpen, setIsSidebarOpen] = useState(true);
	const [isInspectorOpen, setIsInspectorOpen] = useState(true);

	const {
		messages, fetchMessages, addMessage, updateAgentMessage, 
		isStreaming, setStreaming, fetchThreads, settings, setSettings,
		events, agentState, tools, addEvent, setAgentState, addTool, clearTelemetry
	} = useChatStore();

	useEffect(() => {
		fetchMessages(threadId);
	}, [threadId, fetchMessages]);

	const searchParams = useSearchParams();
	const router = useRouter();
	const hasInitialized = useRef(false);

	useEffect(() => {
		const initialQuery = searchParams.get("q");
		const initialMode = searchParams.get("m");
		
		if (initialQuery && !hasInitialized.current) {
			hasInitialized.current = true;
			setTimeout(() => {
				executeStream(initialQuery, initialMode || settings.mode);
				router.replace(`/chat/${threadId}`);
			}, 100);
		}
	}, [searchParams, router, threadId, settings.mode]);

	const executeStream = async (userQuery: string, modeToUse: string) => {
		if (!userQuery.trim() || isStreaming) return;

		const tempAgentId = `temp-${Date.now()}`;

		addMessage({id: Date.now().toString(), role: "user", content: userQuery});
		addMessage({id: tempAgentId, role: "agent", content: "", statuses: []});

		setStreaming(true);
		clearTelemetry();

		try {
			const response = await fetch("http://localhost:8000/api/v1/agent/stream", {
				method: "POST",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					thread_id: threadId,
					query: userQuery,
					mode: modeToUse,
					search_depth: settings.searchDepth,
					strictness: settings.strictness,
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
								addEvent({
									id: Date.now().toString() + Math.random(),
									node: data.node,
									msg: data.message,
									time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
								});
							} else if (data.type === "delta") {
								updateAgentMessage(tempAgentId, data.content);
							} else if (data.type === "state") {
								setAgentState(data.data);
							} else if (data.type === "tool") {
								addTool(data.data);
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
		<div className="flex h-screen w-full bg-slate-50 text-slate-900 overflow-hidden m-0 p-0">
			{/* LEFT PANE */}
			<div
				className={`${
					isSidebarOpen ? "w-64" : "w-0"
				} transition-all duration-300 ease-in-out border-r border-slate-200 bg-slate-50 overflow-hidden flex-shrink-0`}>
				<Sidebar />
			</div>

			{/* CENTER PANE */}
			<div className="flex-1 flex flex-col min-w-0 relative bg-white">
				<header className="h-14 border-b border-slate-200 flex items-center justify-between px-4 bg-white z-10 flex-shrink-0">
					<button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-2 hover:bg-slate-100 rounded-md text-slate-500 transition-colors">
						{isSidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
					</button>
					<h1 className="font-semibold text-slate-700 tracking-tight">Research Session {threadId}</h1>
					<button onClick={() => setIsInspectorOpen(!isInspectorOpen)} className="p-2 hover:bg-slate-100 rounded-md text-slate-500 transition-colors">
						{isInspectorOpen ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
					</button>
				</header>

				<div className="flex-1 min-h-0 w-full relative flex flex-col">
					<ChatPane messages={messages} isStreaming={isStreaming} onSubmit={(q: string, m: string) => executeStream(q, m)} />
				</div>
			</div>

			{/* RIGHT PANE */}
			<div
				className={`${isInspectorOpen ? "w-[450px]" : "w-0"} transition-all duration-300 border-l border-slate-200 bg-slate-50 overflow-hidden flex-shrink-0`}>
				<InspectorPane isOpen={isInspectorOpen} events={events} agentState={agentState} tools={tools} />
			</div>
		</div>
	);
}
