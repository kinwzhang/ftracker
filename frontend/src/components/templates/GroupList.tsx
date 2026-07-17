import React, { useState } from 'react';
import type { Group } from '../../types';
import ConfirmDialog from '../common/ConfirmDialog';

interface GroupListProps {
  groups: Group[];
  isExpanded: boolean;
  onToggleExpand: () => void;
  editingGroupId: number | null;
  onEditGroup: (group: Group) => void;
  onSaveGroup: (id: number, name: string) => void;
  onCancelGroup: () => void;
  onDeleteGroup: (id: number) => void;
  onAddGroup: (name: string, sortOrder: number) => void;
}

const GroupList: React.FC<GroupListProps> = ({
  groups,
  isExpanded,
  onToggleExpand,
  editingGroupId,
  onEditGroup,
  onSaveGroup,
  onCancelGroup,
  onDeleteGroup,
  onAddGroup,
}) => {
  const [editName, setEditName] = useState('');
  const [newName, setNewName] = useState('');
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const handleEditStart = (g: Group) => {
    setEditName(g.name);
    onEditGroup(g);
  };

  const handleSave = (id: number) => {
    if (!editName.trim()) return;
    onSaveGroup(id, editName.trim());
  };

  const handleAdd = () => {
    if (!newName.trim()) return;
    onAddGroup(newName.trim(), groups.length);
    setNewName('');
  };

  return (
    <div className="mb-3">
      <button className="btn btn-sm btn-outline-secondary" onClick={onToggleExpand}>
        {isExpanded ? 'Hide Groups' : 'Manage Groups'}
      </button>

      {isExpanded && (
        <div className="glass-card card mt-2">
          <div className="card-header">Groups</div>
          <div className="card-body">
            <div className="d-flex gap-2 mb-3">
              <input
                className="form-control form-control-sm"
                style={{ maxWidth: '300px' }}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="New group name"
                onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
              />
              <button className="btn btn-sm btn-primary" onClick={handleAdd}>Add Group</button>
            </div>
            <div className="table-responsive">
              <table className="table table-sm table-hover mb-0">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Order</th>
                    <th>Templates</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((g) => (
                    <tr key={g.id}>
                      <td>{g.id}</td>
                      <td>
                        {editingGroupId === g.id ? (
                          <div className="d-flex gap-1">
                            <input
                              className="form-control form-control-sm"
                              value={editName}
                              onChange={(e) => setEditName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleSave(g.id);
                                if (e.key === 'Escape') onCancelGroup();
                              }}
                              autoFocus
                            />
                            <button className="btn btn-sm btn-success" onClick={() => handleSave(g.id)}>Save</button>
                            <button className="btn btn-sm btn-secondary" onClick={onCancelGroup}>Cancel</button>
                          </div>
                        ) : (
                          <span style={{ cursor: 'pointer' }} onClick={() => handleEditStart(g)}>
                            {g.name}
                          </span>
                        )}
                      </td>
                      <td>{g.sort_order}</td>
                      <td>{g.template_count ?? '—'}</td>
                      <td>
                        <button className="btn btn-sm btn-outline-danger" onClick={() => setDeleteId(g.id)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                  {groups.length === 0 && (
                    <tr><td colSpan={5} className="text-center text-muted">No groups</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        show={deleteId != null}
        title="Delete Group"
        message="Are you sure you want to delete this group? Templates in this group will not be deleted."
        onConfirm={() => { if (deleteId != null) onDeleteGroup(deleteId); setDeleteId(null); }}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
};

export default GroupList;
