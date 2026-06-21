"use client";
import {useState} from "react";
import {useRouter} from "next/navigation";
import {useChatStore} from "@/store/useChatStore";
import {PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen} from "lucide-react";
import {ChatPane} from "@/components/chat/ChatPane";
import {InspectorPane} from "@/components/chat/InspectorPane";
import {Sidebar} from "@/components/chat/Sidebar";

export default function AgentWorkspace() {
	const router = useRouter();
	const {createThread, setPendingQuery} = useChatStore();
	const [isSidebarOpen, setIsSidebarOpen] = useState(true);
	const [isInspectorOpen, setIsInspectorOpen] = useState(true);
	const [isCreating, setIsCreating] = useState(false);

	const handleNewQuery = async (query: string, mode: string) => {
		setIsCreating(true);
		const newId = await createThread();
		setPendingQuery({ query, mode });
		router.push(`/chat/${newId}`);
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
					<h1 className="font-semibold text-slate-700 tracking-tight">Ronin Engine Workspace</h1>
					<button onClick={() => setIsInspectorOpen(!isInspectorOpen)} className="p-2 hover:bg-slate-100 rounded-md text-slate-500 transition-colors">
						{isInspectorOpen ? <PanelRightClose size={20} /> : <PanelRightOpen size={20} />}
					</button>
				</header>

				<div className="flex-1 min-h-0 w-full relative flex flex-col">
					<div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-8 flex flex-col items-center justify-center text-slate-400">
						<div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mb-4">
							<span className="text-2xl">🤖</span>
						</div>
						<h2 className="text-xl font-medium text-slate-600">How can I help you today?</h2>
						<p className="text-sm">Start typing below to initiate a new research session.</p>
					</div>

					<ChatPane messages={[]} isStreaming={isCreating} onSubmit={handleNewQuery} />
				</div>
			</div>

			{/* RIGHT PANE */}
			<div
				className={`${isInspectorOpen ? "w-[450px]" : "w-0"} transition-all duration-300 border-l border-slate-200 bg-slate-50 overflow-hidden flex-shrink-0`}>
				<InspectorPane isOpen={isInspectorOpen} events={[]} agentState={null} tools={[]} />
			</div>
		</div>
	);
}
