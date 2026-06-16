"use client";

import {useState} from "react";
import {Activity, Database, Wrench, CheckCircle2, Terminal} from "lucide-react";

// Match the type we exported from the hook
export type AgentEvent = {
	id: string;
	node: string;
	msg: string;
	time: string;
};

interface InspectorPaneProps {
	isOpen: boolean;
	events: AgentEvent[]; // Now accepting live events from the stream hook
	agentState: any;
	tools: any[];
}

export function InspectorPane({isOpen, events, agentState, tools}: InspectorPaneProps) {
	const [activeTab, setActiveTab] = useState<"events" | "state" | "tools">("events");

	// Prevent rendering complex internals if the pane is fully collapsed to save DOM memory
	if (!isOpen) return null;

	// ------------------------------------------------------------------------

	return (
		<div className="flex flex-col h-full w-full min-w-[400px]">
			{/* Dev Header & Tabs */}
			<div className="flex-shrink-0 border-b border-slate-200 bg-slate-100/50 p-2">
				<div className="flex items-center justify-between px-2 pb-2">
					<span className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1">
						<Terminal size={14} /> Execution Telemetry
					</span>
					<span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" title="Agent is active"></span>
				</div>

				<div className="flex gap-1 p-1 bg-slate-200/50 rounded-lg">
					<TabButton active={activeTab === "events"} onClick={() => setActiveTab("events")} icon={<Activity size={14} />} label="Events" />
					<TabButton active={activeTab === "state"} onClick={() => setActiveTab("state")} icon={<Database size={14} />} label="State" />
					<TabButton active={activeTab === "tools"} onClick={() => setActiveTab("tools")} icon={<Wrench size={14} />} label="Tools" />
				</div>
			</div>

			{/* Tab Content Area */}
			<div className="flex-1 overflow-y-auto p-4 bg-slate-50 font-mono text-sm">
				{/* EVENTS TAB (Now Live) */}
				{activeTab === "events" && (
					<div className="space-y-4">
						{events.length === 0 && (
							<div className="text-xs text-slate-400 p-2 border border-dashed border-slate-300 rounded-md text-center">Awaiting execution...</div>
						)}
						{events.map((ev) => (
							<div key={ev.id} className="flex gap-3 text-slate-600">
								<div className="flex flex-col items-center mt-1">
									<CheckCircle2 size={14} className="text-emerald-500" />
									<div className="w-px h-full bg-slate-200 mt-1"></div>
								</div>
								<div className="flex-1 pb-4">
									<div className="flex justify-between items-baseline mb-1">
										<span className="text-xs font-bold text-slate-700 bg-slate-200 px-2 py-0.5 rounded">{ev.node}</span>
										<span className="text-[10px] text-slate-400">{ev.time}</span>
									</div>
									<p className="text-xs leading-relaxed">{ev.msg}</p>
								</div>
							</div>
						))}
					</div>
				)}

				{/* STATE TAB (Now Live) */}
				{activeTab === "state" && (
					<div className="rounded-md bg-slate-800 p-4 shadow-inner overflow-x-auto">
						{agentState ? (
							<pre className="text-xs text-emerald-400">{JSON.stringify(agentState, null, 2)}</pre>
						) : (
							<span className="text-xs text-slate-500">Awaiting state snapshot...</span>
						)}
					</div>
				)}

				{/* TOOLS TAB (Now Live) */}
				{activeTab === "tools" && (
					<div className="space-y-4">
						{tools.length === 0 && <div className="text-xs text-slate-400 p-2 border border-dashed border-slate-300 rounded-md text-center">No tools executed yet.</div>}
						{tools.map((tool, idx) => (
							<div key={tool.id || idx} className="border border-slate-200 rounded-lg bg-white overflow-hidden shadow-sm">
								<div className="bg-slate-100 px-3 py-2 flex items-center justify-between border-b border-slate-200">
									<div className="flex items-center gap-2">
										<Wrench size={14} className="text-indigo-500" />
										<span className="font-semibold text-slate-700 text-xs">{tool.name}</span>
									</div>
									<span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">{tool.status}</span>
								</div>
								<div className="p-3 space-y-3">
									<div>
										<span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider mb-1 block">Input Payload</span>
										<pre className="bg-slate-50 text-slate-600 p-2 rounded text-xs border border-slate-100 overflow-x-auto">
											{JSON.stringify(tool.input, null, 2)}
										</pre>
									</div>
									<div>
										<span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider mb-1 block">Raw Output</span>
										<pre className="bg-slate-800 text-slate-300 p-2 rounded text-xs overflow-x-auto h-24">{tool.output}</pre>
									</div>
								</div>
							</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
}

// Helper component for the segmented control tabs
function TabButton({active, onClick, icon, label}: {active: boolean; onClick: () => void; icon: React.ReactNode; label: string}) {
	return (
		<button
			onClick={onClick}
			className={`flex-1 flex items-center justify-center gap-2 py-1.5 rounded-md text-xs font-medium transition-all ${
				active ? "bg-white text-slate-800 shadow-sm ring-1 ring-slate-200/50" : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
			}`}>
			{icon} {label}
		</button>
	);
}
