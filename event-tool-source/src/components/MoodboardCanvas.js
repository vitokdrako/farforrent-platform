import React, { useState, useRef, useEffect } from 'react';
import Moveable from 'react-moveable';

// Layout templates based on the provided image
const LAYOUT_TEMPLATES = [
  {
    id: 1,
    name: 'Асиметричний',
    cells: [
      { x: 0, y: 0, width: 50, height: 100 },
      { x: 50, y: 0, width: 25, height: 20 },
      { x: 75, y: 0, width: 25, height: 30 },
      { x: 50, y: 20, width: 50, height: 25 },
      { x: 50, y: 45, width: 25, height: 30 },
      { x: 75, y: 45, width: 25, height: 25 }
    ]
  },
  {
    id: 2,
    name: 'Сітка 2×2',
    cells: [
      { x: 0, y: 0, width: 50, height: 50 },
      { x: 50, y: 0, width: 50, height: 50 },
      { x: 0, y: 50, width: 50, height: 50 },
      { x: 50, y: 50, width: 50, height: 50 }
    ]
  },
  {
    id: 3,
    name: 'Сітка 3×2',
    cells: [
      { x: 0, y: 0, width: 33.33, height: 50 },
      { x: 33.33, y: 0, width: 33.33, height: 50 },
      { x: 66.66, y: 0, width: 33.34, height: 50 },
      { x: 0, y: 50, width: 33.33, height: 50 },
      { x: 33.33, y: 50, width: 33.33, height: 50 },
      { x: 66.66, y: 50, width: 33.34, height: 50 }
    ]
  },
  {
    id: 4,
    name: 'Центральний фокус',
    cells: [
      { x: 0, y: 0, width: 25, height: 33 },
      { x: 25, y: 0, width: 50, height: 33 },
      { x: 75, y: 0, width: 25, height: 33 },
      { x: 0, y: 33, width: 25, height: 34 },
      { x: 25, y: 33, width: 50, height: 34 },
      { x: 75, y: 33, width: 25, height: 34 },
      { x: 0, y: 67, width: 50, height: 33 },
      { x: 50, y: 67, width: 50, height: 33 }
    ]
  },
  {
    id: 5,
    name: 'Горизонтальний',
    cells: [
      { x: 0, y: 0, width: 100, height: 33 },
      { x: 0, y: 33, width: 50, height: 34 },
      { x: 50, y: 33, width: 50, height: 34 },
      { x: 0, y: 67, width: 100, height: 33 }
    ]
  },
  {
    id: 6,
    name: 'Великий центр',
    cells: [
      { x: 0, y: 0, width: 33.33, height: 25 },
      { x: 33.33, y: 0, width: 33.34, height: 25 },
      { x: 66.67, y: 0, width: 33.33, height: 25 },
      { x: 0, y: 25, width: 25, height: 50 },
      { x: 25, y: 25, width: 50, height: 50 },
      { x: 75, y: 25, width: 25, height: 50 },
      { x: 0, y: 75, width: 33.33, height: 25 },
      { x: 33.33, y: 75, width: 33.34, height: 25 },
      { x: 66.67, y: 75, width: 33.33, height: 25 }
    ]
  }
];

const MoodboardCanvas = ({ board, onClose, onSave }) => {
  const [elements, setElements] = useState(board.canvasLayout?.elements || []);
  const [selectedId, setSelectedId] = useState(null);
  const [background, setBackground] = useState(board.canvasLayout?.background || '#ffffff');
  const [textMode, setTextMode] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const canvasRef = useRef(null);

  // Helper function to get correct image URL
  const getImageUrl = (imageUrl) => {
    if (!imageUrl) return null;
    const pathWithoutExt = imageUrl.replace(/\.(png|jpg|jpeg|webp)$/i, '');
    const ext = imageUrl.match(/\.(png|jpg|jpeg|webp)$/i)?.[0] || '.png';
    return `https://www.farforrent.com.ua/image/cache/${pathWithoutExt}-300x200${ext}`;
  };

  // Initialize elements from board items if not loaded
  useEffect(() => {
    if (elements.length === 0 && board.items && board.items.length > 0) {
      // Don't auto-add, keep carousel for manual drag
    }
  }, []);

  const handleAddItem = (item) => {
    // Calculate offset for new items so they don't overlap
    const offset = elements.length * 40;
    const newElement = {
      id: `item-${Date.now()}`,
      type: 'product',
      productId: item.product_id,
      productName: item.product?.name,
      imageUrl: item.product?.image_url,
      x: 100 + offset,
      y: 100 + offset,
      width: 200,
      height: 200,
      rotation: 0,
    };
    setElements([...elements, newElement]);
    setSelectedId(newElement.id);
  };

  const handleAddText = () => {
    const newElement = {
      id: `text-${Date.now()}`,
      type: 'text',
      content: 'Текст тут',
      x: 150,
      y: 150,
      width: 200,
      height: 50,
      fontSize: 24,
      color: '#333333',
      fontWeight: 'normal',
    };
    setElements([...elements, newElement]);
    setSelectedId(newElement.id);
    setTextMode(false);
  };

  const handleDragElement = (id, translate) => {
    setElements(
      elements.map((el) => {
        if (el.id === id) {
          return { 
            ...el, 
            x: el.x + translate[0], 
            y: el.y + translate[1] 
          };
        }
        return el;
      })
    );
  };

  const handleResizeElement = (id, width, height) => {
    setElements(
      elements.map((el) =>
        el.id === id ? { ...el, width, height } : el
      )
    );
  };

  const handleRotateElement = (id, rotation) => {
    setElements(
      elements.map((el) =>
        el.id === id ? { ...el, rotation } : el
      )
    );
  };

  const handleDeleteElement = (id) => {
    setElements(elements.filter((el) => el.id !== id));
    setSelectedId(null);
  };

  const handleUpdateText = (id, content) => {
    setElements(
      elements.map((el) =>
        el.id === id ? { ...el, content } : el
      )
    );
  };

  const handleApplyTemplate = (template) => {
    const canvasWidth = 1200;
    const canvasHeight = 800;
    
    // Get products from board items
    const products = board.items || [];
    
    // Create elements from template cells
    const newElements = template.cells.map((cell, index) => {
      const product = products[index];
      if (!product) return null;
      
      return {
        id: `item-${Date.now()}-${index}`,
        type: 'product',
        productId: product.product_id,
        productName: product.product?.name,
        imageUrl: product.product?.image_url,
        x: (cell.x / 100) * canvasWidth,
        y: (cell.y / 100) * canvasHeight,
        width: (cell.width / 100) * canvasWidth,
        height: (cell.height / 100) * canvasHeight,
        rotation: 0,
      };
    }).filter(Boolean);
    
    setElements(newElements);
    setShowTemplates(false);
    setSelectedId(null);
  };

  const handleSaveCanvas = async () => {
    const canvasLayout = {
      elements,
      background,
      zoom,
      updatedAt: new Date().toISOString(),
    };
    
    await onSave(canvasLayout);
  };

  const selectedElement = elements.find((el) => el.id === selectedId);

  return (
    <div className="fixed inset-0 z-50 bg-black bg-opacity-90 flex flex-col">
      {/* Header */}
      <div className="fd-header flex items-center justify-between" style={{padding: '16px 32px', background: '#fff', borderBottom: '1px solid #e3e3e3'}}>
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="fd-btn fd-btn-secondary">
            ← Назад
          </button>
          <h2 className="font-bold" style={{fontSize: '18px', color: '#333'}}>
            {board.board_name} - Візуальний мудборд
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setZoom(Math.max(0.5, zoom - 0.1))} className="fd-btn fd-btn-secondary">
            −
          </button>
          <span style={{fontSize: '12px', color: '#666', minWidth: '50px', textAlign: 'center'}}>
            {Math.round(zoom * 100)}%
          </span>
          <button onClick={() => setZoom(Math.min(2, zoom + 0.1))} className="fd-btn fd-btn-secondary">
            +
          </button>
          <button onClick={handleSaveCanvas} className="fd-btn fd-btn-secondary">
            Зберегти
          </button>
        </div>
      </div>

      {/* Main Content - Left Tools + Canvas + Right Products */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* Left Sidebar - Tools */}
        <div style={{
          width: '240px',
          background: '#fff',
          borderRight: '1px solid #e3e3e3',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          {/* Tools Header */}
          <div style={{
            padding: '20px',
            borderBottom: '1px solid #f0f0f0',
            background: '#fafafa'
          }}>
            <h3 className="font-bold" style={{fontSize: '14px', color: '#333', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
              Інструменти
            </h3>
          </div>

          {/* Tools List */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px'
          }}>
            {/* Layout Templates */}
            <div style={{marginBottom: '20px'}}>
              <button
                onClick={() => setShowTemplates(!showTemplates)}
                className="fd-btn fd-btn-secondary"
                style={{width: '100%'}}
              >
                Шаблони розташування
              </button>
              
              {showTemplates && (
                <div style={{
                  marginTop: '12px',
                  padding: '12px',
                  background: '#f9f9f9',
                  borderRadius: '4px',
                  border: '1px solid #e8e8e8',
                  maxHeight: '400px',
                  overflowY: 'auto'
                }}>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '8px'
                  }}>
                    {LAYOUT_TEMPLATES.map((template) => (
                      <button
                        key={template.id}
                        onClick={() => handleApplyTemplate(template)}
                        style={{
                          padding: '8px',
                          background: '#fff',
                          border: '1px solid #ddd',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                          position: 'relative',
                          aspectRatio: '1'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.borderColor = '#333';
                          e.currentTarget.style.transform = 'translateY(-2px)';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = '#ddd';
                          e.currentTarget.style.transform = 'translateY(0)';
                        }}
                      >
                        {/* Visual preview of template */}
                        <div style={{position: 'relative', width: '100%', height: '100%'}}>
                          {template.cells.map((cell, idx) => (
                            <div
                              key={idx}
                              style={{
                                position: 'absolute',
                                left: `${cell.x}%`,
                                top: `${cell.y}%`,
                                width: `${cell.width}%`,
                                height: `${cell.height}%`,
                                border: '1px solid #ccc',
                                background: '#f5f5f5',
                                boxSizing: 'border-box'
                              }}
                            />
                          ))}
                        </div>
                        <div style={{
                          position: 'absolute',
                          bottom: '4px',
                          left: '4px',
                          right: '4px',
                          fontSize: '9px',
                          color: '#666',
                          textAlign: 'center',
                          background: 'rgba(255,255,255,0.9)',
                          padding: '2px',
                          borderRadius: '2px'
                        }}>
                          {template.name}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div style={{height: '1px', background: '#e8e8e8', margin: '16px 0'}}></div>

            {/* Background Color */}
            <div style={{marginBottom: '20px'}}>
              <button
                onClick={() => setShowColorPicker(!showColorPicker)}
                className="fd-btn fd-btn-secondary"
                style={{width: '100%', justifyContent: 'space-between', display: 'flex', alignItems: 'center'}}
              >
                <span>Фон canvas</span>
                <div style={{
                  width: '24px',
                  height: '24px',
                  background: background,
                  border: '2px solid #ddd',
                  borderRadius: '4px'
                }}></div>
              </button>
              
              {showColorPicker && (
                <div style={{
                  marginTop: '12px',
                  padding: '12px',
                  background: '#f9f9f9',
                  borderRadius: '4px',
                  border: '1px solid #e8e8e8'
                }}>
                  <input
                    type="color"
                    value={background}
                    onChange={(e) => setBackground(e.target.value)}
                    style={{width: '100%', height: '40px', border: 'none', cursor: 'pointer'}}
                  />
                  <div style={{display: 'flex', gap: '8px', marginTop: '12px'}}>
                    <button
                      onClick={() => setBackground('#ffffff')}
                      style={{
                        flex: 1,
                        padding: '8px',
                        background: '#ffffff',
                        border: '1px solid #ddd',
                        borderRadius: '4px',
                        fontSize: '11px',
                        cursor: 'pointer'
                      }}
                    >
                      Білий
                    </button>
                    <button
                      onClick={() => setBackground('#f5f5dc')}
                      style={{
                        flex: 1,
                        padding: '8px',
                        background: '#f5f5dc',
                        border: '1px solid #ddd',
                        borderRadius: '4px',
                        fontSize: '11px',
                        cursor: 'pointer'
                      }}
                    >
                      Бежевий
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div style={{height: '1px', background: '#e8e8e8', margin: '16px 0'}}></div>

            {/* Add Text */}
            <button
              onClick={handleAddText}
              className="fd-btn fd-btn-secondary"
              style={{width: '100%', marginBottom: '12px'}}
            >
              Додати текст
            </button>

            {/* Delete Element */}
            {selectedId && (
              <>
                <div style={{height: '1px', background: '#e8e8e8', margin: '16px 0'}}></div>
                <button
                  onClick={() => handleDeleteElement(selectedId)}
                  className="fd-btn fd-btn-small"
                  style={{color: '#c62828', border: '1px solid #c62828', width: '100%'}}
                >
                  Видалити елемент
                </button>
              </>
            )}
          </div>
        </div>

        {/* Center - Canvas Area */}
        <div className="flex-1 flex flex-col">
          {/* Canvas */}
          <div className="flex-1 overflow-auto" style={{background: '#e8e8e8', padding: '40px'}}>
        <div
          ref={canvasRef}
          className="relative mx-auto"
          style={{
            width: '1200px',
            height: '800px',
            background: background,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            transform: `scale(${zoom})`,
            transformOrigin: 'top center',
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setSelectedId(null);
            }
          }}
        >
          {/* Empty state */}
          {elements.length === 0 && (
            <div className="fd-empty" style={{paddingTop: '200px', textAlign: 'center'}}>
              <div style={{fontSize: '18px', fontWeight: '600', color: '#999', marginBottom: '12px'}}>
                Почніть створювати мудборд
              </div>
              <div className="fd-empty-text" style={{fontSize: '14px', color: '#999', lineHeight: '1.6'}}>
                Клацніть на товар у правій панелі щоб додати його на canvas<br/>
                Використовуйте інструменти зліва для налаштування
              </div>
            </div>
          )}

          {/* Render elements */}
          {elements.map((element) => (
            <div
              key={element.id}
              data-element-id={element.id}
              className="canvas-element"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedId(element.id);
              }}
              style={{
                position: 'absolute',
                left: element.x,
                top: element.y,
                width: element.width,
                height: element.height,
                transform: `rotate(${element.rotation || 0}deg)`,
                cursor: 'move',
                border: selectedId === element.id ? '2px solid #2196F3' : '2px solid transparent',
                boxSizing: 'border-box',
              }}
            >
              {element.type === 'product' ? (
                <div
                  style={{
                    width: '100%',
                    height: '100%',
                    background: element.imageUrl
                      ? `url(${getImageUrl(element.imageUrl)})`
                      : 'linear-gradient(135deg, #f0f0f0, #e4e4e4)',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                    borderRadius: '4px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                  }}
                />
              ) : (
                <div
                  contentEditable={selectedId === element.id}
                  suppressContentEditableWarning
                  onBlur={(e) => handleUpdateText(element.id, e.target.textContent)}
                  style={{
                    width: '100%',
                    height: '100%',
                    fontSize: element.fontSize || 24,
                    color: element.color || '#333',
                    fontWeight: element.fontWeight || 'normal',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '8px',
                    outline: 'none',
                    background: 'transparent',
                  }}
                >
                  {element.content}
                </div>
              )}
            </div>
          ))}

          {/* Moveable for selected element */}
          {selectedId && selectedElement && (
            <Moveable
              target={document.querySelector(`[data-element-id="${selectedId}"]`)}
              draggable={true}
              resizable={true}
              rotatable={true}
              keepRatio={true}
              throttleDrag={0}
              throttleResize={0}
              throttleRotate={0}
              renderDirections={["nw", "n", "ne", "w", "e", "sw", "s", "se"]}
              edge={false}
              zoom={1}
              origin={false}
              padding={{ left: 0, top: 0, right: 0, bottom: 0 }}
              snappable={true}
              snapCenter={true}
              snapThreshold={5}
              onDrag={({ target, beforeTranslate }) => {
                const newX = selectedElement.x + beforeTranslate[0];
                const newY = selectedElement.y + beforeTranslate[1];
                target.style.left = `${newX}px`;
                target.style.top = `${newY}px`;
              }}
              onDragEnd={({ target, lastEvent }) => {
                if (lastEvent) {
                  handleDragElement(selectedId, lastEvent.beforeTranslate);
                }
              }}
              onResize={({ target, width, height, drag }) => {
                target.style.width = `${width}px`;
                target.style.height = `${height}px`;
                target.style.left = `${selectedElement.x + drag.beforeTranslate[0]}px`;
                target.style.top = `${selectedElement.y + drag.beforeTranslate[1]}px`;
              }}
              onResizeEnd={({ target, lastEvent }) => {
                if (lastEvent) {
                  const newWidth = lastEvent.width;
                  const newHeight = lastEvent.height;
                  const dragX = lastEvent.drag.beforeTranslate[0];
                  const dragY = lastEvent.drag.beforeTranslate[1];
                  
                  setElements(
                    elements.map((el) =>
                      el.id === selectedId 
                        ? { ...el, width: newWidth, height: newHeight, x: el.x + dragX, y: el.y + dragY } 
                        : el
                    )
                  );
                }
              }}
              onRotate={({ target, transform }) => {
                target.style.transform = transform;
              }}
              onRotateEnd={({ target, lastEvent }) => {
                if (lastEvent) {
                  handleRotateElement(selectedId, lastEvent.rotation);
                }
              }}
            />
          )}
        </div>
          </div>
        </div>

        {/* Right Sidebar - Products List */}
        <div style={{
          width: '340px',
          background: '#fff',
          borderLeft: '1px solid #e3e3e3',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          {/* Sidebar Header */}
          <div style={{
            padding: '20px',
            borderBottom: '1px solid #f0f0f0',
            background: '#fafafa'
          }}>
            <h3 className="font-bold mb-1" style={{fontSize: '14px', color: '#333', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
              Товари мудборду
            </h3>
            <p className="fd-label">
              Клацніть на товар щоб додати на canvas
            </p>
          </div>

          {/* Products List */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px'
          }}>
            {board.items && board.items.length > 0 ? (
              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px'}}>
                {board.items.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => handleAddItem(item)}
                    className="fd-card cursor-pointer hover:shadow-lg"
                    style={{
                      padding: '8px',
                      background: '#fff',
                      border: '1px solid #e8e8e8',
                      borderRadius: '4px',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <div
                      style={{
                        width: '100%',
                        paddingBottom: '100%',
                        position: 'relative',
                        background: item.product?.image_url
                          ? `url(${getImageUrl(item.product.image_url)})`
                          : 'linear-gradient(135deg, #f0f0f0, #e4e4e4)',
                        backgroundSize: 'cover',
                        backgroundPosition: 'center',
                        borderRadius: '3px',
                        marginBottom: '6px',
                      }}
                    />
                    <p style={{
                      fontSize: '11px',
                      color: '#666',
                      lineHeight: '1.3',
                      height: '30px',
                      overflow: 'hidden',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical'
                    }}>
                      {item.product?.name}
                    </p>
                    <div style={{
                      fontSize: '10px',
                      color: '#999',
                      marginTop: '4px'
                    }}>
                      Кількість: {item.quantity}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="fd-empty" style={{paddingTop: '100px', textAlign: 'center'}}>
                <div style={{fontSize: '14px', fontWeight: '600', color: '#999', marginBottom: '8px'}}>
                  Немає товарів
                </div>
                <div className="fd-empty-text" style={{fontSize: '12px', color: '#999'}}>
                  Додайте товари до мудборду<br/>на головній сторінці
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default MoodboardCanvas;
