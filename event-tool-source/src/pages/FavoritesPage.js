import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Heart, ArrowLeft, ShoppingBag, Loader2, Plus, Trash2 } from 'lucide-react';
import { favoritesAPI } from '../api/favorites';
import { useFavorites } from '../context/FavoritesContext';
import AddToBoardModal from '../components/AddToBoardModal';

const PLACEHOLDER = '/logo.svg';

const FavoriteCard = ({ product, onAddToProject, onRemove }) => {
  const img = product.image_url
    ? (product.image_url.startsWith('http') || product.image_url.startsWith('data:')
        ? product.image_url
        : `${process.env.REACT_APP_BACKEND_URL || ''}/api/uploads/products/${product.image_url.split('/').pop()}`)
    : PLACEHOLDER;
  return (
    <div
      data-testid={`fav-card-${product.product_id}`}
      style={{
        background: '#fff', borderRadius: 12, overflow: 'hidden',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)', position: 'relative',
        display: 'flex', flexDirection: 'column',
      }}
    >
      <button
        onClick={() => onRemove(product.product_id)}
        aria-label="Прибрати з обраного"
        data-testid={`fav-remove-${product.product_id}`}
        style={{
          position: 'absolute', top: 6, right: 6, zIndex: 2,
          width: 28, height: 28, borderRadius: '50%',
          background: 'rgba(255,255,255,0.92)', border: 'none',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
        }}
      >
        <Trash2 size={13} color="#c62828" />
      </button>
      <div style={{
        width: '100%', aspectRatio: '1 / 1', background: '#f7f5ee',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <img src={img} alt={product.name}
             onError={(e) => { e.currentTarget.src = PLACEHOLDER; }}
             style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
      </div>
      <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{
          fontSize: 13, color: '#222', fontWeight: 500,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {product.name}
        </div>
        <div style={{ fontSize: 11, color: '#aaa' }}>{product.sku || ''}</div>
        <div style={{
          fontSize: 13, fontWeight: 600, color: '#0a3d2e',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span>₴{Math.round(product.rental_price || product.price || 0)}/день</span>
          <span style={{ fontSize: 11, color: '#888', fontWeight: 400 }}>
            {product.quantity || 0} шт
          </span>
        </div>
        <button
          onClick={() => onAddToProject(product)}
          data-testid={`fav-add-project-${product.product_id}`}
          style={{
            marginTop: 4, padding: '8px 12px', borderRadius: 999,
            background: '#0a3d2e', color: '#fff', border: 'none',
            cursor: 'pointer', fontSize: 12, fontWeight: 500,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            textTransform: 'uppercase', letterSpacing: '0.04em',
          }}
        >
          <Plus size={13} /> В проєкт
        </button>
      </div>
    </div>
  );
};


const FavoritesPage = () => {
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeModalProduct, setActiveModalProduct] = useState(null);
  const { toggle: toggleFav, refresh: refreshFav } = useFavorites();

  const load = async () => {
    setLoading(true);
    try {
      const list = await favoritesAPI.listProducts();
      setProducts(list);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleRemove = async (productId) => {
    await toggleFav(productId);   // toggles off
    setProducts((prev) => prev.filter((p) => p.product_id !== productId));
    refreshFav();
  };

  return (
    <div data-testid="favorites-page" style={{ minHeight: '100vh', background: '#f7f5ee' }}>
      <header style={{
        position: 'sticky', top: 0, zIndex: 10, background: '#fff',
        borderBottom: '1px solid #e9e4d6', padding: '12px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <button onClick={() => navigate('/')}
                data-testid="favorites-back-btn"
                style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex' }}
                aria-label="Назад">
          <ArrowLeft size={22} />
        </button>
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 600,
                    display: 'flex', alignItems: 'center', gap: 8 }}>
          <Heart size={20} fill="#e63946" color="#e63946" /> Обране
          <span style={{ fontSize: 13, color: '#888', fontWeight: 400 }}>
            ({products.length})
          </span>
        </h1>
      </header>

      <main style={{ padding: 16, paddingBottom: 96 }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <Loader2 className="animate-spin" size={28} color="#888" />
          </div>
        ) : products.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#888' }}
               data-testid="favorites-empty">
            <Heart size={56} color="#ddd" style={{ marginBottom: 16 }} />
            <p style={{ fontSize: 16, marginBottom: 8 }}>Ще немає обраних товарів</p>
            <p style={{ fontSize: 14, marginBottom: 20 }}>
              Натискайте ♡ на картках, щоб зберегти їх тут
            </p>
            <button
              onClick={() => navigate('/')}
              data-testid="favorites-browse-btn"
              style={{
                background: '#222', color: '#fff', border: 'none', borderRadius: 999,
                padding: '12px 24px', fontSize: 14, cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 8,
              }}
            >
              <ShoppingBag size={16} /> Перейти до каталогу
            </button>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
            gap: 12,
          }}>
            {products.map((p) => (
              <FavoriteCard
                key={p.product_id}
                product={p}
                onAddToProject={(prod) => setActiveModalProduct(prod)}
                onRemove={handleRemove}
              />
            ))}
          </div>
        )}
      </main>

      {activeModalProduct && (
        <AddToBoardModal
          product={activeModalProduct}
          onClose={() => setActiveModalProduct(null)}
          onAdded={() => { /* could show toast */ }}
        />
      )}
    </div>
  );
};

export default FavoritesPage;
