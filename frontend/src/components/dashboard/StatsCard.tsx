import React from 'react';

interface StatsCardProps {
  value: number;
  label: string;
  variant: 'success' | 'warning' | 'danger' | 'primary';
}

const variantClass: Record<string, string> = {
  success: 'glass-success',
  warning: 'glass-warning',
  danger: 'glass-danger',
  primary: '',
};

const StatsCard: React.FC<StatsCardProps> = ({ value, label, variant }) => {
  return (
    <div className={`stat-card glass-card ${variantClass[variant] || ''}`}>
      <p className="stat-number">{value}</p>
      <p className="stat-label">{label}</p>
    </div>
  );
};

export default StatsCard;
