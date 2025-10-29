import React, { useState, useRef } from 'react';
import './DopamineButton.css';

interface DopamineButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'success';
  size?: 'sm' | 'md' | 'lg';
}

export function DopamineButton({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  onClick,
  ...props
}: DopamineButtonProps) {
  const [ripples, setRipples] = useState<Array<{ x: number; y: number; id: number }>>([]);
  const [isPressed, setIsPressed] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const rippleIdRef = useRef(0);

  const createRipple = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (!buttonRef.current) return;

    const button = buttonRef.current;
    const rect = button.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const newRipple = { x, y, id: rippleIdRef.current++ };
    setRipples(prev => [...prev, newRipple]);

    setTimeout(() => {
      setRipples(prev => prev.filter(r => r.id !== newRipple.id));
    }, 600);
  };

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    createRipple(event);
    setIsPressed(true);

    setTimeout(() => setIsPressed(false), 200);

    if (onClick) {
      onClick(event);
    }
  };

  return (
    <button
      ref={buttonRef}
      className={`dopamine-button dopamine-button--${variant} dopamine-button--${size} ${isPressed ? 'pressed' : ''} ${className}`}
      onClick={handleClick}
      {...props}
    >
      <span className="dopamine-button__content">{children}</span>
      <div className="dopamine-button__ripples">
        {ripples.map(ripple => (
          <span
            key={ripple.id}
            className="dopamine-button__ripple"
            style={{ left: ripple.x, top: ripple.y }}
          />
        ))}
      </div>
      <div className="dopamine-button__shimmer" />
    </button>
  );
}
