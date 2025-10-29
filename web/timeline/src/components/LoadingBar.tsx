import React, { useState, useEffect } from 'react';
import './LoadingBar.css';
import tipsData from '../tips.json';

interface LoadingBarProps {
  isLoading: boolean;
  progress?: number; // 0-100, optional
  message?: string;
}

export function LoadingBar({ isLoading, progress, message }: LoadingBarProps) {
  const [currentTip, setCurrentTip] = useState('');
  const [tipIndex, setTipIndex] = useState(0);

  useEffect(() => {
    if (isLoading && tipsData.loadingTips.length > 0) {
      // Set initial random tip
      const randomIndex = Math.floor(Math.random() * tipsData.loadingTips.length);
      setTipIndex(randomIndex);
      setCurrentTip(tipsData.loadingTips[randomIndex]);

      // Rotate tips every 4 seconds
      const interval = setInterval(() => {
        setTipIndex(prev => {
          const nextIndex = (prev + 1) % tipsData.loadingTips.length;
          setCurrentTip(tipsData.loadingTips[nextIndex]);
          return nextIndex;
        });
      }, 4000);

      return () => clearInterval(interval);
    }
  }, [isLoading]);

  if (!isLoading) return null;

  return (
    <div className="loading-bar-container">
      <div className="loading-bar-wrapper">
        <div className="loading-bar-track">
          <div
            className="loading-bar-fill"
            style={{
              width: progress !== undefined ? `${progress}%` : '100%',
              animation: progress === undefined ? 'indeterminateProgress 1.5s ease-in-out infinite' : 'none'
            }}
          >
            <div className="loading-bar-shimmer" />
          </div>
        </div>
        {message && (
          <div className="loading-bar-message">{message}</div>
        )}
        {currentTip && (
          <div className="loading-bar-tip" key={tipIndex}>
            <span className="loading-bar-tip-icon">💡</span>
            <span className="loading-bar-tip-text">{currentTip}</span>
          </div>
        )}
      </div>
    </div>
  );
}
