import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {Link as LinkIcon} from "lucide-react";

interface MarkdownRendererProps {
	content: string;
}

export function MarkdownRenderer({content}: MarkdownRendererProps) {
	return (
		<ReactMarkdown
			remarkPlugins={[remarkGfm]}
			components={{
				// 1. Intercept and custom-style Links (Citations)
				a: ({node, href, children, ...props}) => {
					const linkText = children?.toString() || "";

					// Detect our backend citation formats: "Source" or "[1]"
					const isCitation = linkText.includes("Source") || /^\[\d+\]$/.test(linkText);

					if (isCitation) {
						return (
							<a
								href={href}
								target="_blank"
								rel="noopener noreferrer"
								title={href}
								className="inline-flex items-center justify-center gap-1 bg-emerald-50 text-emerald-600 border border-emerald-200 text-[10px] font-bold px-1.5 py-0.5 rounded shadow-sm ml-1 hover:bg-emerald-100 hover:text-emerald-700 transition-all no-underline align-middle"
								{...props}>
								<LinkIcon size={10} />
								{linkText}
							</a>
						);
					}

					// Standard hyperlinks
					return (
						<a
							href={href}
							target="_blank"
							rel="noopener noreferrer"
							className="text-indigo-600 hover:text-indigo-800 underline decoration-indigo-200 underline-offset-2 transition-colors"
							{...props}>
							{children}
						</a>
					);
				},

				// 2. Intercept and custom-style Code Blocks
				code: ({inline, className, children, ...props}: any) => {
					const match = /language-(\w+)/.exec(className || "");

					if (inline) {
						return (
							<code className="bg-slate-100 text-pink-600 px-1.5 py-0.5 rounded text-[13px] font-mono border border-slate-200" {...props}>
								{children}
							</code>
						);
					}

					return (
						<div className="relative my-4 group">
							{match && (
								<div className="absolute top-0 right-0 bg-slate-700 text-slate-300 text-[10px] uppercase font-bold px-2 py-1 rounded-bl-md rounded-tr-md">
									{match[1]}
								</div>
							)}
							<pre className="bg-slate-800 text-slate-50 p-4 rounded-lg overflow-x-auto border border-slate-700 shadow-sm text-[13px] font-mono leading-relaxed">
								<code className={className} {...props}>
									{children}
								</code>
							</pre>
						</div>
					);
				},

				// 3. Standard Typography Overrides
				p: ({children}) => <p className="mb-4 last:mb-0">{children}</p>,
				h1: ({children}) => <h1 className="text-xl font-bold text-slate-900 mt-6 mb-3">{children}</h1>,
				h2: ({children}) => <h2 className="text-lg font-bold text-slate-800 mt-5 mb-2">{children}</h2>,
				h3: ({children}) => <h3 className="text-base font-bold text-slate-800 mt-4 mb-2">{children}</h3>,
				ul: ({children}) => <ul className="list-disc list-outside ml-5 mb-4 space-y-1">{children}</ul>,
				ol: ({children}) => <ol className="list-decimal list-outside ml-5 mb-4 space-y-1">{children}</ol>,
				li: ({children}) => <li className="pl-1">{children}</li>,
				blockquote: ({children}) => (
					<blockquote className="border-l-4 border-slate-300 pl-4 py-1 my-4 text-slate-600 italic bg-slate-50 rounded-r-md">{children}</blockquote>
				),
			}}>
			{content}
		</ReactMarkdown>
	);
}
