import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {Loader2, CheckCircle2} from "lucide-react";
import type {Components} from "react-markdown";
import {Prism as SyntaxHighlighter} from "react-syntax-highlighter";
import {vscDarkPlus} from "react-syntax-highlighter/dist/esm/styles/prism";
import {Message} from "@/store/useChatStore";

interface MessageBubbleProps {
	msg: Message;
	isLastMessage: boolean;
	isStreaming: boolean;
}

export function MessageBubble({msg, isLastMessage, isStreaming}: MessageBubbleProps) {
	return (
		<div className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
			{msg.role === "user" && <div className="bg-neutral-800 px-6 py-4 rounded-2xl max-w-[80%] text-neutral-200 shadow-sm">{msg.content}</div>}

			{msg.role === "agent" && (
				<div className="w-full space-y-4">
					{msg.statuses && msg.statuses.length > 0 && (
						<div className="flex flex-col space-y-2 border-l-2 border-neutral-800 pl-4 py-2">
							{msg.statuses.map((status, idx) => (
								<div key={idx} className="flex items-center space-x-3 text-sm text-neutral-400 font-mono">
									{idx === msg.statuses!.length - 1 && isStreaming && isLastMessage ? (
										<Loader2 className="w-4 h-4 animate-spin text-blue-500" />
									) : (
										<CheckCircle2 className="w-4 h-4 text-emerald-500" />
									)}
									<span>{status.message}</span>
								</div>
							))}
						</div>
					)}

					{msg.content && (
						<div className="prose prose-invert max-w-none prose-p:leading-relaxed prose-headings:text-neutral-200 prose-a:text-blue-400 prose-strong:text-neutral-200 bg-neutral-900/30 p-6 rounded-xl border border-neutral-800/50">
							<ReactMarkdown
								remarkPlugins={[remarkGfm]}
								components={
									{
										code({
											inline,
											className,
											children,
											style: _style,
											...codeProps
										}: React.ComponentPropsWithoutRef<"code"> & {inline?: boolean}) {
											void _style;
											const match = /language-(\w+)/.exec(className || "");
											return !inline && match ? (
												<div className="rounded-md overflow-hidden my-4 border border-neutral-800">
													<div className="bg-neutral-900 px-4 py-2 text-xs text-neutral-400 font-mono border-b border-neutral-800 uppercase tracking-wider">
														{match[1]}
													</div>
													<SyntaxHighlighter
														language={match[1]}
														style={vscDarkPlus as Record<string, React.CSSProperties>}
														PreTag="div"
														customStyle={{margin: 0, padding: "1rem", background: "#0a0a0a"}}
														{...codeProps}>
														{String(children).replace(/\n$/, "")}
													</SyntaxHighlighter>
												</div>
											) : (
												<code
													className="bg-neutral-800 text-neutral-300 px-1.5 py-0.5 rounded-md font-mono text-sm before:hidden after:hidden"
													{...codeProps}>
													{children}
												</code>
											);
										},
										a({children, ...props}: React.ComponentPropsWithoutRef<"a">) {
											const text = String(children);
											if (/^\[\d+\]$/.test(text)) {
												return (
													<a
														{...props}
														className="inline-flex items-center justify-center w-5 h-5 ml-1 text-[10px] font-medium text-neutral-400 bg-neutral-800 rounded-full hover:bg-neutral-700 hover:text-neutral-200 transition-colors no-underline align-super cursor-pointer"
														target="_blank"
														rel="noopener noreferrer">
														{text.replace(/\[|\]/g, "")}
													</a>
												);
											}
											return (
												<a
													{...props}
													className="text-blue-400 hover:text-blue-300 underline decoration-blue-400/30 underline-offset-2 transition-colors"
													target="_blank"
													rel="noopener noreferrer">
													{children}
												</a>
											);
										},
										table({...props}: React.ComponentPropsWithoutRef<"table">) {
											return (
												<div className="overflow-x-auto my-6 rounded-lg border border-neutral-800">
													<table className="w-full text-sm text-left m-0" {...props} />
												</div>
											);
										},
										th({...props}: React.ComponentPropsWithoutRef<"th">) {
											return (
												<th className="bg-neutral-900 px-4 py-3 font-medium text-neutral-300 border-b border-neutral-800" {...props} />
											);
										},
										td({...props}: React.ComponentPropsWithoutRef<"td">) {
											return <td className="px-4 py-3 border-b border-neutral-800/50 text-neutral-400" {...props} />;
										},
									} as Components
								}>
								{msg.content}
							</ReactMarkdown>
						</div>
					)}
				</div>
			)}
		</div>
	);
}
