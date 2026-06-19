import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Heart, ArrowLeft, ShoppingBag, Loader2 } from 'lucide-react';
import { favoritesAPI } from '../api/favorites';
import { useFavorites } from '../context/FavoritesContext';
import { useBoard } from '../context/BoardContext';
import ProductCard from '../components/ProductCard';

const FavoritesPage = () => {
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const { refresh: refreshFavorites } = useFavorites();
  const { activeBoard, addItemToBoard } = useBoard();

  useEffect(() => { load(); }, []);
  const load = async () => {
    setLoading(true);
    try {
      const list = await favoritesAPI.listProducts();
      setProducts(list);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  return (
    <div className="favorites-page" data-testid="favorites-page" style={{ minHeight: '100vh', background: '#f7f5ee' }}>
      <header style={{
        position: 'sticky', top: 0, zIndex: 10,
        background: '#fff', borderBottom: '1px solid #e9e4d6',
        padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <button
          onClick={() => navigate('/')}
          data-testid="favorites-back-btn"
          style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
          aria-label="Назад"
        >
          <ArrowLeft size={22} />
        </button>
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Heart size={20} fill="#e63946" color="#e63946" /> Обране
          <span style={{ fontSize: 13, color: '#888', fontWeight: 400 }}>({products.length})</span>
        </h1>
      </header>

      <main style={{ padding: 16, paddingBottom: 96 }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <Loader2 className="animate-spin" size={28} color="#888" />
          </div>
        ) : products.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#888' }} data-testid="favorites-empty">
            <Heart size={56} color="#ddd" style={{ marginBottom: 16 }} />
            <p style={{ fontSize: 16, marginBottom: 8 }}>Ще немає обраних товарів</p>
            <p style={{ fontSize: 14, marginBottom: 20 }}>Натискайте ♡ на картках, щоб зберегти їх тут</p>
            <button
              onClick={() => navigate('/')}
              data-testid="favorites-browse-btn"
              style={{
                background: '#222', color: '#fff', border: 'none', borderRadius: 999,
                padding: '12px 24px', fontSize: 14, cursor: 'pointer', display: 'inline-flex',
                alignItems: 'center', gap: 8,
              }}
            >
              <ShoppingBag size={16} /> Перейти до каталогу
            </button>
          </div>
        ) : (
          <div className="favorites-grid" style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
            gap: 12,
          }}>
            {products.map((p) => (
              <ProductCard
                key={p.product_id}
                product={p}
                onAddToBoard={addItemToBoard}
                boardDates={activeBoard ? {
                  startDate: activeBoard.rental_start_date,
                  endDate: activeBoard.rental_end_date,
                } : null}
                onOpenDetails={null}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default FavoritesPage;
