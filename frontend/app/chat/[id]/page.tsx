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
		messages, fetchMessages, isStreaming, fetchThreads, settings,
		events, agentState, tools, executeStream
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
				executeStream(threadId, initialQuery, initialMode || settings.mode);
				router.replace(`/chat/${threadId}`);
			}, 100);
		}
	}, [searchParams, router, threadId, settings.mode]);

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
					<ChatPane messages={messages} isStreaming={isStreaming} onSubmit={(q: string, m: string) => executeStream(threadId, q, m)} />
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
