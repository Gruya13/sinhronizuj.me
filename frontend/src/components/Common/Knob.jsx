import { useEffect, useRef, useState } from 'react';

export default function Knob({
  label,
  value,
  min,
  max,
  step = 1,
  defaultValue = 0,
  unit = '',
  onChange,
  onRelease,
  onStartChange
}) {
  const knobRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ y: 0, val: 0 });

  // Računanje procenta i ugla (-135 do +135 stepeni)
  const pct = Math.min(Math.max((value - min) / (max - min), 0), 1);
  const angle = -135 + pct * 270;

  // SVG parametri za kružni prsten
  const radius = 24;
  const strokeWidth = 3;
  const circumference = 2 * Math.PI * radius;
  // Pokrivamo samo 270 stepeni (3/4 kruga)
  const arcLength = circumference * 0.75;
  const strokeDashoffset = circumference - pct * arcLength;

  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
    if (onStartChange) onStartChange();
    dragStartRef.current = {
      y: e.clientY,
      val: value
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const handleMouseMove = (e) => {
    const deltaY = dragStartRef.current.y - e.clientY;
    // Osetljivost: 150 piksela prevlačenja za pun opseg min->max
    const sensitivity = 150;
    const range = max - min;
    const deltaVal = (deltaY / sensitivity) * range;
    
    let newVal = dragStartRef.current.val + deltaVal;
    newVal = Math.min(Math.max(newVal, min), max);
    
    // Zaokruživanje na step
    const stepsCount = Math.round((newVal - min) / step);
    const roundedVal = min + stepsCount * step;
    
    // Formatiranje broja da izbegnemo JS float greške (npr. 0.300000000000004)
    const precision = step.toString().split('.')[1]?.length || 0;
    const finalVal = parseFloat(roundedVal.toFixed(precision));

    if (finalVal !== value && onChange) {
      onChange(finalVal);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
    if (onRelease) {
      onRelease();
    }
  };

  const handleDoubleClick = () => {
    if (onStartChange) onStartChange();
    if (onChange) onChange(defaultValue);
    setTimeout(() => {
      if (onRelease) onRelease();
    }, 50);
  };

  // Touch podrška za mobilne
  const handleTouchStart = (e) => {
    if (e.touches.length !== 1) return;
    setIsDragging(true);
    if (onStartChange) onStartChange();
    dragStartRef.current = {
      y: e.touches[0].clientY,
      val: value
    };
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('touchend', handleTouchEnd);
  };

  const handleTouchMove = (e) => {
    if (e.touches.length !== 1) return;
    e.preventDefault(); // Sprečavamo scroll tokom okretanja
    const deltaY = dragStartRef.current.y - e.touches[0].clientY;
    const sensitivity = 150;
    const range = max - min;
    const deltaVal = (deltaY / sensitivity) * range;
    
    let newVal = dragStartRef.current.val + deltaVal;
    newVal = Math.min(Math.max(newVal, min), max);
    
    const stepsCount = Math.round((newVal - min) / step);
    const roundedVal = min + stepsCount * step;
    const precision = step.toString().split('.')[1]?.length || 0;
    const finalVal = parseFloat(roundedVal.toFixed(precision));

    if (finalVal !== value && onChange) {
      onChange(finalVal);
    }
  };

  const handleTouchEnd = () => {
    setIsDragging(false);
    document.removeEventListener('touchmove', handleTouchMove);
    document.removeEventListener('touchend', handleTouchEnd);
    if (onRelease) {
      onRelease();
    }
  };

  // Cleanup kod unmount-a
  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  }, []);

  return (
    <div 
      style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        gap: '6px', 
        userSelect: 'none',
        width: '76px'
      }}
    >
      {/* Labela na vrhu */}
      <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 'bold', letterSpacing: '0.5px', textAlign: 'center', whiteSpace: 'nowrap' }}>
        {label}
      </span>

      {/* Kružni deo */}
      <div
        ref={knobRef}
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
        onDoubleClick={handleDoubleClick}
        style={{
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          position: 'relative',
          cursor: isDragging ? 'grabbing' : 'grab',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'radial-gradient(circle, #1e293b 0%, #0f172a 100%)',
          boxShadow: isDragging 
            ? '0 0 15px var(--primary-glow), inset 0 2px 4px rgba(0,0,0,0.5)' 
            : '0 4px 10px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)',
          border: '1px solid rgba(255,255,255,0.04)',
          transition: 'box-shadow 0.2s'
        }}
      >
        {/* Aktivni svetleći prsten oko kruga */}
        <svg 
          style={{ 
            position: 'absolute', 
            top: 0, 
            left: 0, 
            width: '100%', 
            height: '100%', 
            transform: 'rotate(135deg)',
            pointerEvents: 'none'
          }}
        >
          {/* Pozadinska linija */}
          <circle
            cx="28"
            cy="28"
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.03)"
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={circumference - arcLength}
            strokeLinecap="round"
          />
          {/* Aktivna linija */}
          <circle
            cx="28"
            cy="28"
            r={radius}
            fill="none"
            stroke="var(--primary)"
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{ 
              filter: 'drop-shadow(0 0 2px var(--primary-glow))',
              transition: isDragging ? 'none' : 'stroke-dashoffset 0.15s ease'
            }}
          />
        </svg>

        {/* Unutrašnji rotor sa linijom pokazivača */}
        <div
          style={{
            width: '38px',
            height: '38px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #334155 0%, #1e293b 100%)',
            boxShadow: '0 2px 5px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1)',
            transform: `rotate(${angle}deg)`,
            transition: isDragging ? 'none' : 'transform 0.15s ease',
            position: 'relative',
            display: 'flex',
            justifyContent: 'center'
          }}
        >
          {/* Indikaciona crta */}
          <div
            style={{
              width: '2px',
              height: '8px',
              background: isDragging ? 'var(--primary)' : '#e2e8f0',
              borderRadius: '1px',
              position: 'absolute',
              top: '3px',
              boxShadow: isDragging ? '0 0 6px var(--primary-glow)' : 'none'
            }}
          />
        </div>
      </div>

      {/* Tekstualna vrednost ispod */}
      <span 
        style={{ 
          fontSize: '0.75rem', 
          fontFamily: 'monospace', 
          fontWeight: 'bold', 
          color: isDragging ? 'var(--primary)' : '#cbd5e1',
          transition: 'color 0.2s',
          marginTop: '2px'
        }}
      >
        {value > 0 && unit === 'dB' ? `+${value}` : value} {unit}
      </span>
    </div>
  );
}
