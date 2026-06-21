import {Send, Cpu} from "lucide-react";
import {AgentSettings} from "@/store/useChatStore";

interface ChatInputProps {
	query: string;
	setQuery: (val: string) => void;
	handleSubmit: (e: React.FormEvent) => void;
	isStreaming: boolean;
	settings: AgentSettings;
	setSettings: (val: Partial<AgentSettings>) => void;
}

export function ChatInput({query, setQuery, handleSubmit, isStreaming, settings, setSettings}: ChatInputProps) {
	return (
		<footer className="p-4 md:p-6 bg-neutral-950 border-t border-neutral-900">
			<form
				onSubmit={handleSubmit}
				className="max-w-3xl mx-auto relative flex items-center bg-neutral-900 border border-neutral-800 rounded-xl transition-all focus-within:ring-1 focus-within:ring-neutral-700">
				<div className="pl-3 pr-2 flex items-center border-r border-neutral-800">
					<Cpu className="w-4 h-4 text-neutral-500 mr-2" />
					<select
						value={settings.mode}
						onChange={(e) => setSettings({mode: e.target.value as "general" | "code"})}
						disabled={isStreaming}
						className="bg-transparent text-sm text-neutral-300 focus:outline-none disabled:opacity-50 appearance-none cursor-pointer">
						<option value="general">General</option>
						<option value="code" disabled>Code</option>
					</select>
				</div>

				<input
					type="text"
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					disabled={isStreaming}
					placeholder={settings.mode === "code" ? "Code mode..." : "Ask a general question..."}
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
	);
}
