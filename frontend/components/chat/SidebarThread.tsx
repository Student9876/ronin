"use client";

import {useState, useRef, useEffect} from "react";
import {useRouter} from "next/navigation";
import {MessageSquare, MoreVertical, Edit2, Trash2, Share, Check, X} from "lucide-react";
import {Thread, useChatStore} from "@/store/useChatStore";

export function SidebarThread({thread, isActive}: {thread: Thread; isActive: boolean}) {
	const router = useRouter();
	const {deleteThread, renameThread} = useChatStore();

	const [isMenuOpen, setIsMenuOpen] = useState(false);
	const [isEditing, setIsEditing] = useState(false);
	const [editTitle, setEditTitle] = useState(thread.title);
	const menuRef = useRef<HTMLDivElement>(null);

	// Close dropdown when clicking outside
	useEffect(() => {
		const handleClickOutside = (event: MouseEvent) => {
			if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
				setIsMenuOpen(false);
			}
		};
		if (isMenuOpen) document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, [isMenuOpen]);

	const handleRenameSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (editTitle.trim() && editTitle !== thread.title) {
			await renameThread(thread.id, editTitle);
		}
		setIsEditing(false);
	};

	const handleDelete = async () => {
		await deleteThread(thread.id);
		if (isActive) router.push("/");
	};

	const handleShare = async () => {
		// Copies the current thread URL to the clipboard
		const url = `${window.location.origin}/chat/${thread.id}`;
		await navigator.clipboard.writeText(url);
		setIsMenuOpen(false);
		alert("Chat link copied to clipboard!"); // Replace with a toast notification later
	};

	if (isEditing) {
		return (
			<form onSubmit={handleRenameSubmit} className="flex items-center gap-2 px-3 py-2 bg-slate-200 rounded-lg">
				<MessageSquare className="w-4 h-4 shrink-0 text-slate-500" />
				<input
					type="text"
					value={editTitle}
					onChange={(e) => setEditTitle(e.target.value)}
					className="flex-1 bg-transparent text-sm text-slate-800 focus:outline-none"
					autoFocus
					onBlur={() => setIsEditing(false)}
				/>
				<button type="submit" className="text-emerald-600 hover:text-emerald-500">
					<Check className="w-4 h-4" />
				</button>
				<button type="button" onClick={() => setIsEditing(false)} className="text-slate-400 hover:text-slate-600">
					<X className="w-4 h-4" />
				</button>
			</form>
		);
	}

	return (
		<div className="relative" ref={menuRef}>
			<button
				onClick={() => router.push(`/chat/${thread.id}`)}
				className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-sm rounded-lg text-left transition-all group ${
					isActive ? "bg-slate-200 text-slate-800" : "text-slate-500 hover:bg-slate-200 hover:text-slate-700"
				}`}>
				<div className="flex items-center gap-2 truncate overflow-hidden">
					<MessageSquare className="w-4 h-4 shrink-0" />
					<span className="truncate">{thread.title}</span>
				</div>

				{/* The 3-Dots Button (Only appears on hover or if menu is open) */}
				<div
					onClick={(e) => {
						e.stopPropagation();
						setIsMenuOpen(!isMenuOpen);
					}}
					className={`p-1 rounded hover:bg-slate-300 transition-colors ${isMenuOpen ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}>
					<MoreVertical className="w-4 h-4" />
				</div>
			</button>

			{/* The Dropdown Menu */}
			{isMenuOpen && (
				<div className="absolute right-0 top-10 w-40 bg-white border border-slate-200 rounded-lg shadow-xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-100">
					<button
						onClick={(e) => {
							e.stopPropagation();
							handleShare();
						}}
						className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors">
						<Share className="w-3.5 h-3.5" /> Share
					</button>
					<button
						onClick={(e) => {
							e.stopPropagation();
                            setEditTitle(thread.title);
							setIsEditing(true);
							setIsMenuOpen(false);
						}}
						className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors">
						<Edit2 className="w-3.5 h-3.5" /> Rename
					</button>
					<div className="h-px bg-slate-200 w-full" />
					<button
						onClick={(e) => {
							e.stopPropagation();
							handleDelete();
						}}
						className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-500 hover:bg-slate-100 hover:text-red-600 transition-colors">
						<Trash2 className="w-3.5 h-3.5" /> Delete
					</button>
				</div>
			)}
		</div>
	);
}
