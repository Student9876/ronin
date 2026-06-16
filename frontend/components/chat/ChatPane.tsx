"use client";

import {useState, useRef, useEffect} from "react";
import {Send, User, TerminalSquare, MessageSquare, Microscope} from "lucide-react";
import {MessageBubble} from "./MessageBubble";

export type Message = {
	id: string;
	role: "user" | "agent";
	content: string;
	isStreaming?: boolean;
};

export function ChatPane({messages, isStreaming, onSubmit}: any) {
	const [input, setInput] = useState("");
	// Track the active agent mode
	const [mode, setMode] = useState<"general" | "deep">("general");

	const messagesEndRef = useRef<HTMLDivElement>(null);
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	useEffect(() => {
		messagesEndRef.current?.scrollIntoView({behavior: "smooth"});
	}, [messages]);

	const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
		setInput(e.target.value);
		if (textareaRef.current) {
			textareaRef.current.style.height = "auto";
			textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
		}
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	};

	const handleSubmit = () => {
		if (!input.trim() || isStreaming) return;

		// Pass the dynamically selected mode to the backend hook
		onSubmit(input.trim(), mode);

		setInput("");
		if (textareaRef.current) textareaRef.current.style.height = "auto";
	};

	return (
		<div className="flex flex-col h-full w-full bg-white relative">
			{/* Message Feed Area */}
			<div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
				{messages.map((msg: Message, index: number) => (
					<div key={msg.id} className={`flex gap-4 max-w-4xl mx-auto ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
						<div
							className={`flex-shrink-0 flex items-center justify-center h-8 w-8 rounded-full ${
								msg.role === "user" ? "bg-slate-800 text-white" : "bg-emerald-100 text-emerald-700"
							}`}>
							{msg.role === "user" ? <User size={18} /> : <TerminalSquare size={18} />}
						</div>

						<div className="flex-1 min-w-0">
							<MessageBubble 
								msg={msg} 
								isLastMessage={index === messages.length - 1} 
								isStreaming={isStreaming} 
							/>
						</div>
					</div>
				))}
				<div ref={messagesEndRef} className="h-4" />
			</div>

			{/* Input Area with Integrated Mode Selector */}
			<div className="p-4 bg-white border-t border-slate-100">
				<div className="max-w-4xl mx-auto relative flex flex-col gap-2 bg-slate-50 border border-slate-200 rounded-2xl p-2 focus-within:ring-2 focus-within:ring-emerald-500/20 focus-within:border-emerald-500 transition-all">
					<textarea
						ref={textareaRef}
						value={input}
						onChange={handleInput}
						onKeyDown={handleKeyDown}
						placeholder="Instruct the agent... (Shift+Enter for new line)"
						className="w-full max-h-[200px] min-h-[44px] bg-transparent resize-none outline-none py-2 px-3 text-slate-800 placeholder:text-slate-400 text-[15px]"
						rows={1}
					/>

					{/* Bottom Toolbar: Mode Toggle & Submit */}
					<div className="flex items-center justify-between px-2 pb-1 pt-2 border-t border-slate-200/50">
						{/* Mode Segmented Control */}
						<div className="flex items-center gap-1 bg-slate-200/50 p-1 rounded-lg">
							<button
								onClick={() => setMode("general")}
								className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
									mode === "general"
										? "bg-white text-slate-800 shadow-sm ring-1 ring-slate-200"
										: "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
								}`}>
								<MessageSquare size={14} /> General Chat
							</button>
							<button
								onClick={() => setMode("deep")}
								className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
									mode === "deep"
										? "bg-emerald-50 text-emerald-700 shadow-sm ring-1 ring-emerald-200"
										: "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
								}`}>
								<Microscope size={14} /> Deep Research
							</button>
						</div>

						{/* Submit Button */}
						<button
							onClick={handleSubmit}
							disabled={!input.trim() || isStreaming}
							className="flex-shrink-0 h-8 w-8 flex items-center justify-center rounded-lg bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-50 disabled:hover:bg-slate-800 transition-colors">
							<Send size={14} className="ml-0.5" />
						</button>
					</div>
				</div>
				<div className="max-w-4xl mx-auto text-center mt-2">
					<span className="text-xs text-slate-400">Ronin Engine can make mistakes. Verify critical configurations.</span>
				</div>
			</div>
		</div>
	);
}
