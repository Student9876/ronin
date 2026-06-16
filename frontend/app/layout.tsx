import "./globals.css";

export const metadata = {
	title: "Ronin Engine Workspace",
	description: "Deep Research and Code Analysis Agent",
};

export default function RootLayout({children}: {children: React.ReactNode}) {
	return (
		<html lang="en">
			<body className="antialiased font-sans bg-slate-50 text-slate-900 m-0 p-0 overflow-hidden">{children}</body>
		</html>
	);
}
