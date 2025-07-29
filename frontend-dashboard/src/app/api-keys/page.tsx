"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@clerk/nextjs';

interface ApiKey {
  id: number;
  exchange_name: string;
  api_key: string;
  is_active: boolean;
  created_at: string;
}

export default function ApiKeysPage() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loadingFetch, setLoadingFetch] = useState(false); // For initial fetch
  const [loadingAction, setLoadingAction] = useState(false); // For add/delete/test actions
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const { getToken } = useAuth();

  const fetchWithAuth = async (url: string, options?: RequestInit) => {
    const token = await getToken();
    const headers = {
      ...(options?.headers || {}),
      'Authorization': `Bearer ${token}`,
    };
    return fetch(url, { ...options, headers });
  };
  
  const [addForm, setAddForm] = useState({
    exchange_name: 'binance',
    api_key: '',
    secret_key: '',
    is_active: true
  });

  const exchanges = [
    'binance', 'coinbase', 'kraken', 'bitfinex', 'huobi', 'okx', 'bybit'
  ];

  useEffect(() => {
    fetchApiKeys();
  }, []);

  const fetchApiKeys = async () => {
    setLoadingFetch(true);
    setError(null);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/api_keys');
      if (!response.ok) throw new Error('Failed to fetch API keys');
      const data = await response.json();
      setApiKeys(data);
    } catch (e: any) {
      setError(`Failed to fetch API keys: ${e.message}`);
    } finally {
      setLoadingFetch(false);
    }
  };

  const addApiKey = async () => {
    if (!addForm.api_key || !addForm.secret_key) {
      setError('Please fill in all required fields');
      return;
    }

    setLoadingAction(true);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/api_keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(addForm)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to add API key');
      }
      
      const data = await response.json();
      alert(data.message);
      setShowAddForm(false);
      setAddForm({
        exchange_name: 'binance',
        api_key: '',
        secret_key: '',
        is_active: true
      });
      fetchApiKeys();
    } catch (e: any) {
      setError(`Failed to add API key: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const deleteApiKey = async (apiKeyId: number) => {
    if (!confirm('Are you sure you want to delete this API key?')) return;
    
    setLoading(true);
    try {
      const response = await fetchWithAuth(`http://127.0.0.1:8000/api_keys/${apiKeyId}`, {
        method: 'DELETE'
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete API key');
      }
      
      const data = await response.json();
      alert(data.message);
      fetchApiKeys();
    } catch (e: any) {
      setError(`Failed to delete API key: ${e.message}`);
    } finally {
      setLoadingAction(false);
    }
  };

  const testConnection = async (exchange: string) => {
    setLoading(true);
    try {
      const response = await fetchWithAuth(`http://127.0.0.1:8000/trading/balance/${exchange}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Connection test failed');
      }
      
      const balance = await response.json();
      alert(`✅ Connection successful!\nTotal balance available: ${JSON.stringify(balance.total || {}, null, 2)}`);
    } catch (e: any) {
      setError(`Connection test failed: ${e.message}`);
    } finally {
      setLoadingAction(false);
    }
  };

  if (error && !showAddForm) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <h2 className="text-h3 text-red-400 mb-4">Error</h2>
          <p className="text-body text-secondary mb-6">{error}</p>
          <button 
            onClick={() => setError(null)}
            className="linear-button-primary py-2 px-4"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-h1 text-center mb-12">API Key Management</h1>
        
        {error && (
          <div className="linear-card mb-6 border-red-400 bg-red-400 bg-opacity-10">
            <p className="text-body text-red-400">{error}</p>
            <button 
              onClick={() => setError(null)}
              className="linear-button-secondary text-red-400 mt-2"
            >
              Dismiss
            </button>
          </div>
        )}
        
        <div className="linear-card mb-8">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-h3">Your API Keys</h2>
            <button
              onClick={() => setShowAddForm(true)}
              className="linear-button-primary py-2 px-4"
              disabled={loadingAction || loadingFetch}
            >
              Add New API Key
            </button>
          </div>
          
          {apiKeys.length > 0 ? (
            <div className="space-y-4">
              {apiKeys.map((apiKey) => (
                <div key={apiKey.id} className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-body font-medium text-white mb-2">
                        {apiKey.exchange_name.toUpperCase()}
                      </h3>
                      <p className="text-small text-secondary mb-2">
                        API Key: {apiKey.api_key.substring(0, 8)}...{apiKey.api_key.substring(-4)}
                      </p>
                      <p className="text-small text-secondary">
                        Added: {new Date(apiKey.created_at).toLocaleDateString()}
                      </p>
                      <div className="flex items-center mt-2">
                        <span className={`text-small ${apiKey.is_active ? 'text-green-400' : 'text-red-400'}`}>
                          {apiKey.is_active ? '● Active' : '● Inactive'}
                        </span>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => testConnection(apiKey.exchange_name)}
                        className="linear-button-secondary py-1 px-3 text-small"
                        disabled={loadingAction}
                      >
                        Test
                      </button>
                      <button
                        onClick={() => deleteApiKey(apiKey.id)}
                        className="linear-button-secondary py-1 px-3 text-small text-red-400 hover:text-red-300"
                        disabled={loadingAction}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="glass-light p-6 rounded-lg text-center">
              <p className="text-body text-secondary mb-4">No API keys configured</p>
              <p className="text-small text-secondary">
                Add your exchange API keys to enable real-time trading
              </p>
            </div>
          )}
        </div>

        {/* Security Notice */}
        <div className="linear-card border-yellow-500 bg-yellow-500 bg-opacity-10">
          <h3 className="text-body font-medium text-yellow-400 mb-3">🔒 Security Notice</h3>
          <div className="text-small text-secondary space-y-2">
            <p>• API keys are encrypted and stored securely in the database</p>
            <p>• Use sandbox/testnet API keys for testing purposes</p>
            <p>• Never share your API keys with anyone</p>
            <p>• Ensure your API keys have only necessary permissions (trading, but not withdrawal)</p>
            <p>• You can revoke API keys anytime from your exchange account</p>
          </div>
        </div>

        {/* Add API Key Modal */}
        {showAddForm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="linear-card max-w-md w-full mx-4">
              <h2 className="text-h3 mb-6">Add New API Key</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-small mb-2">Exchange:</label>
                  <select
                    value={addForm.exchange_name}
                    onChange={(e) => setAddForm(prev => ({ ...prev, exchange_name: e.target.value }))}
                    className="linear-select w-full"
                  >
                    {exchanges.map((exchange) => (
                      <option key={exchange} value={exchange}>
                        {exchange.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="block text-small mb-2">API Key:</label>
                  <input
                    type="text"
                    value={addForm.api_key}
                    onChange={(e) => setAddForm(prev => ({ ...prev, api_key: e.target.value }))}
                    className="linear-input w-full"
                    placeholder="Enter your API key"
                  />
                </div>
                
                <div>
                  <label className="block text-small mb-2">Secret Key:</label>
                  <input
                    type="password"
                    value={addForm.secret_key}
                    onChange={(e) => setAddForm(prev => ({ ...prev, secret_key: e.target.value }))}
                    className="linear-input w-full"
                    placeholder="Enter your secret key"
                  />
                </div>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={addForm.is_active}
                    onChange={(e) => setAddForm(prev => ({ ...prev, is_active: e.target.checked }))}
                    className="mr-2"
                  />
                  <label htmlFor="is_active" className="text-small">Active</label>
                </div>
              </div>
              
              <div className="flex space-x-4 mt-6">
                <button
                  onClick={addApiKey}
                  disabled={loadingAction}
                  className="linear-button-primary py-3 px-6 flex-1 disabled:opacity-50"
                >
                  {loadingAction ? 'Adding...' : 'Add API Key'}
                </button>
                <button
                  onClick={() => setShowAddForm(false)}
                  className="linear-button-secondary py-3 px-6"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}