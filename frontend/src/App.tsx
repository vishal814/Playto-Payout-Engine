import React, { useState, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { RefreshCw, CheckCircle, XCircle, Clock, ArrowUpRight, ArrowDownLeft } from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api/v1';
const MERCHANT_ID = '0776f8a9-62a8-4ba4-9ecb-8fb584343519';

export default function App() {
  const [merchant, setMerchant] = useState<any>(null);
  const [payouts, setPayouts] = useState<any[]>([]);
  const [ledger, setLedger] = useState<any[]>([]);
  
  const [amount, setAmount] = useState('');
  const [bankAccount, setBankAccount] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchData = async () => {
    try {
      const [mRes, pRes, lRes] = await Promise.all([
        fetch(`${API_BASE}/merchants/${MERCHANT_ID}`),
        fetch(`${API_BASE}/merchants/${MERCHANT_ID}/payouts`),
        fetch(`${API_BASE}/merchants/${MERCHANT_ID}/ledger`),
      ]);
      if (mRes.ok) setMerchant(await mRes.json());
      if (pRes.ok) setPayouts(await pRes.json());
      if (lRes.ok) setLedger(await lRes.json());
    } catch (e) {
      console.error('Fetch failed');
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000); // Poll every 3s
    return () => clearInterval(interval);
  }, []);

  const requestPayout = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    const idempotencyKey = uuidv4();
    
    try {
      const res = await fetch(`${API_BASE}/payouts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
        },
        body: JSON.stringify({
          merchant: MERCHANT_ID,
          amount_paise: parseInt(amount) * 100, // INR to Paise
          bank_account_id: bankAccount,
        }),
      });
      
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Payout failed');
      } else {
        setAmount('');
        setBankAccount('');
        fetchData(); // instantly update view
      }
    } catch (e) {
      setError('Network error');
    }
    setLoading(false);
  };

  if (!merchant) {
    return <div className="flex h-screen items-center justify-center text-gray-500">Loading Dashboard...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8 text-gray-800 font-sans">
      <div className="max-w-5xl mx-auto space-y-8">
        
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-gray-900">{merchant.name}</h1>
            <p className="text-sm text-gray-500">Merchant ID: {merchant.id}</p>
          </div>
          <div className="flex gap-8 mt-4 md:mt-0">
            <div className="text-right">
              <p className="text-sm font-medium text-gray-500">Available Balance</p>
              <p className="text-3xl font-bold text-green-600">₹{(merchant.available_balance_paise / 100).toFixed(2)}</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-medium text-gray-500">Held Balance</p>
              <p className="text-3xl font-bold text-orange-500">₹{(merchant.held_balance_paise / 100).toFixed(2)}</p>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          
          {/* Request Form */}
          <div className="md:col-span-1 bg-white p-6 rounded-2xl shadow-sm border border-gray-100 h-fit">
            <h2 className="text-lg font-semibold mb-4 text-gray-900">Request Payout</h2>
            {error && <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4 text-sm font-medium">{error}</div>}
            
            <form onSubmit={requestPayout} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Amount (INR)</label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-gray-500">₹</span>
                  <input 
                    type="number" 
                    required min="1" max={merchant.available_balance_paise / 100}
                    className="w-full border border-gray-200 rounded-lg p-2.5 pl-8 focus:ring-2 focus:ring-black outline-none transition-all" 
                    value={amount} 
                    onChange={e => setAmount(e.target.value)} 
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Bank Account ID</label>
                <input 
                  type="text" required placeholder="e.g. HDFC123456"
                  className="w-full border border-gray-200 rounded-lg p-2.5 focus:ring-2 focus:ring-black outline-none transition-all" 
                  value={bankAccount} 
                  onChange={e => setBankAccount(e.target.value)} 
                />
              </div>
              <button 
                type="submit" disabled={loading || merchant.available_balance_paise <= 0}
                className="w-full bg-black text-white font-medium py-3 rounded-xl hover:bg-gray-800 disabled:opacity-50 transition-colors shadow-sm"
              >
                {loading ? 'Processing...' : 'Withdraw Funds'}
              </button>
            </form>
          </div>

          {/* Tables */}
          <div className="md:col-span-2 space-y-8">
            
            {/* Payouts Table */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="p-6 border-b border-gray-100 flex justify-between items-center">
                <h2 className="text-lg font-semibold text-gray-900">Recent Payouts</h2>
                <div className="flex items-center gap-2 text-xs text-gray-500 bg-gray-50 px-3 py-1 rounded-full">
                  <RefreshCw size={12} className="animate-spin" /> Live updates
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-500 bg-gray-50 uppercase">
                    <tr>
                      <th className="px-6 py-3">Amount</th>
                      <th className="px-6 py-3">Bank Account</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payouts.length === 0 ? (
                      <tr><td colSpan={4} className="px-6 py-8 text-center text-gray-500">No payouts yet.</td></tr>
                    ) : payouts.map(p => (
                      <tr key={p.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50">
                        <td className="px-6 py-4 font-medium text-gray-900">₹{(p.amount_paise / 100).toFixed(2)}</td>
                        <td className="px-6 py-4 text-gray-500">{p.bank_account_id}</td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
                            ${p.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : 
                              p.status === 'FAILED' ? 'bg-red-100 text-red-700' : 
                              'bg-orange-100 text-orange-700'}`}>
                            {p.status === 'COMPLETED' && <CheckCircle size={12} />}
                            {p.status === 'FAILED' && <XCircle size={12} />}
                            {(p.status === 'PENDING' || p.status === 'PROCESSING') && <Clock size={12} />}
                            {p.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-400">{new Date(p.created_at).toLocaleTimeString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Ledger Table */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
              <div className="p-6 border-b border-gray-100">
                <h2 className="text-lg font-semibold text-gray-900">Ledger History</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-500 bg-gray-50 uppercase">
                    <tr>
                      <th className="px-6 py-3">Type</th>
                      <th className="px-6 py-3">Description</th>
                      <th className="px-6 py-3 text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.map(entry => (
                      <tr key={entry.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50">
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center gap-1.5 font-medium ${entry.entry_type === 'CREDIT' ? 'text-green-600' : 'text-gray-900'}`}>
                            {entry.entry_type === 'CREDIT' ? <ArrowDownLeft size={16} /> : <ArrowUpRight size={16} />}
                            {entry.entry_type}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-500">{entry.description}</td>
                        <td className={`px-6 py-4 text-right font-medium ${entry.entry_type === 'CREDIT' ? 'text-green-600' : 'text-gray-900'}`}>
                          {entry.entry_type === 'CREDIT' ? '+' : '-'}₹{(entry.amount_paise / 100).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
