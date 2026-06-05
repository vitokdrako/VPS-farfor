/**
 * ProductDetailsModal — розгорнута картка товару при кліку на фото.
 * Тягне повну інформацію через /event/products/{id}
 */
import React, { useEffect, useState } from 'react';
import api from '../api/axios';

const resolveImageUrl = (url) => {
  if (!url) return null;
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) return url;
  if (url.startsWith('/')) return url;
  return `/${url}`;
};

const ProductDetailsModal = ({ productId, boardDates, onClose, onAddToBoard }) => {
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [qty, setQty] = useState(1);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (!productId) return;
    let cancelled = false;
    setLoading(true);
    setError('');

    const params = new URLSearchParams();
    if (boardDates?.startDate) params.set('date_from', boardDates.startDate);
    if (boardDates?.endDate) params.set('date_to', boardDates.endDate);
    const query = params.toString() ? `?${params.toString()}` : '';

    api.get(`/event/products/${productId}${query}`)
      .then(r => { if (!cancelled) setProduct(r.data); })
      .catch(e => { if (!cancelled) setError(e?.response?.data?.detail || 'Не вдалося завантажити товар'); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [productId, boardDates?.startDate, boardDates?.endDate]);

  const handleAdd = async () => {
    if (!boardDates?.startDate || !boardDates?.endDate) {
      alert('Спочатку оберіть дати оренди в мудборді!');
      return;
    }
    if (!product) return;
    setAdding(true);
    try {
      await onAddToBoard({ ...product, _quantity: qty });
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setAdding(false);
    }
  };

  if (!productId) return null;

  const img = product ? resolveImageUrl(product.image_url) : null;
  const available = product?.available ?? product?.quantity ?? 0;
  const maxAdd = Math.max(1, available || 1);
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;

  return (
    <div
      data-testid="product-details-overlay"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.55)',
        zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: isMobile ? '0' : '24px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          borderRadius: isMobile ? '0' : '12px',
          maxWidth: '960px', width: '100%',
          maxHeight: isMobile ? '100vh' : '90vh',
          height: isMobile ? '100vh' : 'auto',
          overflow: 'hidden', display: 'grid',
          gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1fr) minmax(0, 1fr)',
          gridTemplateRows: isMobile ? 'minmax(280px, 45vh) 1fr' : 'auto',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}
        data-testid="product-details-modal"
      >
        {/* Зображення */}
        <div style={{background: '#fafafa', minHeight: isMobile ? '280px' : '480px', position: 'relative'}}>
          <button
            data-testid="product-details-close"
            onClick={onClose}
            style={{
              position: 'absolute', top: '12px', right: '12px', zIndex: 2,
              background: '#fff', border: 'none', borderRadius: '50%',
              width: '36px', height: '36px', cursor: 'pointer', fontSize: '18px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            }}
            aria-label="Закрити"
          >×</button>
          {img ? (
            <img src={img} alt={product?.name || ''}
              style={{width: '100%', height: '100%', objectFit: 'contain', padding: '16px', display: 'block'}}
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          ) : (
            <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: '64px'}}>🎨</div>
          )}
        </div>

        {/* Інфо */}
        <div style={{padding: isMobile ? '20px' : '32px', overflowY: 'auto'}}>
          {loading && <div style={{color: '#999'}}>Завантаження...</div>}
          {error && <div style={{color: '#c62828'}}>⚠️ {error}</div>}
          {product && (
            <>
              <div style={{fontSize: '11px', color: '#999', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '6px'}}>
                {product.sku}
              </div>
              <h2 style={{fontSize: '24px', fontWeight: '700', color: '#0f172a', marginBottom: '12px', lineHeight: '1.3'}}>
                {product.name}
              </h2>

              {/* Доступність */}
              <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px'}}>
                <span style={{
                  padding: '4px 12px', borderRadius: '999px', fontSize: '12px', fontWeight: '600',
                  background: available > 0 ? '#dcfce7' : '#fee2e2',
                  color: available > 0 ? '#166534' : '#991b1b',
                }}>
                  {available > 0 ? `✓ Доступно: ${available} шт` : '✗ Недоступно'}
                </span>
                {product.quantity > available && (
                  <span style={{
                    padding: '4px 12px', borderRadius: '999px', fontSize: '12px',
                    background: '#fef3c7', color: '#92400e',
                  }}>
                    Всього в каталозі: {product.quantity} шт
                  </span>
                )}
              </div>

              {/* Характеристики */}
              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 24px', marginBottom: '20px'}}>
                {product.category_name && (
                  <Field label="Категорія" value={product.category_name} />
                )}
                {product.subcategory_name && (
                  <Field label="Підкатегорія" value={product.subcategory_name} />
                )}
                {product.color && <Field label="Колір" value={product.color} />}
                {product.material && <Field label="Матеріал" value={product.material} />}
                {product.size && <Field label="Розмір" value={product.size} />}
                {product.dimensions && <Field label="Габарити" value={product.dimensions} />}
                {product.width && <Field label="Ширина" value={`${product.width} см`} />}
                {product.height && <Field label="Висота" value={`${product.height} см`} />}
                {product.depth && <Field label="Глибина" value={`${product.depth} см`} />}
                {product.weight && <Field label="Вага" value={`${product.weight} кг`} />}
              </div>

              {/* Комплектація */}
              {(product.set_contents || product.complectation || product.components) && (
                <div style={{marginBottom: '20px'}}>
                  <div style={{fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.8px'}}>
                    Комплектація
                  </div>
                  <div style={{fontSize: '14px', color: '#0f172a', lineHeight: '1.55', whiteSpace: 'pre-wrap', padding: '12px', background: '#f8fafc', borderRadius: '6px'}}>
                    {product.set_contents || product.complectation || product.components}
                  </div>
                </div>
              )}

              {/* Опис */}
              {product.description && (
                <div style={{marginBottom: '20px'}}>
                  <div style={{fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.8px'}}>
                    Опис
                  </div>
                  <div style={{fontSize: '14px', color: '#475569', lineHeight: '1.55', whiteSpace: 'pre-wrap'}}>
                    {product.description}
                  </div>
                </div>
              )}

              {/* Ціна */}
              <div style={{
                background: '#f8fafc', borderRadius: '8px', padding: '16px',
                marginBottom: '16px', display: 'flex', alignItems: 'baseline', gap: '8px',
              }}>
                <span style={{fontSize: '32px', fontWeight: '800', color: '#0a3d2e'}}>
                  ₴{(product.rental_price || 0).toLocaleString('uk-UA')}
                </span>
                <span style={{fontSize: '14px', color: '#64748b'}}>/день</span>
              </div>

              {/* Кількість + кнопка */}
              {boardDates?.startDate && boardDates?.endDate ? (
                <div>
                  <div style={{display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px'}}>
                    <label style={{fontSize: '13px', color: '#64748b'}}>Кількість:</label>
                    <button
                      onClick={() => setQty(q => Math.max(1, q - 1))}
                      style={{width: '32px', height: '32px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#fff', cursor: 'pointer', fontSize: '18px'}}
                    >−</button>
                    <input
                      type="number" min="1" max={maxAdd} value={qty}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10) || 1;
                        setQty(Math.min(maxAdd, Math.max(1, v)));
                      }}
                      data-testid="product-details-qty"
                      style={{width: '64px', textAlign: 'center', padding: '6px', borderRadius: '6px', border: '1px solid #cbd5e1'}}
                    />
                    <button
                      onClick={() => setQty(q => Math.min(maxAdd, q + 1))}
                      disabled={qty >= maxAdd}
                      style={{width: '32px', height: '32px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#fff', cursor: qty >= maxAdd ? 'not-allowed' : 'pointer', fontSize: '18px'}}
                    >+</button>
                    <span style={{fontSize: '12px', color: '#94a3b8'}}>максимум {maxAdd}</span>
                  </div>
                  <button
                    onClick={handleAdd}
                    disabled={adding || available <= 0}
                    data-testid="product-details-add"
                    style={{
                      width: '100%', padding: '14px', background: '#0a3d2e', color: '#fff',
                      border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: '700',
                      cursor: (adding || available <= 0) ? 'not-allowed' : 'pointer',
                      opacity: (adding || available <= 0) ? 0.6 : 1,
                      textTransform: 'uppercase', letterSpacing: '0.5px',
                    }}
                  >
                    {adding ? 'Додається...' : `Додати в підбірку (${qty} шт)`}
                  </button>
                </div>
              ) : (
                <div style={{padding: '12px', background: '#fef3c7', borderRadius: '8px', fontSize: '13px', color: '#92400e'}}>
                  ⚠️ Оберіть дати оренди у боксі «Мій івент» щоб додати в підбірку
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const Field = ({label, value}) => (
  <div>
    <div style={{fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '3px'}}>{label}</div>
    <div style={{fontSize: '14px', color: '#0f172a', fontWeight: '500'}}>{value}</div>
  </div>
);

export default ProductDetailsModal;
