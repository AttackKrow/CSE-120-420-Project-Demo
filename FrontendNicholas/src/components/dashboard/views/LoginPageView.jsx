import React, { useState } from 'react';

export function LoginPageView({ onLogin }) {
  const [user, setUser] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onLogin) onLogin(user);
  };

  return (
    <div className="min-h-screen bg-white text-zinc-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm border border-zinc-200 bg-white p-8 rounded-lg shadow-sm space-y-6">
        <h1 className="text-2xl font-bold text-center text-zinc-900">Login</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-zinc-600 mb-1">
              User
            </label>
            <input
              type="text"
              value={user}
              onChange={(e) => setUser(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-zinc-300 rounded text-sm text-zinc-900 focus:outline-none focus:border-zinc-800"
              placeholder="User"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-600 mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-zinc-300 rounded text-sm text-zinc-900 focus:outline-none focus:border-zinc-800"
              placeholder="Password"
              required
            />
          </div>

          <button
            type="submit"
            className="w-full py-2 bg-zinc-900 hover:bg-black text-white text-sm font-semibold rounded transition"
          >
            Login
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginPageView;