import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import { favoritesAPI } from '../api/favorites';
import { useAuth } from './AuthContext';

const FavoritesContext = createContext(null);

const LS_KEY = 'favorite_ids_v2';

export const useFavorites = () => {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error('useFavorites must be used within FavoritesProvider');
  return ctx;
};

export const FavoritesProvider = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [favoriteIds, setFavoriteIds] = useState(() => {
    try {
      const cached = localStorage.getItem(LS_KEY);
      return cached ? JSON.parse(cached) : [];
    } catch { return []; }
  });
  const [serverAvailable, setServerAvailable] = useState(true);

  // Persist to localStorage always
  useEffect(() => {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(favoriteIds));
    } catch (e) { /* ignore quota errors */ }
  }, [favoriteIds]);

  // On auth state change, try to sync with server
  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const serverIds = await favoritesAPI.list();
      // Merge: union of local cache and server (so user doesn't lose locally added)
      const localCached = (() => {
        try { return JSON.parse(localStorage.getItem(LS_KEY) || '[]'); }
        catch { return []; }
      })();
      const merged = Array.from(new Set([...serverIds, ...localCached]));
      // Push any locally-cached items that aren't on server
      const toPush = localCached.filter((id) => !serverIds.includes(id));
      for (const id of toPush) {
        try { await favoritesAPI.add(id); } catch (e) { /* tolerate */ }
      }
      setFavoriteIds(merged);
      setServerAvailable(true);
    } catch (e) {
      console.warn('favorites refresh failed (will work locally):', e?.message);
      setServerAvailable(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) refresh();
  }, [isAuthenticated, refresh]);

  const isFavorite = useCallback(
    (productId) => favoriteIds.includes(productId),
    [favoriteIds]
  );

  const toggle = useCallback(
    async (productId) => {
      const wasFav = favoriteIds.includes(productId);
      // Optimistic update — ЗАВЖДИ зберігається локально
      setFavoriteIds((prev) =>
        wasFav ? prev.filter((id) => id !== productId) : [...prev, productId]
      );
      if (!isAuthenticated) return;
      try {
        if (wasFav) await favoritesAPI.remove(productId);
        else await favoritesAPI.add(productId);
        setServerAvailable(true);
      } catch (e) {
        // НЕ rollback'имо локальний стан — він залишиться в localStorage.
        // Це дає user-experience "обране працює" навіть якщо сервер не готовий.
        console.warn('favorites API call failed, will retry on next refresh:', e?.message);
        setServerAvailable(false);
      }
    },
    [isAuthenticated, favoriteIds]
  );

  return (
    <FavoritesContext.Provider value={{
      favoriteIds, isFavorite, toggle, refresh,
      serverAvailable,
    }}>
      {children}
    </FavoritesContext.Provider>
  );
};

export default FavoritesContext;
