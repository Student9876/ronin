"use client";

import {useEffect, useState} from "react";
import {useRouter, usePathname} from "next/navigation";
import {useChatStore} from "@/store/useChatStore";
import {Compass, Plus, Settings, User} from "lucide-react";
import {SettingsModal} from "@/components/chat/SettingsModal";
import {SidebarThread} from "@/components/chat/SidebarThread";

export function Sidebar() {
	const router = useRouter();
	const pathname = usePathname();
	const {threads, fetchThreads, createThread, isStreaming} = useChatStore();
	const [isSettingsOpen, setIsSettingsOpen] = useState(false);

	useEffect(() => {
		fetchThreads();
	}, [fetchThreads]);

	const handleNewChat = async () => {
		if (isStreaming) return;
		const newId = await createThread();
		router.push(`/chat/${newId}`);
	};

	return (
		<div className="flex flex-col h-full w-full bg-slate-50 text-slate-700 font-sans">
			{/* Header */}
			<div className="h-14 flex items-center px-4 border-b border-slate-200 flex-shrink-0">
				<div className="flex items-center gap-2 text-slate-800">
					<Compass size={18} className="text-emerald-600" />
					<span className="font-bold tracking-widest text-sm uppercase">Ronin</span>
				</div>
			</div>

			{/* New Research Button */}
			<div className="p-3 flex-shrink-0">
				<button
					onClick={handleNewChat}
					disabled={isStreaming}
					className="flex items-center justify-center gap-2 w-full bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2.5 rounded-md text-sm font-medium transition-all shadow-sm disabled:opacity-50 disabled:hover:bg-emerald-600">
					<Plus size={16} />
					New Research
				</button>
			</div>

			{/* Thread List */}
			<div className="flex-1 overflow-y-auto px-2 py-2 space-y-1 custom-scrollbar">
				<div className="px-2 py-1 text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">Recent Activity</div>

				{Array.isArray(threads) &&
					threads.map((thread, index) => {
						const safeKey = thread?.id ? thread.id : `temp-key-${index}`;
						return <SidebarThread key={safeKey} thread={thread} isActive={pathname === `/chat/${thread?.id}`} />;
					})}
			</div>

			{/* Footer / Settings Trigger */}
			<div className="p-3 border-t border-slate-200 flex items-center gap-3 flex-shrink-0 bg-slate-100">
				<div className="w-8 h-8 rounded-md bg-slate-200 flex items-center justify-center text-slate-600 flex-shrink-0">
					<User size={15} />
				</div>
				<div className="flex-1 truncate text-sm font-medium text-slate-700">Developer</div>
				<button
					onClick={() => setIsSettingsOpen(true)}
					className="text-slate-400 hover:text-slate-700 transition-colors p-1 rounded hover:bg-slate-200">
					<Settings size={16} />
				</button>
			</div>

			<SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
		</div>
	);
}
