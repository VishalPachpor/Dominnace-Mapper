export default function StatCard({ title, value, positive }: { title: string, value: string, positive?: boolean }) {
    return (
        <div className="p-6 bg-slate-800 border border-slate-700 hover:border-slate-600 transition-colors rounded-2xl shadow-sm">
            <h3 className="text-slate-400 text-sm font-semibold mb-2 uppercase tracking-wide">{title}</h3>
            <p className={`text-3xl font-bold tracking-tight ${positive !== undefined ? (positive ? 'text-green-500' : 'text-red-500') : 'text-white'}`}>
                {value}
            </p>
        </div>
    );
}
