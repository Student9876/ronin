"use client";

import {useChatStore, AgentSettings} from "@/store/useChatStore";
import {X} from "lucide-react";

export function SettingsModal({isOpen, onClose}: {isOpen: boolean; onClose: () => void}) {
	const {settings, setSettings} = useChatStore();

	if (!isOpen) return null;

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
			<div className="w-full max-w-md bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl p-6 space-y-6 animate-in fade-in zoom-in duration-200">
				<div className="flex items-center justify-between border-b border-neutral-800 pb-4">
					<h2 className="text-lg font-medium text-neutral-200 tracking-wide">Agent Configuration</h2>
					<button onClick={onClose} className="text-neutral-500 hover:text-neutral-300 transition-colors">
						<X className="w-5 h-5" />
					</button>
				</div>

				<div className="space-y-5">
					{/* Search Depth Control */}
					<div className="space-y-2">
						<label className="text-sm font-medium text-neutral-400">Search Depth</label>
						<div className="flex gap-2">
							{["quick", "comprehensive", "exhaustive"].map((depth) => (
								<button
									key={depth}
									onClick={() => setSettings({searchDepth: depth as AgentSettings["searchDepth"]})}
									className={`flex-1 py-2 text-xs font-medium uppercase tracking-wider rounded-lg border transition-colors ${
										settings.searchDepth === depth
											? "bg-neutral-200 text-neutral-900 border-neutral-200"
											: "bg-neutral-950 text-neutral-500 border-neutral-800 hover:border-neutral-600"
									}`}>
									{depth}
								</button>
							))}
						</div>
						<p className="text-xs text-neutral-600">Dictates the number of SearXNG permutations and scrape limits.</p>
					</div>

					{/* Evaluation Strictness Control */}
					<div className="space-y-2">
						<label className="text-sm font-medium text-neutral-400">Source Evaluation Strictness</label>
						<div className="flex gap-2">
							{["lenient", "strict"].map((level) => (
								<button
									key={level}
									onClick={() => setSettings({strictness: level as AgentSettings["strictness"]})}
									className={`flex-1 py-2 text-xs font-medium uppercase tracking-wider rounded-lg border transition-colors ${
										settings.strictness === level
											? "bg-neutral-200 text-neutral-900 border-neutral-200"
											: "bg-neutral-950 text-neutral-500 border-neutral-800 hover:border-neutral-600"
									}`}>
									{level}
								</button>
							))}
						</div>
						<p className="text-xs text-neutral-600">Strict mode drops any source lacking high factual density.</p>
					</div>
				</div>

				<div className="pt-4 flex justify-end">
					<button
						onClick={onClose}
						className="px-6 py-2 bg-neutral-200 hover:bg-white text-neutral-950 text-sm font-medium rounded-lg transition-colors">
						Done
					</button>
				</div>
			</div>
		</div>
	);
}
