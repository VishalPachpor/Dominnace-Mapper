export default function Topbar() {
    return (
        <div className="flex justify-between items-center p-4 bg-slate-900 border-b border-slate-800 text-white">
            <div className="flex items-center gap-4">
                <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-blue-600 bg-clip-text text-transparent">DominanceBot</h1>
            </div>

            <div className="flex items-center gap-6">
                <div className="flex items-center gap-2 bg-slate-800 px-3 py-1 rounded-full border border-slate-700">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                    <span className="text-sm font-medium text-green-400">Bot Running</span>
                </div>

                <button className="flex justify-center items-center w-8 h-8 rounded-full bg-blue-600 hover:bg-blue-500 text-sm font-bold transition-colors shadow-blue-900/50 shadow-lg">
                    U
                </button>
            </div>
        </div>
    );
}
