import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/corporate.css';
import './index.css';
import './styles/mobile.css';
import App from './App';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
