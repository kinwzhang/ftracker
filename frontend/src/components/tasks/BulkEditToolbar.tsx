import React from 'react';

interface BulkEditToolbarProps {
  isActive: boolean;
  onEnterBulkEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
}

const BulkEditToolbar: React.FC<BulkEditToolbarProps> = ({
  isActive,
  onEnterBulkEdit,
  onSave,
  onCancel,
}) => {
  if (isActive) {
    return (
      <div className="d-flex gap-2">
        <button className="btn btn-sm btn-success" onClick={onSave}>
          Save All
        </button>
        <button className="btn btn-sm btn-outline-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button className="btn btn-sm btn-outline-secondary" onClick={onEnterBulkEdit}>
      Edit All
    </button>
  );
};

export default BulkEditToolbar;
