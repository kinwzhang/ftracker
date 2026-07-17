import React from 'react';

interface AlertProps {
  type: 'success' | 'warning' | 'danger' | 'info';
  message: string;
  onDismiss?: () => void;
}

const Alert: React.FC<AlertProps> = ({ type, message, onDismiss }) => {
  return (
    <div className={`alert alert-${type} d-flex align-items-center justify-content-between`} role="alert">
      <span>{message}</span>
      {onDismiss && (
        <button type="button" className="btn-close" aria-label="Close" onClick={onDismiss} />
      )}
    </div>
  );
};

export default Alert;
