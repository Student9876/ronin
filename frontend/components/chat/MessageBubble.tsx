"use client";

import {Loader2, CheckCircle2} from "lucide-react";
import {Message} from "@/store/useChatStore";
import {MarkdownRenderer} from "../MarkdownRenderer";

interface MessageBubbleProps {
	msg: Message;
	isLastMessage: boolean;
	isStreaming: boolean;
}

export function MessageBubble({msg, isLastMessage, isStreaming}: MessageBubbleProps) {
	return (
		<div className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"} w-full space-y-2`}>
			{msg.role === "user" && (
				<div className="bg-slate-100 px-4 py-2.5 rounded-2xl max-w-[80%] text-slate-800 rounded-tr-sm border border-slate-200/50 text-[15px] leading-relaxed shadow-sm">
					{msg.content}
				</div>
			)}

			{msg.role === "agent" && (
				<div className="w-full space-y-4">
					{msg.statuses && msg.statuses.length > 0 && (
						<div className="flex flex-col space-y-2 border-l-2 border-slate-200 pl-4 py-1 my-2">
							{msg.statuses.map((status, idx) => (
								<div key={idx} className="flex items-center space-x-2 text-xs text-slate-500 font-medium font-sans">
									{idx === msg.statuses!.length - 1 && isStreaming && isLastMessage ? (
										<Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-600" />
									) : (
										<CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
									)}
									<span>{status.message}</span>
								</div>
							))}
						</div>
					)}

					{msg.content && (
						<div className="leading-relaxed text-[15px] prose prose-slate max-w-none w-full bg-white text-slate-800">
							<MarkdownRenderer content={msg.content} />
						</div>
					)}
				</div>
			)}
		</div>
	);
}
