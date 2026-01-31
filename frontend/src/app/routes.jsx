// src/app/routes.jsx
import React from 'react';
import App from './App.jsx';
import Settings from '../pages/Settings.jsx';
import Profile from '../pages/Profile.jsx';
import AuthCallback from '../pages/AuthCallback.jsx';

export default [
  { path: '/', element: <App /> },
  { path: '/settings', element: <Settings /> },
  { path: '/profile', element: <Profile /> },
  { path: '/auth/:provider/callback', element: <AuthCallback /> },
];
