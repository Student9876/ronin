"use client";

import "./globals.css";
import {useEffect, useState} from "react";
import {useRouter, usePathname} from "next/navigation";
import {useChatStore} from "@/store/useChatStore";
import {Plus, Settings} from "lucide-react"; // Removed MessageSquare, it's used inside SidebarThread now
import {SettingsModal} from "@/components/SettingsModal";
import {SidebarThread} from "@/components/SidebarThread";

export default function RootLayout({children}: {children: React.ReactNode}) {
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
		<html lang="en">
			<body className="antialiased font-sans bg-neutral-950 text-neutral-50 flex h-screen overflow-hidden">
				{/* Sidebar */}
				<aside className="w-64 bg-neutral-900 border-r border-neutral-800 flex flex-col transition-all">
					{/* Header with Settings Trigger */}
					<div className="p-4 flex items-center justify-between border-b border-neutral-800">
						<span className="font-semibold tracking-widest text-neutral-400 text-sm">RONIN</span>
						<button onClick={() => setIsSettingsOpen(true)} className="text-neutral-500 hover:text-neutral-300">
							<Settings className="w-4 h-4" />
						</button>
					</div>

					{/* New Research Button */}
					<div className="p-3">
						<button
							onClick={handleNewChat}
							disabled={isStreaming}
							className="w-full flex items-center gap-2 px-3 py-2 bg-neutral-800 hover:bg-neutral-700 text-sm rounded-lg transition-colors disabled:opacity-50">
							<Plus className="w-4 h-4" />
							New Research
						</button>
					</div>

					{/* Thread List */}
					<div className="flex-1 overflow-y-auto p-3 flex flex-col gap-1">
						{Array.isArray(threads) &&
							threads.map((thread, index) => {
								const safeKey = thread?.id ? thread.id : `temp-key-${index}`;

								if (!thread?.id) {
									console.warn("Malformed thread object detected from backend:", thread);
								}

								return (
									<SidebarThread
										key={safeKey}
										thread={thread}
										isActive={pathname === `/chat/${thread?.id}`}
									/>
								);
							})}
					</div>
				</aside>

				{/* Main Content Area */}
				<main className="flex-1 flex flex-col min-w-0">{children}</main>

				<SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
			</body>
		</html>
	);
}
