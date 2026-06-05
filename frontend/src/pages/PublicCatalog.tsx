/**
 * PublicCatalog — публічний каталог для клієнтів.
 * Доступний на "/" без авторизації.
 * Дані беруться з /api/catalog/products-lite (загальна БД RentalHub).
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

interface Product {
  product_id: number;
  sku: string;
  name: string;
  image: string;
  cover: string;
  category: string | null;
  category_name: string | null;
  family_id: number | null;
  color: string | null;
  quantity: number;
}

const PLACEHOLDER = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><rect fill="%23f1f5f9" width="400" height="400"/><text x="50%" y="50%" font-family="sans-serif" font-size="22" fill="%2394a3b8" text-anchor="middle" dy=".3em">Немає фото</text></svg>';

function resolveImage(url: string | null | undefined): string {
  if (!url) return PLACEHOLDER;
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) return url;
  // відносний шлях з бекенду
  const base = BACKEND_URL.replace(/\/+$/, '');
  const path = url.startsWith('/') ? url : `/${url}`;
  return `${base}${path}`;
}

export default function PublicCatalog() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('');

  useEffect(() => {
    let aborted = false;
    (async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/catalog/products-lite?limit=5000`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: Product[] = await res.json();
        if (!aborted) setProducts(Array.isArray(data) ? data : []);
      } catch (e: any) {
        if (!aborted) setError(e?.message || 'Не вдалося завантажити каталог');
      } finally {
        if (!aborted) setLoading(false);
      }
    })();
    return () => { aborted = true; };
  }, []);

  const categories = useMemo(() => {
    const set = new Set<string>();
    products.forEach((p) => { if (p.category_name) set.add(p.category_name); });
    return Array.from(set).sort();
  }, [products]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return products.filter((p) => {
      if (activeCategory && p.category_name !== activeCategory) return false;
      if (!q) return true;
      return (
        p.name?.toLowerCase().includes(q) ||
        p.sku?.toLowerCase().includes(q)
      );
    });
  }, [products, search, activeCategory]);

  return (
    <div className="min-h-screen bg-slate-50 font-montserrat">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-corp-primary flex items-center justify-center text-white font-bold text-lg">R</div>
            <div>
              <div className="text-lg font-bold text-corp-text-dark">FarforRent</div>
              <div className="text-xs text-corp-text-muted">Каталог оренди декору</div>
            </div>
          </div>
          <Link
            to="/login"
            data-testid="public-catalog-login-link"
            className="text-sm font-medium text-corp-text-muted hover:text-corp-primary transition-colors"
          >
            Вхід для співробітників →
          </Link>
        </div>
      </header>

      {/* Search + categories */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <input
          type="text"
          placeholder="Пошук по назві або артикулу..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="public-catalog-search-input"
          className="w-full max-w-xl px-4 py-3 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-corp-primary"
        />

        {categories.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setActiveCategory('')}
              data-testid="public-catalog-category-all"
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                activeCategory === ''
                  ? 'bg-corp-primary text-white'
                  : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
              }`}
            >
              Усі ({products.length})
            </button>
            {categories.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setActiveCategory(c)}
                data-testid={`public-catalog-category-${c}`}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  activeCategory === c
                    ? 'bg-corp-primary text-white'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Grid */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 pb-12">
        {loading && (
          <div className="text-center py-20 text-slate-500" data-testid="public-catalog-loading">
            Завантаження каталогу...
          </div>
        )}

        {error && !loading && (
          <div className="text-center py-12 text-red-600" data-testid="public-catalog-error">
            ⚠️ {error}
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-12 text-slate-500" data-testid="public-catalog-empty">
            Нічого не знайдено
          </div>
        )}

        {!loading && filtered.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4" data-testid="public-catalog-grid">
            {filtered.map((p) => (
              <article
                key={p.product_id}
                data-testid={`public-catalog-product-${p.product_id}`}
                className="group bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow"
              >
                <div className="aspect-square bg-slate-100 overflow-hidden">
                  <img
                    src={resolveImage(p.cover || p.image)}
                    alt={p.name}
                    loading="lazy"
                    onError={(e) => { (e.target as HTMLImageElement).src = PLACEHOLDER; }}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                </div>
                <div className="p-3">
                  <div className="text-[11px] uppercase tracking-wide text-slate-400 truncate">{p.sku}</div>
                  <div className="text-sm font-medium text-slate-800 line-clamp-2 mt-0.5 min-h-[2.5rem]">{p.name}</div>
                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span className="text-slate-500 truncate">{p.category_name || '—'}</span>
                    <span className={`font-semibold ${p.quantity > 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                      {p.quantity > 0 ? `${p.quantity} шт` : 'Немає'}
                    </span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-500">
        © 2026 FarforRent • Усі товари доступні з єдиної бази RentalHub
      </footer>
    </div>
  );
}
