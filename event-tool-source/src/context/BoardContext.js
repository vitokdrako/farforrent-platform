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
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(true);

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