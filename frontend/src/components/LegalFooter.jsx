/**
 * LegalFooter - Футер з посиланнями на правові документи
 * © FarforDecorOrenda 2025
 */
import React from 'react';
import { COMPANY_INFO, LEGAL_LINKS } from '../data/companyInfo';

export default function LegalFooter({ className = '', showLinks = true }) {
  return (
    <footer className={`border-t border-slate-200 bg-slate-50 py-4 px-6 ${className}`}>
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          <div className="text-sm text-slate-500">
            © {COMPANY_INFO.name} {COMPANY_INFO.year}
          </div>
          
          {showLinks && (
            <div className="flex flex-wrap items-center gap-4 text-xs">
              <a 
                href={LEGAL_LINKS.terms} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-slate-500 hover:text-corp-primary transition-colors"
              >
                Умови оренди
              </a>
              <a 
                href={LEGAL_LINKS.offer} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-slate-500 hover:text-corp-primary transition-colors"
              >
                Оферта
              </a>
              <a 
                href={LEGAL_LINKS.privacy} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-slate-500 hover:text-corp-primary transition-colors"
              >
                Політика конфіденційності
              </a>
              <a 
                href={LEGAL_LINKS.damageRules} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-slate-500 hover:text-corp-primary transition-colors"
              >
                Опис збитків
              </a>
            </div>
          )}
        </div>
      </div>
    </footer>
  );
}
