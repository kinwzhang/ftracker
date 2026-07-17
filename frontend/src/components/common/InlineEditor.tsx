import React, { useState, useRef, useEffect } from 'react';

interface InlineEditorProps {
  value: string | number;
  type?: 'text' | 'textarea' | 'number' | 'select';
  options?: Array<{ value: string | number; label: string }>;
  onSave: (value: string | number) => void;
  className?: string;
}

const InlineEditor: React.FC<InlineEditorProps> = ({
  value,
  type = 'text',
  options,
  onSave,
  className = '',
}) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string | number>(value);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      if (inputRef.current instanceof HTMLInputElement) {
        inputRef.current.select();
      }
    }
  }, [editing]);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const handleDoubleClick = () => {
    setDraft(value);
    setEditing(true);
  };

  const handleSave = () => {
    setEditing(false);
    if (draft !== value) {
      onSave(draft);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && type !== 'textarea') {
      e.preventDefault();
      handleSave();
    }
    if (e.key === 'Escape') {
      setDraft(value);
      setEditing(false);
    }
  };

  const handleBlur = () => {
    handleSave();
  };

  if (!editing) {
    return (
      <span
        className={`inline-editor-view ${className}`}
        onDoubleClick={handleDoubleClick}
        style={{ cursor: 'pointer', minHeight: '1.5em', display: 'inline-block' }}
        title="Double-click to edit"
      >
        {value ?? ''}
      </span>
    );
  }

  if (type === 'textarea') {
    return (
      <textarea
        ref={inputRef as React.RefObject<HTMLTextAreaElement>}
        className={`form-control form-control-sm ${className}`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        rows={3}
      />
    );
  }

  if (type === 'select' && options) {
    return (
      <select
        ref={inputRef as React.RefObject<HTMLSelectElement>}
        className={`form-select form-select-sm ${className}`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <input
      ref={inputRef as React.RefObject<HTMLInputElement>}
      type={type}
      className={`form-control form-control-sm ${className}`}
      value={draft}
      onChange={(e) => setDraft(type === 'number' ? Number(e.target.value) : e.target.value)}
      onKeyDown={handleKeyDown}
      onBlur={handleBlur}
    />
  );
};

export default InlineEditor;
