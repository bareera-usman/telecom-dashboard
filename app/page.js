
'use client';

import { useState, useEffect } from 'react';
import { Upload, Users, FileText, Trash2, AlertCircle, CheckCircle, BarChart3, PieChart, Activity, TrendingUp } from 'lucide-react';

const API_BASE = typeof window !== 'undefined' && window.location.hostname.includes('vercel.app') 
  ? 'https://telecom-dashboard-production.up.railway.app' 
  : process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function TelecomDashboard() {
  const [stats, setStats] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [providerComparison, setProviderComparison] = useState(null);
  const [topSpenders, setTopSpenders] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [statsRes, invoicesRes, comparisonRes, topSpendersRes] = await Promise.all([
        fetch(`${API_BASE}/api/stats`),
        fetch(`${API_BASE}/api/invoices`),
        fetch(`${API_BASE}/api/analytics/provider-comparison`),
        fetch(`${API_BASE}/api/analytics/top-vodafone-spenders`)
      ]);

      const statsData = await statsRes.json();
      const invoicesData = await invoicesRes.json();
      const comparisonData = await comparisonRes.json();

      let topSpendersData = [];
      if (topSpendersRes.ok) {
        const json = await topSpendersRes.json();
        topSpendersData = json.top_spenders || [];
      } else {
        // Endpoint failed – keep empty list but don't break UI
        console.error('Top spenders endpoint failed');
      }

      setStats(statsData.stats || null);
      setInvoices(invoicesData.invoices || []);
      setProviderComparison(comparisonData || null);
      setTopSpenders(topSpendersData);
      setLoading(false);
    } catch (error) {
      console.error('Error loading data:', error);
      setLoading(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    setUploadMessage(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/api/upload-invoice`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();

      if (response.ok) {
        setUploadMessage({ type: 'success', text: data.message });
        await loadDashboardData();
      } else {
        setUploadMessage({ type: 'error', text: data.detail || 'Upload failed' });
      }
    } catch (error) {
      setUploadMessage({ type: 'error', text: 'Network error occurred' });
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleDeleteInvoice = async (invoiceId) => {
    if (!confirm('Are you sure you want to delete this invoice?')) return;
    try {
      // FIXED path to match backend route
      const response = await fetch(`${API_BASE}/api/invoice/${invoiceId}`, { method: 'DELETE' });
      if (response.ok) await loadDashboardData();
    } catch (error) {
      console.error('Error deleting invoice:', error);
    }
  };

  const formatCurrency = (amount) => new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'GBP',
    minimumFractionDigits: 2,
  }).format(amount ?? 0);

  const formatDate = (dateString) => new Date(dateString).toLocaleDateString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-16 h-16 border-4 border-red-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Telecom Cost Analytics</h1>
              <p className="text-sm text-slate-600 mt-1">Provider comparison &amp; savings analysis</p>
            </div>
            <div>
              <input type="file" accept=".pdf" onChange={handleFileUpload} disabled={uploading} className="hidden" id="invoice-upload" />
              <label htmlFor="invoice-upload" className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition cursor-pointer ${
                uploading ? 'bg-slate-300 text-slate-500 cursor-not-allowed' : 'bg-red-600 text-white hover:bg-red-700 shadow-lg'
              }`}>
                <Upload className="w-5 h-5" />
                {uploading ? 'Uploading...' : 'Upload Invoice'}
              </label>
            </div>
          </div>
          {uploadMessage && (
            <div className={`mt-4 p-4 rounded-lg flex items-start gap-3 ${
              uploadMessage.type === 'success' ? 'bg-blue-50 border border-blue-200' : 'bg-red-50 border border-red-200'
            }`}>
              {uploadMessage.type === 'success' ? <CheckCircle className="w-5 h-5 text-blue-600" /> : <AlertCircle className="w-5 h-5 text-red-600" />}
              <p className={uploadMessage.type === 'success' ? 'text-blue-900' : 'text-red-900'}>{uploadMessage.text}</p>
            </div>
          )}
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1">
            {[
              { id: 'overview', label: 'Overview', icon: BarChart3 },
              { id: 'comparison', label: 'Provider Comparison', icon: PieChart },
              { id: 'spenders', label: 'Top Spenders', icon: Users },
              { id: 'invoices', label: 'Invoice Details', icon: FileText }
            ].map((tab) => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-6 py-4 font-semibold transition border-b-2 ${
                  activeTab === tab.id ? 'text-red-600 border-red-600' : 'text-slate-600 border-transparent hover:text-slate-900'
                }`}>
                <tab.icon className="w-5 h-5" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'overview' && <OverviewTab stats={stats} providerComparison={providerComparison} formatCurrency={formatCurrency} />}
        {activeTab === 'comparison' && <ComparisonTab providerComparison={providerComparison} formatCurrency={formatCurrency} />}
        {activeTab === 'spenders' && <TopSpendersTab topSpenders={topSpenders} formatCurrency={formatCurrency} />}
        {activeTab === 'invoices' && <InvoicesTab invoices={invoices} formatCurrency={formatCurrency} formatDate={formatDate} handleDeleteInvoice={handleDeleteInvoice} />}
      </main>
    </div>
  );
}

function OverviewTab({ stats, providerComparison, formatCurrency }) {
  if (!stats || !providerComparison || !providerComparison.savings) {
    return (
      <div className="text-center py-12">
        <FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
        <p className="text-slate-600">Upload invoices to see analytics</p>
      </div>
    );
  }

  const savings = providerComparison.savings;
  const predictions = providerComparison.predictions;
  const monthlyBreakdown = providerComparison.monthly_breakdown || [];
  const yoyComparison = calculateYoYComparison(monthlyBreakdown);

  return (
    <div className="space-y-6">
      {/* Savings Hero */}
      <div className="bg-gradient-to-br from-red-600 to-rose-600 rounded-xl shadow-xl p-8 text-white">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-red-100 text-sm font-semibold uppercase mb-2">Annual Savings</p>
            <p className="text-5xl font-bold mb-3">{formatCurrency(savings.total_annual)}</p>
            <p className="text-red-100">Saving {formatCurrency(savings.total_monthly)}/month · {savings.percentage.toFixed(1)}% reduction</p>
          </div>
          <div className="bg-white/10 rounded-lg p-6 text-center">
            <TrendingUp className="w-8 h-8 mx-auto mb-2" />
            <p className="text-2xl font-bold">{formatCurrency(savings.per_mobile_monthly)}</p>
            <p className="text-red-100 text-xs">per mobile/mo</p>
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center"><FileText className="w-6 h-6 text-slate-600" /></div>
            <div>
              <p className="text-sm text-slate-600">Total Invoices</p>
              <p className="text-3xl font-bold">{stats.total_invoices}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl shadow p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center"><Users className="w-6 h-6 text-slate-600" /></div>
            <div>
              <p className="text-sm text-slate-600">Current Lines</p>
              <p className="text-3xl font-bold">{stats.current_mobile_lines}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl shadow p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center"><Activity className="w-6 h-6 text-slate-600" /></div>
            <div>
              <p className="text-sm text-slate-600">Avg Per Mobile</p>
              <p className="text-3xl font-bold">{formatCurrency(stats.avg_cost_per_mobile)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* YoY Comparison */}
      {yoyComparison && (
        <div className="bg-white rounded-xl shadow p-8">
          <h3 className="text-lg font-bold mb-6">Year-over-Year Comparison</h3>
          <div className="grid grid-cols-3 gap-6">
            <div className="text-center p-6 bg-slate-50 rounded-lg">
              <p className="text-sm font-semibold text-slate-600 mb-2">{yoyComparison.lastYearMonth}</p>
              <p className="text-3xl font-bold mb-2">{formatCurrency(yoyComparison.lastYearCost)}</p>
              <p className="text-sm text-slate-600 mb-3">Total Cost</p>
              <div className="pt-3 border-t">
                <p className="text-xs text-slate-500">Per Mobile</p>
                <p className="text-lg font-bold">{formatCurrency(yoyComparison.lastYearPerMobile)}</p>
              </div>
            </div>
            <div className="text-center p-6 bg-red-50 rounded-lg border-2 border-red-200">
              <p className="text-sm font-semibold text-red-700 mb-2">{yoyComparison.currentMonth}</p>
              <p className="text-3xl font-bold text-red-600 mb-2">{formatCurrency(yoyComparison.currentCost)}</p>
              <p className="text-sm text-red-700 mb-3">Current</p>
              <div className="pt-3 border-t border-red-200">
                <p className="text-xs text-red-600">Per Mobile</p>
                <p className="text-lg font-bold text-red-700">{formatCurrency(yoyComparison.currentPerMobile)}</p>
              </div>
            </div>
            <div className="text-center p-6 bg-blue-50 rounded-lg">
              <p className="text-sm font-semibold text-blue-700 mb-2">{yoyComparison.nextYearMonth}</p>
              <p className="text-3xl font-bold text-blue-600 mb-2">{formatCurrency(yoyComparison.predictedCost)}</p>
              <p className="text-sm text-blue-700 mb-3">Forecast</p>
              <div className="pt-3 border-t border-blue-200">
                <p className="text-xs text-blue-600">Per Mobile</p>
                <p className="text-lg font-bold text-blue-700">{formatCurrency(yoyComparison.predictedPerMobile)}</p>
              </div>
            </div>
          </div>
          <div className="mt-6 text-center p-4 bg-slate-50 rounded-lg">
            <p className={`text-2xl font-bold ${yoyComparison.change >= 0 ? 'text-red-600' : 'text-green-600'}`}>
              {yoyComparison.changePercent.toFixed(1)}% YoY
              <span className="text-lg ml-2 text-slate-600">({formatCurrency(Math.abs(yoyComparison.change))})</span>
            </p>
          </div>
        </div>
      )}

      {/* Cost Trend Chart */}
      <div className="bg-white rounded-xl shadow p-8">
        <h3 className="text-lg font-bold mb-6">Monthly Cost Trend</h3>
        <LineChart data={monthlyBreakdown} formatCurrency={formatCurrency} />
      </div>

      {/* Forecast */}
      {predictions && (
        <div className="bg-white rounded-xl shadow p-8">
          <h3 className="text-lg font-bold mb-6">Year Ahead Forecast</h3>
          <div className="grid grid-cols-3 gap-6">
            <div className="col-span-2 bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-6">
              <p className="text-sm font-semibold text-blue-700 uppercase mb-2">Projected Annual Expenditure</p>
              <p className="text-4xl font-bold text-blue-900 mb-4">{formatCurrency(predictions.vodafone_projected_annual)}</p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-blue-600">Monthly Average</p>
                  <p className="text-xl font-bold text-blue-800">{formatCurrency(predictions.vodafone_avg_monthly_current)}</p>
                </div>
                <div>
                  <p className="text-xs text-blue-600">Per Mobile</p>
                  <p className="text-xl font-bold text-blue-800">{formatCurrency(providerComparison?.savings?.vodafone_avg_per_mobile ?? 0)}</p>
                </div>
              </div>
            </div>
            <div className="bg-slate-50 rounded-lg p-6">
              <p className="text-sm font-semibold text-slate-700 uppercase mb-4">Quarterly</p>
              <div className="space-y-3">
                {['Q1', 'Q2', 'Q3', 'Q4'].map((q) => (
                  <div key={q} className="flex justify-between">
                    <span className="text-sm font-semibold text-slate-600">{q} 2026</span>
                    <span className="text-sm font-bold">{formatCurrency((predictions.vodafone_avg_monthly_current ?? 0) * 3)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** Cost-centre Top Spenders tab (Vodafone only, old logic) */
function TopSpendersTab({ topSpenders, formatCurrency }) {
  if (!topSpenders || topSpenders.length === 0) {
    return (
      <div className="text-center py-12">
        <Users className="w-16 h-16 text-slate-300 mx-auto mb-4" />
        <p className="text-slate-600">No spending data available</p>
      </div>
    );
  }

  const totalCombined = topSpenders.reduce((sum, s) => sum + (s.total_spent ?? 0), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl shadow p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Top 10 Vodafone Spenders</h2>
            <p className="text-sm text-slate-600 mt-1">Highest spending cost centres</p>
          </div>
          <span className="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg text-sm font-semibold">Cost Centres</span>
        </div>
      </div>

      {/* Spenders List */}
      <div className="grid grid-cols-1 gap-4">
        {topSpenders.map((spender, idx) => (
          <div key={idx} className="bg-white rounded-xl shadow p-6 hover:shadow-lg transition">
            <div className="flex items-center gap-6">
              {/* Rank */}
              <div className="flex-shrink-0">
                <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                  <span className="text-xl font-bold text-blue-700">{idx + 1}</span>
                </div>
              </div>

              {/* Details */}
              <div className="flex-1 grid grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-slate-500 mb-1">Cost Centre</p>
                  <p className="font-semibold text-slate-900">{spender.cost_centre || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Lines</p>
                  <p className="text-sm text-slate-700">{spender.total_mobiles ?? 0}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500 mb-1">Invoices</p>
                  <p className="text-sm text-slate-700">{spender.invoice_count ?? 0}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-500 mb-1">Total Spent</p>
                  <p className="text-xl font-bold text-blue-600">{formatCurrency(spender.total_spent)}</p>
                  <p className="text-xs text-slate-500">{formatCurrency(spender.avg_cost_per_mobile)}/mobile avg</p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Summary Stats */}
      <div className="bg-blue-50 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-blue-900 mb-4">Summary</h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-blue-600 mb-1">Cost Centres</p>
            <p className="text-2xl font-bold text-blue-900">{topSpenders.length}</p>
          </div>
          <div>
            <p className="text-xs text-blue-600 mb-1">Combined Spending</p>
            <p className="text-2xl font-bold text-blue-900">
              {formatCurrency(totalCombined)}
            </p>
          </div>
          <div>
            <p className="text-xs text-blue-600 mb-1">Average per Centre</p>
            <p className="text-2xl font-bold text-blue-900">
              {formatCurrency(totalCombined / topSpenders.length)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function ComparisonTab({ providerComparison, formatCurrency }) {
  if (!providerComparison || !providerComparison.providers) {
    return <div className="text-center py-12 text-slate-600">No data available</div>;
  }

  const { Three, Vodafone } = providerComparison.providers;

  return (
    <div className="grid grid-cols-2 gap-6">
      {Three && (
        <div className="bg-white rounded-xl shadow p-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-2xl font-bold">Three</h3>
            <span className="px-3 py-1 bg-slate-100 text-slate-600 rounded-full text-sm font-semibold">Previous</span>
          </div>
          <p className="text-4xl font-bold text-red-600 mb-6">{formatCurrency(Three.avg_cost_per_mobile_last_4)}</p>
          <div className="space-y-3">
            <div className="flex justify-between py-2 border-b">
              <span className="text-slate-600">Period</span>
              <span className="font-semibold">{Three.invoices_in_comparison} months</span>
            </div>
            <div className="flex justify-between py-2 border-b">
              <span className="text-slate-600">Lines</span>
              <span className="font-semibold">{Three.current_mobile_count}</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-slate-600">Monthly Avg</span>
              <span className="font-semibold">{formatCurrency(Three.avg_monthly_cost_last_4)}</span>
            </div>
          </div>
        </div>
      )}

      {Vodafone && (
        <div className="bg-white rounded-xl shadow p-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-2xl font-bold">Vodafone</h3>
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-semibold">Current</span>
          </div>
          <p className="text-4xl font-bold text-blue-600 mb-6">{formatCurrency(Vodafone.avg_cost_per_mobile_last_4)}</p>
          <div className="space-y-3">
            <div className="flex justify-between py-2 border-b">
              <span className="text-slate-600">Period</span>
              <span className="font-semibold">{Vodafone.invoices_in_comparison} months</span>
            </div>
            <div className="flex justify-between py-2 border-b">
              <span className="text-slate-600">Lines</span>
              <span className="font-semibold">{Vodafone.current_mobile_count}</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-slate-600">Monthly Avg</span>
              <span className="font-semibold">{formatCurrency(Vodafone.avg_monthly_cost_last_4)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function InvoicesTab({ invoices, formatCurrency, formatDate, handleDeleteInvoice }) {
  if (!invoices || invoices.length === 0) {
    return (
      <div className="text-center py-12">
        <FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
        <p className="text-slate-600">No invoices yet</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-6 py-4 text-sm font-semibold text-slate-700">Date</th>
              <th className="text-left px-6 py-4 text-sm font-semibold text-slate-700">Provider</th>
              <th className="text-left px-6 py-4 text-sm font-semibold text-slate-700">Invoice #</th>
              <th className="text-right px-6 py-4 text-sm font-semibold text-slate-700">Lines</th>
              <th className="text-right px-6 py-4 text-sm font-semibold text-slate-700">Total</th>
              <th className="text-right px-6 py-4 text-sm font-semibold text-slate-700">Per Mobile</th>
              <th className="text-right px-6 py-4 text-sm font-semibold text-slate-700">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {invoices.map((invoice) => (
              <tr key={invoice.id} className="hover:bg-slate-50">
                <td className="px-6 py-4 font-medium">{formatDate(invoice.invoice_date)}</td>
                <td className="px-6 py-4">
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                    invoice.provider === 'Vodafone' ? 'bg-blue-100 text-blue-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {invoice.provider}
                  </span>
                </td>
                <td className="px-6 py-4 text-slate-600 font-mono text-sm">{invoice.invoice_number}</td>
                <td className="px-6 py-4 text-right font-semibold">{invoice.total_mobiles}</td>
                <td className="px-6 py-4 text-right font-semibold">{formatCurrency(invoice.total_amount)}</td>
                <td className="px-6 py-4 text-right font-bold">
                  {formatCurrency((invoice.total_amount ?? 0) / (invoice.total_mobiles || 1))}
                </td>
                <td className="px-6 py-4 text-right">
                  <button onClick={() => handleDeleteInvoice(invoice.id)} className="text-red-600 hover:bg-red-50 p-2 rounded-lg">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function calculateYoYComparison(monthlyBreakdown) {
  if (!monthlyBreakdown || monthlyBreakdown.length === 0) return null;
  
  const sortedData = [...monthlyBreakdown].sort((a, b) => new Date(b.month) - new Date(a.month));
  const latestInvoice = sortedData[0];
  const latestDate = new Date(latestInvoice.month + '-01');
  const latestMonth = latestDate.getMonth();
  const latestYear = latestDate.getFullYear();

  const lastYearData = monthlyBreakdown.find(item => {
    const itemDate = new Date(item.month + '-01');
    return itemDate.getMonth() === latestMonth && itemDate.getFullYear() === latestYear - 1;
  });

  if (!lastYearData) return null;

  const recentInvoices = sortedData.slice(0, 4);
  const avgCost = recentInvoices.reduce((sum, inv) => sum + inv.total_amount, 0) / recentInvoices.length;
  const avgPerMobile = recentInvoices.reduce((sum, inv) => sum + inv.cost_per_mobile, 0) / recentInvoices.length;

  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const change = latestInvoice.total_amount - lastYearData.total_amount;
  const changePercent = (change / lastYearData.total_amount) * 100;

  return {
    lastYearMonth: `${monthNames[latestMonth]} ${latestYear - 1}`,
    lastYearCost: lastYearData.total_amount,
    lastYearPerMobile: lastYearData.cost_per_mobile,
    currentMonth: `${monthNames[latestMonth]} ${latestYear}`,
    currentCost: latestInvoice.total_amount,
    currentPerMobile: latestInvoice.cost_per_mobile,
    nextYearMonth: `${monthNames[latestMonth]} ${latestYear + 1}`,
    predictedCost: avgCost,
    predictedPerMobile: avgPerMobile,
    change,
    changePercent
  };
}

function LineChart({ data }) {
  if (!data || data.length === 0) return null;

  const sortedData = [...data].sort((a, b) => a.month.localeCompare(b.month));
  const maxAmount = Math.max(...sortedData.map(d => d.total_amount));
  const minAmount = Math.min(...sortedData.map(d => d.total_amount));
  const range = (maxAmount - minAmount) || 1;

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex justify-end gap-4">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500"></div>
          <span className="text-sm font-medium">Three</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-blue-500"></div>
          <span className="text-sm font-medium">Vodafone</span>
        </div>
      </div>

      {/* Chart */}
      <div className="relative h-64 bg-slate-50 rounded-lg p-4">
        <svg className="w-full h-full">
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((fraction, i) => (
            <line key={i} x1="0" y1={`${fraction * 100}%`} x2="100%" y2={`${fraction * 100}%`}
              stroke="#e2e8f0" strokeWidth="1" strokeDasharray="4 4" />
          ))}

          {/* Data points and lines */}
          {sortedData.map((item, index) => {
            if (index === 0) return null;
            const prevItem = sortedData[index - 1];
            if (prevItem.provider !== item.provider) return null;

            const x1 = ((index - 1) / (sortedData.length - 1)) * 100;
            const y1 = ((maxAmount - prevItem.total_amount) / range) * 100;
            const x2 = (index / (sortedData.length - 1)) * 100;
            const y2 = ((maxAmount - item.total_amount) / range) * 100;
            const color = item.provider === 'Vodafone' ? '#3b82f6' : '#ef4444';

            return (
              <g key={index}>
                <line x1={`${x1}%`} y1={`${y1}%`} x2={`${x2}%`} y2={`${y2}%`}
                  stroke={color} strokeWidth="3" strokeLinecap="round" />
                <circle cx={`${x2}%`} cy={`${y2}%`} r="4" fill={color} />
              </g>
            );
          })}
        </svg>
      </div>

      {/* Timeline */}
      <div className="flex justify-between text-xs text-slate-500 px-4">
        {sortedData.filter((_, i) => i % Math.ceil(sortedData.length / 8) === 0).map((item, i) => (
          <span key={i}>{item.month}</span>
        ))}
      </div>
    </div>
  );
}
