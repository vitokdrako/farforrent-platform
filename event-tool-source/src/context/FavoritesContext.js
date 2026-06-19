import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import { favoritesAPI } from '../api/favorites';
import { useAuth } from './AuthContext';

const FavoritesContext = createContext(null);

export const useFavorites = () => {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error('useFavorites must be used within FavoritesProvider');
  return ctx;
};

export const FavoritesProvider = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [favoriteIds, setFavoriteIds] = useState(() => {
    const cached = localStorage.getItem('favorite_ids');
    return cached ? JSON.parse(cached) : [];
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) refresh();
    else setFavoriteIds([]);
  }, [isAuthenticated]);

  useEffect(() => {
    localStorage.setItem('favorite_ids', JSON.stringify(favoriteIds));
  }, [favoriteIds]);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const ids = await favoritesAPI.list();
      setFavoriteIds(ids);
    } catch (e) {
      console.error('favorites refresh failed:', e);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  const isFavorite = useCallback(
    (productId) => favoriteIds.includes(productId),
    [favoriteIds]
  );

  const toggle = useCallback(
    async (productId) => {
      if (!isAuthenticated) {
        // Guest: store locally only
        setFavoriteIds((prev) =>
          prev.includes(productId)
            ? prev.filter((id) => id !== productId)
            : [...prev, productId]
        );
        return;
      }
      const wasFav = favoriteIds.includes(productId);
      // Optimistic update
      setFavoriteIds((prev) =>
        wasFav ? prev.filter((id) => id !== productId) : [...prev, productId]
      );
      try {
        if (wasFav) await favoritesAPI.remove(productId);
        else await favoritesAPI.add(productId);
      } catch (e) {
        console.error('toggle favorite failed:', e);
        // rollback
        setFavoriteIds((prev) =>
          wasFav ? [...prev, productId] : prev.filter((id) => id !== productId)
        );
      }
    },
    [isAuthenticated, favoriteIds]
  );

  return (
    <FavoritesContext.Provider value={{ favoriteIds, isFavorite, toggle, refresh, loading }}>
      {children}
    </FavoritesContext.Provider>
  );
};

export default FavoritesContext;
