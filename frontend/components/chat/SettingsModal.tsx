"use client";

import {useChatStore, AgentSettings} from "@/store/useChatStore";
import {X} from "lucide-react";

export function SettingsModal({isOpen, onClose}: {isOpen: boolean; onClose: () => void}) {
	const {settings, setSettings} = useChatStore();

	if (!isOpen) return null;

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
			<div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-2xl p-6 space-y-6 animate-in fade-in zoom-in duration-200">
				<div className="flex items-center justify-between border-b border-slate-100 pb-4">
					<h2 className="text-lg font-semibold text-slate-800 tracking-wide">Agent Configuration</h2>
					<button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
						<X className="w-5 h-5" />
					</button>
				</div>

				<div className="space-y-5">
					{/* Search Depth Control */}
					<div className="space-y-2">
						<label className="text-sm font-medium text-slate-600">Search Depth</label>
						<div className="flex gap-2">
							{["quick", "comprehensive", "exhaustive"].map((depth) => (
								<button
									key={depth}
									onClick={() => setSettings({searchDepth: depth as AgentSettings["searchDepth"]})}
									className={`flex-1 py-2 text-xs font-medium uppercase tracking-wider rounded-lg border transition-colors ${
										settings.searchDepth === depth
											? "bg-slate-800 text-white border-slate-800 shadow-sm"
											: "bg-slate-50 text-slate-500 border-slate-200 hover:border-slate-400 hover:text-slate-700"
									}`}>
									{depth}
								</button>
							))}
						</div>
						<p className="text-xs text-slate-400">Dictates the number of SearXNG permutations and scrape limits.</p>
					</div>

					{/* Evaluation Strictness Control */}
					<div className="space-y-2">
						<label className="text-sm font-medium text-slate-600">Source Evaluation Strictness</label>
						<div className="flex gap-2">
							{["lenient", "strict"].map((level) => (
								<button
									key={level}
									onClick={() => setSettings({strictness: level as AgentSettings["strictness"]})}
									className={`flex-1 py-2 text-xs font-medium uppercase tracking-wider rounded-lg border transition-colors ${
										settings.strictness === level
											? "bg-slate-800 text-white border-slate-800 shadow-sm"
											: "bg-slate-50 text-slate-500 border-slate-200 hover:border-slate-400 hover:text-slate-700"
									}`}>
									{level}
								</button>
							))}
						</div>
						<p className="text-xs text-slate-400">Strict mode drops any source lacking high factual density.</p>
					</div>
				</div>

				<div className="pt-4 flex justify-end">
					<button
						onClick={onClose}
						className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors">
						Done
					</button>
				</div>
			</div>
		</div>
	);
}
