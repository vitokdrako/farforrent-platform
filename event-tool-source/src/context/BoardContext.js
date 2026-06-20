import React, { createContext, useState, useContext } from 'react';

const BoardContext = createContext(null);

export const useBoard = () => {
  const context = useContext(BoardContext);
  if (!context) {
    throw new Error('useBoard must be used within BoardProvider');
  }
  return context;
};

export const BoardProvider = ({ children }) => {
  const [activeBoard, setActiveBoard] = useState(null);
  // За замовчуванням панель закрита на мобільному (≤768px), відкрита на desktop
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.innerWidth > 768;
  });

  const toggleSidePanel = () => {
    setIsSidePanelOpen((prev) => !prev);
  };

  return (
    <BoardContext.Provider
      value={{
        activeBoard,
        setActiveBoard,
        isSidePanelOpen,
        setIsSidePanelOpen,
        toggleSidePanel,
      }}
    >
      {children}
    </BoardContext.Provider>
  );
};